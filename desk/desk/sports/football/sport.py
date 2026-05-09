"""FootballSport — wires the football package to the Sport protocol.

PR 2 only implements `code`, `short_code`, `label`, `market_outcomes`,
and `list_fixtures`. PR 3 / PR 5 fill in model + voice hooks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from desk.sport import FixtureRef, MarketSide
from desk.sports.football.fixtures import (
    MARKET_OUTCOMES_3WAY,
    list_priced_football_fixtures,
)

log = logging.getLogger("desk.sports.football")


class FootballSport:
    code:       str = "football"
    short_code: str = "fb"
    label:      str = "Football"

    def market_outcomes(self) -> tuple[MarketSide, ...]:
        return MARKET_OUTCOMES_3WAY

    def list_fixtures(self) -> Iterable[FixtureRef]:
        """Synchronous wrapper around the async fixture lister.

        PR 6's scheduler will call the async path directly; for `desk run
        --once` and tests, this synchronous form keeps callers simple.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an existing loop; caller should use the async path.
                raise RuntimeError(
                    "FootballSport.list_fixtures() is sync; from async "
                    "code call list_priced_football_fixtures() directly"
                )
        except RuntimeError:
            pass
        return asyncio.run(list_priced_football_fixtures())
