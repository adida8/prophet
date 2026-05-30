"""Walk priced fixtures inside a kickoff window → resolve api-football
fixture_id (via fixture_resolution cache) → fetch /fixtures/lineups
per fixture → upsert per (fixture_id, team_id).

Mirrors `injuries_refresh.py` shape — auth-abort discipline, per-fixture
failure isolation, same write surface to the api-football sqlite.

Driven by:
  * the daily refresh tick (`desk fetch-lineups --window-hours 24`)
  * the T-90m polling loop (`desk fetch-lineups --window-hours 2`)

Both consume the same `desk` priced-fixture pool, so the orchestrator
doesn't need to learn match-id format — it just takes a list of
`(match_id, home_iso3, away_iso3, kickoff_utc)` tuples.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballClient, APIFootballError
from desk.data.api_football.lineups import (
    LineupFetchOutcome, refresh_lineup_for_match,
)

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class LineupRefreshTarget:
    """One fixture to refresh lineups for. Shape kept tight so the
    runner / loop can build it from a `FixtureRef` without dragging the
    full sport API surface across the boundary."""
    match_id:    str
    home_iso3:   str
    away_iso3:   str
    kickoff_utc: datetime


async def refresh_lineups_for_targets(
    targets: list[LineupRefreshTarget],
    *,
    season: int,
    client: APIFootballClient,
    cache:  APIFootballCache,
) -> list[LineupFetchOutcome]:
    """Refresh lineups for every target. Per-fixture failures are
    captured; an auth failure aborts the rest of the batch (mirrors the
    injuries refresh path)."""
    outcomes: list[LineupFetchOutcome] = []
    for tgt in targets:
        try:
            outcome = await refresh_lineup_for_match(
                match_id=tgt.match_id,
                home_iso3=tgt.home_iso3.lower(),
                away_iso3=tgt.away_iso3.lower(),
                kickoff_utc=tgt.kickoff_utc,
                season=season, client=client, cache=cache,
            )
        except APIFootballError as e:
            outcome = LineupFetchOutcome(
                match_id=tgt.match_id, status="error",
                error=f"{e.kind}: {e}",
            )
        outcomes.append(outcome)
        if outcome.error and outcome.error.lower().startswith("auth"):
            _LOG.error(
                "api-football auth failed on %s — aborting lineup refresh: %s",
                tgt.match_id, outcome.error,
            )
            return outcomes
    return outcomes


def fixtures_in_window(
    targets: list[LineupRefreshTarget],
    *,
    now: datetime | None = None,
    window_hours: float = 24.0,
) -> list[LineupRefreshTarget]:
    """Filter targets to those with kickoff inside [now, now+window].

    Past-kickoff fixtures are excluded — lineup data for a finished
    match isn't useful to the next pre-match publish.
    """
    now = now or datetime.now(tz=timezone.utc)
    upper = now + timedelta(hours=window_hours)
    out: list[LineupRefreshTarget] = []
    for t in targets:
        ko = t.kickoff_utc
        # Naive timestamps assumed to be UTC (matches FixtureRef shape).
        if ko.tzinfo is None:
            ko = ko.replace(tzinfo=timezone.utc)
        if now <= ko <= upper:
            out.append(t)
    return out
