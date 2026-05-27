"""Resolve canonical ISO3 → api-football numeric team_id, persist.

The api-football `/teams?search={name}` endpoint returns a list of
matching teams (clubs + nationals). For national sides we filter to
`team.national == True` and take the first match — there's only ever
one national side per country, so the first national hit is correct.

Resolution is idempotent: once cached, subsequent calls hit sqlite, not
the wire. Re-resolution is explicit (`force=True`) for the rare case of
api-football renaming a team in their backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballClient, APIFootballError
from desk.data.api_football.wc26_registry import search_query_for_iso3

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolutionOutcome:
    iso3:           str
    status:         str           # "cached", "resolved", "unknown_iso3", "no_match", "error"
    team_id:        int | None
    error:          str | None = None


async def resolve_team_id(
    iso3: str,
    *,
    client: APIFootballClient,
    cache:  APIFootballCache,
    force:  bool = False,
) -> ResolutionOutcome:
    iso3 = iso3.lower()

    if not force:
        cached = cache.team_id_for_iso3(iso3)
        if cached is not None:
            return ResolutionOutcome(iso3, "cached", cached)

    query = search_query_for_iso3(iso3)
    if query is None:
        return ResolutionOutcome(iso3, "unknown_iso3", None,
                                 error=f"no WC26 registry entry for {iso3}")

    try:
        resp = await client.get("/teams", params={"search": query})
    except APIFootballError as e:
        return ResolutionOutcome(iso3, "error", None, error=f"{e.kind}: {e}")

    items = resp.payload.get("response") or []
    # Filter to the national side. api-football returns each match as
    # `{"team": {...}, "venue": {...}}`.
    national = [
        it for it in items
        if isinstance(it.get("team"), dict)
        and it["team"].get("national") is True
    ]
    if not national:
        return ResolutionOutcome(
            iso3, "no_match", None,
            error=f"no national-side match for query {query!r}",
        )

    team = national[0]["team"]
    team_id = int(team["id"])
    cache.upsert_team_resolution(
        iso3, team_id,
        source_label=f"api-football:/teams?search={query}",
    )
    _LOG.info("resolved %s → api-football team_id %d (%s)",
              iso3, team_id, team.get("name"))
    return ResolutionOutcome(iso3, "resolved", team_id)
