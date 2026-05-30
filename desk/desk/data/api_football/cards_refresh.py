"""Walk WC26 registry → resolve team_ids → fetch card accumulation →
reconcile with injuries cache → persist per-team rows.

Mirrors the injuries refresh path. Same auth-abort discipline, same
per-team failure isolation. Off the hot path: writes only to the
sqlite cache. Q5 of the squad-paragraph spec.

For each team we:
  1. Resolve canonical ISO3 → api-football `team_id` (cached).
  2. Pull `/players?team=&season=&league=` for the competition's
     league id (WC26 = 1).
  3. Read the team's current `Suspended` injuries from the cache so
     the at-risk derivation reconciles them out.
  4. Compute at-risk per spec §Q1 + write the full squad's card
     accumulation rows.

The /players endpoint reads each team's full WC26 squad in one call
(~26 players per national side). Worst case across the 48-team
registry: 48 calls per refresh — well inside the api-football Pro
cap (7,500 / day).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.cards import (
    WC26_LEAGUE_ID, card_data_to_rows, fetch_for_team,
)
from desk.data.api_football.client import APIFootballClient, APIFootballError
from desk.data.api_football.teams import resolve_team_id
from desk.data.api_football.wc26_registry import WC26_NATIONAL_REGISTRY

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class CardRefreshOutcome:
    iso3:        str
    status:      str    # "ok" | "no_team_id" | "fetch_failed" | "error"
    team_id:     int | None = None
    competition: str = "wc26"
    n_rows:      int = 0
    n_at_risk:   int = 0
    error:       str | None = None


def _suspended_player_ids(
    cache: APIFootballCache, team_id: int,
) -> set[int]:
    """Set of api-football player_ids the injuries cache currently
    flags as `Suspended` for this team. The cards reconcile drops
    these from the at-risk set (per spec §Q1: suspension wins)."""
    out: set[int] = set()
    for row in cache.injuries_for_team(team_id):
        if row.type == "Suspended":
            out.add(int(row.player_id))
    return out


async def refresh_cards_one(
    iso3: str,
    *,
    season: int,
    competition: str,
    league_id: int,
    client: APIFootballClient,
    cache: APIFootballCache,
) -> CardRefreshOutcome:
    iso3 = iso3.lower()
    resolution = await resolve_team_id(iso3, client=client, cache=cache)
    if resolution.team_id is None:
        return CardRefreshOutcome(
            iso3=iso3, status="no_team_id",
            competition=competition, error=resolution.error,
        )
    team_id = resolution.team_id

    status, items = await fetch_for_team(
        team_id, season=season, league_id=league_id, client=client,
    )
    if status != "ok":
        return CardRefreshOutcome(
            iso3=iso3, status="fetch_failed",
            competition=competition, team_id=team_id, error=status,
        )

    suspended = _suspended_player_ids(cache, team_id)
    rows = card_data_to_rows(
        items, competition=competition,
        suspended_player_ids=suspended,
    )
    cache.replace_cards_for_team(team_id, competition, rows)
    cache.mark_fetch(
        f"/players?team={team_id}&season={season}&league={league_id}",
        "ok",
    )
    n_at_risk = sum(1 for r in rows if r.is_at_risk)
    return CardRefreshOutcome(
        iso3=iso3, status="ok",
        team_id=team_id, competition=competition,
        n_rows=len(rows), n_at_risk=n_at_risk,
    )


async def refresh_cards_all(
    *,
    season: int,
    client: APIFootballClient,
    cache: APIFootballCache,
    competition: str = "wc26",
    league_id: int = WC26_LEAGUE_ID,
    iso3s: list[str] | None = None,
) -> list[CardRefreshOutcome]:
    targets = iso3s or list(WC26_NATIONAL_REGISTRY)
    outcomes: list[CardRefreshOutcome] = []
    for iso3 in targets:
        try:
            outcome = await refresh_cards_one(
                iso3, season=season,
                competition=competition, league_id=league_id,
                client=client, cache=cache,
            )
        except APIFootballError as e:
            outcome = CardRefreshOutcome(
                iso3=iso3, status="error",
                competition=competition, error=f"{e.kind}: {e}",
            )
        outcomes.append(outcome)
        if outcome.error and outcome.error.lower().startswith("auth"):
            _LOG.error(
                "api-football auth failed on %s — aborting card refresh: %s",
                iso3, outcome.error,
            )
            return outcomes
    return outcomes
