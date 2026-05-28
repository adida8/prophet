"""Walk WC26 registry → resolve team_ids → fetch injuries per team →
compute + persist per-team Elo penalty.

Mirrors the form_delta refresh path (refresh.py) — same auth-abort
discipline, same per-team failure isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from desk.data.api_football.cache import APIFootballCache, InjuryRow
from desk.data.api_football.client import APIFootballClient, APIFootballError
from desk.data.api_football.injuries import fetch_for_team
from desk.data.api_football.injury_penalty import compute_injury_penalty
from desk.data.api_football.teams import resolve_team_id
from desk.data.api_football.wc26_registry import WC26_NATIONAL_REGISTRY

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class InjuryRefreshOutcome:
    iso3:        str
    status:      str    # "ok", "no_team_id", "fetch_failed", "error"
    team_id:     int | None = None
    n_players:   int = 0
    elo_penalty: float = 0.0
    error:       str | None = None


async def refresh_injuries_one(
    iso3: str,
    *,
    season: int,
    client: APIFootballClient,
    cache:  APIFootballCache,
) -> InjuryRefreshOutcome:
    iso3 = iso3.lower()
    resolution = await resolve_team_id(iso3, client=client, cache=cache)
    if resolution.team_id is None:
        return InjuryRefreshOutcome(iso3, "no_team_id", error=resolution.error)
    team_id = resolution.team_id

    status, items = await fetch_for_team(
        team_id, season=season, client=client,
    )
    if status != "ok":
        return InjuryRefreshOutcome(
            iso3, "fetch_failed", team_id=team_id,
            error=status,
        )

    now = datetime.now(tz=timezone.utc)
    rows = [
        InjuryRow(
            api_football_team_id=item.team_id,
            player_id=item.player_id,
            player_name=item.player_name,
            type=item.type, reason=item.reason,
            position=item.position,
            fetched_at=now.isoformat(),
        )
        for item in items
    ]
    cache.replace_injuries_for_team(team_id, rows)
    cache.mark_fetch(f"/injuries?team={team_id}&season={season}", "ok")

    penalty, n_counted = compute_injury_penalty(rows)
    cache.upsert_injury_penalty(
        iso3, penalty, n_counted,
        computed_at=now,
        source_endpoint=f"/injuries?team={team_id}&season={season}",
    )
    return InjuryRefreshOutcome(
        iso3, "ok", team_id=team_id,
        n_players=n_counted, elo_penalty=penalty,
    )


async def refresh_injuries_all(
    *,
    season: int,
    client: APIFootballClient,
    cache:  APIFootballCache,
    iso3s:  list[str] | None = None,
) -> list[InjuryRefreshOutcome]:
    targets = iso3s or list(WC26_NATIONAL_REGISTRY)
    outcomes: list[InjuryRefreshOutcome] = []
    for iso3 in targets:
        try:
            outcome = await refresh_injuries_one(
                iso3, season=season, client=client, cache=cache,
            )
        except APIFootballError as e:
            outcome = InjuryRefreshOutcome(
                iso3, "error", error=f"{e.kind}: {e}",
            )
        outcomes.append(outcome)
        if outcome.error and outcome.error.lower().startswith("auth"):
            _LOG.error(
                "api-football auth failed on %s — aborting injury refresh: %s",
                iso3, outcome.error,
            )
            return outcomes
    return outcomes
