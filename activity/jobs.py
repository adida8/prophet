"""Background jobs for activity signals.

Three jobs, each idempotent and self-contained:
  aggregate_match_activity  — UPSERT match_aggregates from raw rows.
  seed_match_activity       — top up seeded views + votes toward stage targets.
  prune_old_views           — drop view rows older than 7 days.

The activity_refresh_loop.py at the project root runs each on its own
cadence (60s / 8m / daily). Each job opens its own pool conn; if the
pool isn't initialised (DATABASE_URL unset) the call raises and the loop
logs + sleeps.

For the seed engine — spec-driven ranges live as module constants near
the top so they're easy to tune from one place.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from .db import get_pool

log = logging.getLogger("activity.jobs")


# --- aggregator -------------------------------------------------------------

# One UPSERT computes everything in a single round trip. At launch scale
# (<100k rows in each table) a full recompute is sub-second; an O(changed)
# variant is unnecessary until that stops being true.
_AGGREGATE_SQL = """
INSERT INTO match_aggregates AS agg
  (match_id, views_24h, votes_total, sharp_call, fair_call, off_mark,
   wait_see, aligned_pct, seeded_share, refreshed_at)
SELECT
  m.match_id,
  COALESCE(v.views_24h, 0),
  COALESCE(r.votes_total, 0),
  COALESCE(r.sharp_call, 0),
  COALESCE(r.fair_call, 0),
  COALESCE(r.off_mark, 0),
  COALESCE(r.wait_see, 0),
  CASE WHEN COALESCE(r.votes_total, 0) > 0
       THEN round(
              (COALESCE(r.sharp_call, 0) + COALESCE(r.fair_call, 0))::numeric
              / r.votes_total * 100)::int
       ELSE NULL END,
  CASE WHEN (COALESCE(v.total_views, 0) + COALESCE(r.votes_total, 0)) > 0
       THEN ((COALESCE(v.seeded_views, 0) + COALESCE(r.seeded_votes, 0))::numeric
             / (COALESCE(v.total_views, 0) + COALESCE(r.votes_total, 0)))
       ELSE NULL END,
  now()
FROM (
  SELECT match_id FROM match_views
  UNION
  SELECT match_id FROM match_reactions
) m
LEFT JOIN (
  SELECT match_id,
         COUNT(DISTINCT anon_id) FILTER (
             WHERE viewed_at > now() - interval '1 day') AS views_24h,
         COUNT(*) AS total_views,
         COUNT(*) FILTER (WHERE seeded = true) AS seeded_views
  FROM match_views
  GROUP BY match_id
) v USING (match_id)
LEFT JOIN (
  SELECT match_id,
         COUNT(*) AS votes_total,
         COUNT(*) FILTER (WHERE reaction = 'sharp_call') AS sharp_call,
         COUNT(*) FILTER (WHERE reaction = 'fair_call')  AS fair_call,
         COUNT(*) FILTER (WHERE reaction = 'off_mark')   AS off_mark,
         COUNT(*) FILTER (WHERE reaction = 'wait_see')   AS wait_see,
         COUNT(*) FILTER (WHERE seeded = true) AS seeded_votes
  FROM match_reactions
  GROUP BY match_id
) r USING (match_id)
ON CONFLICT (match_id) DO UPDATE SET
  views_24h    = EXCLUDED.views_24h,
  votes_total  = EXCLUDED.votes_total,
  sharp_call   = EXCLUDED.sharp_call,
  fair_call    = EXCLUDED.fair_call,
  off_mark     = EXCLUDED.off_mark,
  wait_see     = EXCLUDED.wait_see,
  aligned_pct  = EXCLUDED.aligned_pct,
  seeded_share = EXCLUDED.seeded_share,
  refreshed_at = EXCLUDED.refreshed_at;
"""


async def aggregate_match_activity() -> int:
    """Recompute match_aggregates from raw tables. Returns rows touched."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(_AGGREGATE_SQL)
    # asyncpg returns command tag like "INSERT 0 12"
    parts = result.split()
    return int(parts[-1]) if parts and parts[-1].isdigit() else 0


# --- seed engine -----------------------------------------------------------

# Per ACTIVITY_SIGNALS_SPEC.md §"Seed engine".
# Tuple = (views_lo, views_hi, votes_lo, votes_hi) at Tier-3 baseline (1×).
_STAGES = (
    # (days_to_kickoff_threshold_lo, threshold_hi, views_range, votes_range)
    (14, 9999, (12, 30),  (2, 5)),     # > 14d away
    (5,  14,   (25, 60),  (4, 10)),    # 14d → 5d
    (1,  5,    (50, 130), (8, 20)),    # 5d → 1d
    (-1, 1,    (100, 260), (15, 40)),  # match day (incl. day-of)
)

