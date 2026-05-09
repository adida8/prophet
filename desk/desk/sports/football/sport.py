"""FootballSport — wires the football package to the Sport protocol.

PR 4 adds the model + verdict hooks: `list_priced_fixtures` returns
(FixtureRef, MarketSnapshot) pairs, and `decide` produces the contract
Verdict from a model output + a market snapshot.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from desk.publish.contract import Verdict
from desk.sport import FixtureRef, MarketSide
from desk.sports.football.features_builder import build_features
from desk.sports.football.fixtures import (
    MARKET_OUTCOMES_3WAY,
    list_priced_football_fixtures,
)
from desk.sports.football.model import compute as compute_model
from desk.sports.football.priced import list_priced_fixtures_polymarket
from desk.verdict.compare import MarketSnapshot
from desk.verdict.decide import decide as decide_verdict

log = logging.getLogger("desk.sports.football")


def _run_async(coro):
    """Sync wrapper that's safe inside or outside an existing loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError(
                "FootballSport sync wrapper called from inside a running loop; "
                "use the underlying async function directly"
            )
    except RuntimeError:
        pass
    return asyncio.run(coro)


class FootballSport:
    code:       str = "football"
    short_code: str = "fb"
    label:      str = "Football"

    def market_outcomes(self) -> tuple[MarketSide, ...]:
        return MARKET_OUTCOMES_3WAY

    def list_fixtures(self) -> Iterable[FixtureRef]:
        return _run_async(list_priced_football_fixtures())

    def list_priced_fixtures(self) -> list[tuple[FixtureRef, MarketSnapshot]]:
        return _run_async(list_priced_fixtures_polymarket())

    # ── Model + verdict (PR 4) ──────────────────────────────────────

    def decide(
        self,
        fx: FixtureRef,
        snapshot: MarketSnapshot,
    ) -> Verdict:
        features = build_features(fx)
        out = compute_model(features)
        return decide_verdict(
            model_p={"a": out.p_a, "draw": out.p_draw, "b": out.p_b},
            market=snapshot,
            sides=MARKET_OUTCOMES_3WAY,
            team_a=fx.team_a,
            team_b=fx.team_b,
            elo_sources=(out.team_a_elo_source, out.team_b_elo_source),  # type: ignore[arg-type]
            match_id=fx.match_id,
        )
