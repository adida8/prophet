"""FootballSport — wires the football package to the Sport protocol.

PR 4 adds the model + verdict hooks: `list_priced_fixtures` returns
(FixtureRef, MarketSnapshot) pairs, and `decide` produces the contract
Verdict from a model output + a market snapshot.

`decide_and_explain` (PR 4.x) returns both the Verdict and the
templated explainer Copy in one pass. PR 5 swaps the templates for
real Haiku output.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from desk.explainer import build_copy
from desk.publish.contract import Copy, Verdict
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


def _market_url_for_fixture(fx: FixtureRef) -> str | None:
    """Build the venue-side deep link from the source slug.

    Polymarket events resolve at `https://polymarket.com/event/{slug}`,
    where `slug` is e.g. `fifwc-fra-mex-2026-06-12`. We strip the
    optional `-more-markets` suffix Polymarket sometimes appends, then
    front it with the canonical event URL.

    Returns None when we can't construct a clean URL — caller decides
    whether that downgrades a Pick to a Pass (see decide()).
    """
    slug = (fx.source_event_slug or "").strip().lower()
    if not slug:
        return None
    if slug.endswith("-more-markets"):
        slug = slug[: -len("-more-markets")]
    if (fx.source_venue or "").lower() == "polymarket":
        return f"https://polymarket.com/event/{slug}"
    # Kalshi (and future venues) plug in here when their slug + URL
    # pattern is known. Until then we don't fabricate a URL.
    return None


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
        verdict, _copy = self.decide_and_explain(fx, snapshot)
        return verdict

    def decide_and_explain(
        self,
        fx: FixtureRef,
        snapshot: MarketSnapshot,
    ) -> tuple[Verdict, Copy]:
        """Compute the verdict and the editorial copy in one pass.

        Runs the model once and reuses its output for both branches.
        PR 5 will swap the templated copy for Haiku-generated prose.
        """
        features = build_features(fx)
        out = compute_model(features)
        market_url = _market_url_for_fixture(fx)
        verdict = decide_verdict(
            model_p={"a": out.p_a, "draw": out.p_draw, "b": out.p_b},
            model_p_lower={"a": out.p_a_lower, "draw": out.p_draw_lower, "b": out.p_b_lower},
            market=snapshot,
            sides=MARKET_OUTCOMES_3WAY,
            team_a=fx.team_a,
            team_b=fx.team_b,
            elo_sources=(out.team_a_elo_source, out.team_b_elo_source),  # type: ignore[arg-type]
            match_id=fx.match_id,
            market_url=market_url,
        )

        market_p = {
            "a":    snapshot.best_for("a").implied_p    if snapshot.best_for("a")    else 0.0,
            "draw": snapshot.best_for("draw").implied_p if snapshot.best_for("draw") else 0.0,
            "b":    snapshot.best_for("b").implied_p    if snapshot.best_for("b")    else 0.0,
        }
        copy = build_copy({
            "state":         verdict.state if isinstance(verdict.state, str) else verdict.state.value,
            "side":          verdict.side,
            "edge_pp":       verdict.edge_pp,
            "market_venue":  verdict.market_venue,
            "price":         verdict.price,
            "team_a":        fx.team_a,
            "team_b":        fx.team_b,
            "competition":   fx.competition_label,
            "model_p_a":     out.p_a,
            "model_p_draw":  out.p_draw,
            "model_p_b":     out.p_b,
            "market_p_a":    market_p["a"],
            "market_p_draw": market_p["draw"],
            "market_p_b":    market_p["b"],
            "team_a_elo":         features.team_a_elo,
            "team_b_elo":         features.team_b_elo,
            "elo_a_adj":          out.elo_a_adj,
            "elo_b_adj":          out.elo_b_adj,
            "team_a_elo_source":  out.team_a_elo_source,
            "team_b_elo_source":  out.team_b_elo_source,
            "model_p_a_lower":    out.p_a_lower,
            "model_p_a_upper":    out.p_a_upper,
            "model_p_draw_lower": out.p_draw_lower,
            "model_p_draw_upper": out.p_draw_upper,
            "model_p_b_lower":    out.p_b_lower,
            "model_p_b_upper":    out.p_b_upper,
            "venue_city":         fx.venue_city,
            "venue_stadium":      fx.venue_stadium,
            "venue_country":      fx.venue_country,
            "kickoff_utc":        fx.kickoff_utc.isoformat() if fx.kickoff_utc else None,
        })
        return verdict, copy