_HARD_CAP_VIEWS_DAY = 450
_HARD_CAP_VOTES_LIFETIME = 70

_REACTION_DISTRIBUTION = {
    "pick":  {"sharp_call": 0.45, "fair_call": 0.30, "off_mark": 0.12, "wait_see": 0.13},
    "pass":  {"sharp_call": 0.20, "fair_call": 0.25, "off_mark": 0.18, "wait_see": 0.37},
    "avoid": {"sharp_call": 0.10, "fair_call": 0.15, "off_mark": 0.50, "wait_see": 0.25},
}

_AUTO_DECAY_REAL_VIEWS = 60
_AUTO_DECAY_REAL_VOTES = 25

_MADRID = ZoneInfo("Europe/Madrid")
# 8-minute cadence → 180 ticks/day.
_TICKS_PER_DAY = 180


def _stage_for(days_to_kickoff: float) -> Optional[tuple[tuple[int, int], tuple[int, int]]]:
    for lo, hi, views, votes in _STAGES:
        if lo <= days_to_kickoff < hi:
            return views, votes
    return None


def _time_of_day_weight(now_utc: datetime) -> float:
    """Madrid-local activity weight. Peak ~1.6×, quiet ~0.2×, baseline 1.0×."""
    local_hour = now_utc.astimezone(_MADRID).hour
    if 19 <= local_hour <= 23:
        return 1.6
    if local_hour >= 9 or local_hour <= 1:
        return 1.0
    if 2 <= local_hour <= 7:
        return 0.2
    return 0.6


def _weighted_reaction(distribution: dict[str, float]) -> str:
    return random.choices(
        list(distribution.keys()),
        weights=list(distribution.values()),
        k=1,
    )[0]


