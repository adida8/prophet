"""api-football /injuries — Phase B.3 data side.

Per data-layer spec §5 Phase 4:
  * Pre-Phase-4 source audit (gate — first). Confirm api-football
    reliably provides, on the chosen plan's endpoints, per-player
    `recent_minutes_share`, `role`, and `position`. If it can't,
    ship availability-only and keep the hook in Shadow.
  * Late-binding T-3d (poll every 6-12h) → T-1h (poll hourly).
  * Bounded per-team Elo penalty (per spec design).

This module ships the **data path**. The Elo-penalty hook lives next
to the existing news-signals hard_signals path (see hard_signals.py);
both feed into the late-binding adjustment ladder.

Source-audit helper exposed here so the operator can run
`desk b3-audit` against the live key + confirm endpoint quality
BEFORE flipping DESK_INJURY_FETCH=1 in prod. Pure audit reads — no
writes to verdict path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from desk.data.api_football.client import APIFootballClient, APIFootballError

_LOG = logging.getLogger(__name__)

# Position-importance weights per spec §4.B.3 design.
POSITION_WEIGHT: dict[str, float] = {
    "Goalkeeper": 1.5,
    "Defender":   1.0,
    "Midfielder": 1.0,
    "Attacker":   1.0,
}
# Centre-backs + defensive mids ride the 1.2 multiplier per the spec
# example. api-football's `position` field is coarse (Defender /
# Midfielder / Attacker / Goalkeeper); the centre-back distinction
# isn't surfaced cleanly. v1 uses the coarse mapping; refinement
# follows once the audit confirms a sub-position field exists.

DEFAULT_POSITION_WEIGHT: float = 0.8   # safety net for unknown position


@dataclass(frozen=True)
class InjuryDatum:
    """One injured / unavailable player flagged by api-football.

    `player_id` is api-football's numeric id. `team_id` is the
    api-football team id (resolved via team_resolution upstream).
    """
    team_id:         int
    player_id:       int
    player_name:     str
    type:            str       # e.g. "Missing Fixture", "Questionable"
    reason:          str
    position:        str | None
    fetched_at:      datetime


@dataclass(frozen=True)
class InjuryFetchOutcome:
    iso3:        str
    team_id:     int | None
    status:      str             # "ok", "no_team_id", "fetch_failed", "error"
    n_items:     int = 0
    items:       tuple[InjuryDatum, ...] = ()
    error:       str | None = None


def _parse_injury_entry(entry: dict, *, fetched_at: datetime) -> InjuryDatum | None:
    """Normalise one entry from /injuries' `response` array.

    api-football's payload shape:
      {
        "player": {"id": 12345, "name": "...", "position": "Defender", "photo": "..."},
        "team":   {"id": 33, "name": "...", "logo": "..."},
        "fixture":{"id": 1234, "date": "...", ...},
        "league": {...},
        "type":   "Missing Fixture",
        "reason": "Knock"
      }

    Returns None when the shape doesn't match — we don't fail the
    whole batch on a single malformed row.
    """
    player = entry.get("player") or {}
    team = entry.get("team") or {}
    try:
        return InjuryDatum(
            team_id=int(team["id"]),
            player_id=int(player["id"]),
            player_name=str(player.get("name") or ""),
            type=str(entry.get("type") or ""),
            reason=str(entry.get("reason") or ""),
            position=player.get("position"),
            fetched_at=fetched_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


async def fetch_for_team(
    api_football_team_id: int,
    *,
    season: int,
    client: APIFootballClient,
) -> tuple[str, list[InjuryDatum]]:
    """Return (status, items). Status is "ok" on success;
    "fetch_failed" / "error" on failure (items=[]).
    """
    try:
        resp = await client.get(
            "/injuries",
            params={
                "team":   str(api_football_team_id),
                "season": str(season),
            },
        )
    except APIFootballError as e:
        return f"{e.kind}", []
    now = datetime.now(tz=timezone.utc)
    items: list[InjuryDatum] = []
    for entry in (resp.payload.get("response") or []):
        parsed = _parse_injury_entry(entry, fetched_at=now)
        if parsed is not None:
            items.append(parsed)
    return "ok", items


# ── Source audit ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class B3SourceAudit:
    """Surfaces what api-football actually returns so the operator can
    decide if the spec's player-level importance attributes are
    available before flipping DESK_INJURY_FETCH=1.

    Three signals checked across a probe sample:
      * coverage_rate — fraction of probed teams that return any rows
      * has_position_rate — fraction of rows with `player.position` set
      * has_type_rate — fraction of rows with non-empty `type`
    """
    probed_team_ids:        tuple[int, ...]
    coverage_rate:          float
    has_position_rate:      float
    has_type_rate:          float
    rows_total:             int

    @property
    def passes(self) -> bool:
        """Audit clears when:
          * >= 60% of probed teams return at least one row
          * >= 90% of returned rows have position
          * >= 90% of returned rows have type
        Loose-but-non-trivial floors; spec calls for the operator's
        judgement once this report is in front of them.
        """
        return (self.coverage_rate >= 0.60
                and self.has_position_rate >= 0.90
                and self.has_type_rate >= 0.90)

    def headline(self) -> str:
        mark = "✓" if self.passes else "✗"
        return (
            f"api-football B.3 audit · {mark} "
            f"coverage={self.coverage_rate*100:.0f}% · "
            f"position={self.has_position_rate*100:.0f}% · "
            f"type={self.has_type_rate*100:.0f}% · "
            f"rows={self.rows_total}"
        )


async def run_source_audit(
    team_ids: list[int],
    *,
    season:  int,
    client:  APIFootballClient,
) -> B3SourceAudit:
    n_teams_with_rows = 0
    rows_total = 0
    rows_with_position = 0
    rows_with_type = 0
    for tid in team_ids:
        status, items = await fetch_for_team(tid, season=season, client=client)
        if status != "ok":
            continue
        if items:
            n_teams_with_rows += 1
        for item in items:
            rows_total += 1
            if item.position:
                rows_with_position += 1
            if item.type:
                rows_with_type += 1

    n_probed = len(team_ids) or 1
    return B3SourceAudit(
        probed_team_ids=tuple(team_ids),
        coverage_rate=n_teams_with_rows / n_probed,
        has_position_rate=(rows_with_position / rows_total) if rows_total else 0.0,
        has_type_rate=(rows_with_type / rows_total) if rows_total else 0.0,
        rows_total=rows_total,
    )
