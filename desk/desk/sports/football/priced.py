"""Football fixture+price ingest — pairs each `FixtureRef` with the
gamma event's market snapshot, in one HTTP round trip.

The runner consumes (fixture, snapshot) pairs without knowing they
came from the same Polymarket event payload. PR 6's scheduler will
poll this every 60s for the verdict cadence.
"""

from __future__ import annotations

import logging
from typing import Iterable

from desk import config
from desk.ingest.polymarket import PolymarketSoccerEventsSource
from desk.ingest.polymarket_prices import prices_from_polymarket_event
from desk.sport import FixtureRef
from desk.sports.football.fixtures import from_polymarket_event
from desk.verdict.compare import MarketSnapshot

log = logging.getLogger("desk.sports.football.priced")


async def list_priced_fixtures_polymarket() -> list[tuple[FixtureRef, MarketSnapshot]]:
    out: list[tuple[FixtureRef, MarketSnapshot]] = []
    seen: set[str] = set()

    try:
        events = await PolymarketSoccerEventsSource().fetch()
    except Exception as e:                      # noqa: BLE001 — spec §9
        log.warning("polymarket fetch failed: %s", e)
        return out

    allow = config.COMPETITION_ALLOWLIST
    n_filtered = 0
    for ev in events:
        fx = from_polymarket_event(ev)
        if fx is None or fx.match_id in seen:
            continue
        if allow is not None and fx.competition_code not in allow:
            n_filtered += 1
            continue
        seen.add(fx.match_id)
        snap = prices_from_polymarket_event(
            ev,
            match_id=fx.match_id,
            team_a=fx.team_a,
            team_b=fx.team_b,
        )
        out.append((fx, snap))

    if allow is not None:
        log.info(
            "competition allowlist %s — kept %d, filtered %d",
            sorted(allow), len(out), n_filtered,
        )
    return out