def _read_priced_fixtures(output_dir: Path) -> list[dict]:
    """Read desk's published index + per-match JSONs for seed inputs.

    Each returned dict carries: match_id, kickoff_utc, team_a, team_b,
    verdict_state. Missing or unreadable files are skipped silently —
    the seed engine should never block on a desk publish hiccup.
    """
    index_path = output_dir / "index.json"
    if not index_path.exists():
        return []
    try:
        index = json.loads(index_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []

    out: list[dict] = []
    for row in index.get("matches", []):
        mid = row.get("match_id")
        if not mid:
            continue
        per_match = output_dir / f"{mid}.json"
        if not per_match.exists():
            continue
        try:
            payload = json.loads(per_match.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        try:
            ko = datetime.fromisoformat(payload["kickoff_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        out.append({
            "match_id": mid,
            "kickoff_utc": ko,
            "team_a": payload.get("team_a", ""),
            "team_b": payload.get("team_b", ""),
            "verdict_state": (payload.get("verdict") or {}).get("state", "pass"),
        })
    return out


async def seed_match_activity(
    *,
    output_dir: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Top up seeded views + votes toward stage targets. Returns counters."""
    from desk.sports.football.data.team_popularity import match_popularity_multiplier

    now = now or datetime.now(timezone.utc)
    output_dir = output_dir or Path("desk/data/output/football")

    fixtures = _read_priced_fixtures(output_dir)
    if not fixtures:
        return {"matches_seen": 0, "views_inserted": 0, "votes_inserted": 0}

    tod_weight = _time_of_day_weight(now)
    pool = get_pool()
    views_inserted = 0
    votes_inserted = 0
    decay_set = 0

    async with pool.acquire() as conn:
        for fx in fixtures:
            mid = fx.get("match_id", "?")
            try:
                # Per-fixture try/except — before this guard, a single
                # bad fixture (SQL error, missing field) bubbled out of
                # the for-loop and killed the entire seed cycle. Then
                # _safe_loop slept 8 minutes before the next attempt, so
                # most matches went unseeded.
                ko = fx["kickoff_utc"]
                days_to_ko = (ko - now).total_seconds() / 86400

                stage = _stage_for(days_to_ko)
                if stage is None:
                    continue  # post-kickoff window not yet defined
                views_range, votes_range = stage

                # Skip + decay if real engagement crossed the threshold.
                disabled = await conn.fetchval(
                    "SELECT seed_disabled FROM match_aggregates WHERE match_id = $1", mid,
                )
                if disabled:
                    continue

                real_views = await conn.fetchval(
                    "SELECT count(DISTINCT anon_id) FROM match_views "
                    "WHERE match_id = $1 AND seeded = false "
                    "AND viewed_at > now() - interval '1 day'",
                    mid,
                ) or 0
                real_votes = await conn.fetchval(
                    "SELECT count(*) FROM match_reactions "
                    "WHERE match_id = $1 AND seeded = false",
                    mid,
                ) or 0
                if real_views >= _AUTO_DECAY_REAL_VIEWS and real_votes >= _AUTO_DECAY_REAL_VOTES:
                    await conn.execute(
                        "INSERT INTO match_aggregates (match_id, seed_disabled, refreshed_at) "
                        "VALUES ($1, true, now()) "
                        "ON CONFLICT (match_id) DO UPDATE SET seed_disabled = true",
                        mid,
                    )
                    decay_set += 1
                    continue

                mult = match_popularity_multiplier(fx["team_a"], fx["team_b"])

                # ── views: maintain a daily rate ────────────────────────
                view_target_day = min(
                    int(random.uniform(*views_range) * mult),
                    _HARD_CAP_VIEWS_DAY,
                )
                current_seeded_24h = await conn.fetchval(
                    "SELECT count(*) FROM match_views "
                    "WHERE match_id = $1 AND seeded = true "
                    "AND viewed_at > now() - interval '1 day'",
                    mid,
                ) or 0
                # Per-tick budget, modulated by TOD weight. The +1 noise
                # floor keeps quiet hours from going to zero.
                this_tick_views = max(
                    0,
                    int(round(view_target_day / _TICKS_PER_DAY * tod_weight + random.random())),
                )
                this_tick_views = min(this_tick_views, view_target_day - current_seeded_24h)

                for _ in range(max(0, this_tick_views)):
                    jitter_secs = int(random.uniform(0, 240))
                    # Multiplication with an interval literal — the
                    # version-agnostic form. `$N || ' seconds'` can throw
                    # under some PG coercion rules.
                    await conn.execute(
                        "INSERT INTO match_views "
                        "(match_id, anon_id, ip_hash, seeded, viewed_at) "
                        "VALUES ($1, $2, $3, true, now() - ($4 * interval '1 second'))",
                        mid, f"seed:{uuid.uuid4()}", "seed", jitter_secs,
                    )
                    views_inserted += 1

                # ── votes: ramp toward lifetime target ──────────────────
                vote_target_lifetime = min(
                    int(random.uniform(*votes_range) * mult),
                    _HARD_CAP_VOTES_LIFETIME,
                )
                current_seeded_votes = await conn.fetchval(
                    "SELECT count(*) FROM match_reactions "
                    "WHERE match_id = $1 AND seeded = true",
                    mid,
                ) or 0
                gap = vote_target_lifetime - current_seeded_votes
                if gap <= 0:
                    continue
                # Ramp over ~24h of ticks (180), at least 1/tick.
                this_tick_votes = min(gap, max(1, gap // 60))

                dist = _REACTION_DISTRIBUTION.get(
                    fx["verdict_state"], _REACTION_DISTRIBUTION["pass"]
                )
                for _ in range(this_tick_votes):
                    reaction = _weighted_reaction(dist)
                    await conn.execute(
                        "INSERT INTO match_reactions "
                        "(match_id, anon_id, reaction, seeded, voted_at) "
                        "VALUES ($1, $2, $3, true, now())",
                        mid, f"seed:{uuid.uuid4()}", reaction,
                    )
                    votes_inserted += 1
            except Exception:  # noqa: BLE001
                log.exception("activity seed: skipping %s", mid)
                continue

    log.info(
        "activity seed: matches=%d views_inserted=%d votes_inserted=%d decay=%d",
        len(fixtures), views_inserted, votes_inserted, decay_set,
    )
    return {
        "matches_seen": len(fixtures),
        "views_inserted": views_inserted,
        "votes_inserted": votes_inserted,
        "decay_set": decay_set,
    }


# --- prune -----------------------------------------------------------------


async def prune_old_views(retention_days: int = 7) -> int:
    """Delete view rows older than `retention_days`. Returns rows dropped."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM match_views "
            "WHERE viewed_at < now() - ($1 || ' days')::interval",
            str(retention_days),
        )
    parts = result.split()
    return int(parts[-1]) if parts and parts[-1].isdigit() else 0
