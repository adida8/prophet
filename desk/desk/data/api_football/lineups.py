"""api-football `/fixtures/lineups` — Slice B / N3 of the team-news spec.

Two calls compose the lineup path:

  1. `/fixtures?team={home_id}&season={s}` (filtered by kickoff date) —
     resolves a `FixtureRef.match_id` to the api-football `fixture_id`.
     Cached in `fixture_resolution` after first hit so the T-90m loop
     doesn't re-query for every poll.

  2. `/fixtures/lineups?fixture={fixture_id}` — returns both teams'
     lineups. We split the response into two `LineupRow` entries and
     upsert per (fixture_id, team_id).

State classification:

  * `state="confirmed"` — api-football's payload carries non-empty
    `startXI` (11 players) for the team. This is the canonical signal
    that an XI has been announced.
  * `state="predicted"` — payload has the team entry but `startXI` is
    empty (rare; some providers return scheduled XI before kickoff).
  * No row at all → caller treats as `state="unknown"`.

Fetch ergonomics:

  * Caller decides what fixtures to refresh — daily-tick takes a
    window of (now, now+24h), T-90m loop takes (now, now+2h).
  * Each call costs ≤ 2 api-football requests (resolve + lineups);
    well inside the Pro-tier 7,500/day budget.

Failure modes: any HTTP / parse / shape error is logged and returns
(status="fetch_failed", []). The blurb path treats absent lineup data
as `state="unknown"` and the prompt mandate stays silent on lineups.
No raises ever cross out of this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from desk.data.api_football.cache import (
    APIFootballCache,
    FixtureResolution,
    LineupRow,
)
from desk.data.api_football.client import APIFootballClient, APIFootballError

_LOG = logging.getLogger(__name__)

# api-football kickoff timestamps are quoted as ISO-8601 with the tz
# offset (e.g. "2026-06-12T19:00:00+00:00"). Tolerance window when we
# match a /fixtures result against our kickoff_utc — providers may
# round to the minute and we don't want a 30-second mismatch to drop a
# valid hit.
_KICKOFF_MATCH_TOLERANCE = timedelta(minutes=15)


@dataclass(frozen=True)
class LineupFetchOutcome:
    """Per-fixture result of one refresh call.

    `home_lineup` / `away_lineup` are populated only on `status="ok"`;
    on any failure they're None and the caller leaves the cache as-is.
    """
    match_id:     str
    status:       str         # "ok" | "no_fixture_id" | "fetch_failed" | "no_lineups"
    home_lineup:  LineupRow | None = None
    away_lineup:  LineupRow | None = None
    error:        str | None = None


def _parse_lineup_entry(
    entry: dict, *, fixture_id: int, fetched_at: datetime,
    announced_at: datetime | None = None,
) -> LineupRow | None:
    """Convert one api-football lineup entry to a LineupRow.

    Payload shape (api-football v3):
      {
        "team":      {"id": 33, "name": "...", "logo": "..."},
        "coach":     {"id": ..., "name": "...", "photo": "..."},
        "formation": "4-3-3",
        "startXI":   [{"player": {"id": ..., "name": "Mbappé", ...}}, ...],
        "substitutes": [...]
      }
    """
    team = entry.get("team") or {}
    try:
        team_id = int(team["id"])
    except (KeyError, TypeError, ValueError):
        return None

    formation = entry.get("formation") or None
    coach = (entry.get("coach") or {}).get("name") or None

    def _names(field: str) -> tuple[str, ...]:
        out: list[str] = []
        for row in (entry.get(field) or []):
            p = (row.get("player") or {})
            name = p.get("name") or ""
            name = name.strip()
            if name:
                out.append(name)
        return tuple(out)

    starters = _names("startXI")
    substitutes = _names("substitutes")

    # Confirmed when the announced XI is 11 names. Anything else is
    # 'predicted' (some providers pre-fill, some don't).
    state = "confirmed" if len(starters) == 11 else "predicted"

    return LineupRow(
        fixture_id=fixture_id,
        api_football_team_id=team_id,
        state=state,
        formation=formation,
        coach_name=coach,
        starters=starters,
        substitutes=substitutes,
        fetched_at=fetched_at.isoformat(),
        announced_at=announced_at.isoformat() if announced_at else None,
    )


async def resolve_fixture_id(
    *,
    match_id: str,
    home_team_id: int,
    away_team_id: int,
    kickoff_utc: datetime,
    season: int,
    client: APIFootballClient,
    cache: APIFootballCache,
) -> int | None:
    """Resolve (home, away, kickoff) → api-football fixture_id.

    Cache-then-fetch. On a cache miss, queries
    `/fixtures?team={home_team_id}&season={season}` and finds the entry
    whose kickoff matches our `kickoff_utc` within ±15 min AND whose
    away_team_id matches. Result is cached for future calls.
    """
    cached = cache.fixture_resolution_for(match_id)
    if cached is not None:
        return cached.api_football_fixture_id

    try:
        resp = await client.get("/fixtures", params={
            "team":   str(home_team_id),
            "season": str(season),
        })
    except APIFootballError as e:
        _LOG.warning("resolve_fixture_id %s: /fixtures failed (%s)", match_id, e)
        return None

    target = kickoff_utc.astimezone(timezone.utc)
    for entry in (resp.payload.get("response") or []):
        fx = (entry.get("fixture") or {})
        teams = (entry.get("teams") or {})
        away = (teams.get("away") or {})
        try:
            api_fixture_id = int(fx["id"])
            away_id = int(away["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if away_id != away_team_id:
            continue
        # api-football timestamps: "date": ISO-8601 (UTC).
        date_raw = fx.get("date")
        if not date_raw:
            continue
        try:
            ts = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if abs(ts - target) > _KICKOFF_MATCH_TOLERANCE:
            continue
        # Match. Cache + return.
        cache.upsert_fixture_resolution(
            match_id=match_id,
            api_football_fixture_id=api_fixture_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            kickoff_utc=kickoff_utc,
        )
        return api_fixture_id

    _LOG.debug("resolve_fixture_id %s: no matching fixture in /fixtures response",
               match_id)
    return None


async def fetch_lineups_for_fixture(
    *,
    fixture_id: int,
    client: APIFootballClient,
) -> tuple[str, list[LineupRow]]:
    """Pull /fixtures/lineups?fixture=X. Returns (status, rows).
    Status is "ok" on success, "fetch_failed" on transport/auth/quota.
    "no_lineups" when the endpoint returned an empty `response`.
    """
    try:
        resp = await client.get("/fixtures/lineups", params={
            "fixture": str(fixture_id),
        })
    except APIFootballError as e:
        return (f"{e.kind}", [])

    raw = resp.payload.get("response") or []
    if not raw:
        return ("no_lineups", [])

    now = datetime.now(tz=timezone.utc)
    rows: list[LineupRow] = []
    for entry in raw:
        row = _parse_lineup_entry(entry, fixture_id=fixture_id, fetched_at=now)
        if row is not None:
            rows.append(row)
    if not rows:
        return ("no_lineups", [])
    return ("ok", rows)


async def refresh_lineup_for_match(
    *,
    match_id: str,
    home_iso3: str,
    away_iso3: str,
    kickoff_utc: datetime,
    season: int,
    client: APIFootballClient,
    cache: APIFootballCache,
) -> LineupFetchOutcome:
    """Top-level orchestrator: resolve fixture_id (cached or via
    /fixtures) and pull /fixtures/lineups. Splits result into home /
    away rows + upserts both. Never raises."""
    home_team_id = cache.team_id_for_iso3(home_iso3)
    away_team_id = cache.team_id_for_iso3(away_iso3)
    if home_team_id is None or away_team_id is None:
        _LOG.debug(
            "refresh_lineup_for_match %s: team_resolution missing "
            "(home=%s/%s away=%s/%s)",
            match_id, home_iso3, home_team_id, away_iso3, away_team_id,
        )
        return LineupFetchOutcome(
            match_id=match_id, status="no_team_id",
            error="team_resolution row missing",
        )

    fixture_id = await resolve_fixture_id(
        match_id=match_id, home_team_id=home_team_id,
        away_team_id=away_team_id, kickoff_utc=kickoff_utc,
        season=season, client=client, cache=cache,
    )
    if fixture_id is None:
        return LineupFetchOutcome(match_id=match_id, status="no_fixture_id")

    status, rows = await fetch_lineups_for_fixture(
        fixture_id=fixture_id, client=client,
    )
    if status != "ok":
        return LineupFetchOutcome(match_id=match_id, status=status)

    home_lineup = next(
        (r for r in rows if r.api_football_team_id == home_team_id), None,
    )
    away_lineup = next(
        (r for r in rows if r.api_football_team_id == away_team_id), None,
    )
    for row in rows:
        cache.upsert_lineup(row)
    return LineupFetchOutcome(
        match_id=match_id, status="ok",
        home_lineup=home_lineup, away_lineup=away_lineup,
    )
