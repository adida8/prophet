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
from desk.ops.report import IngestStats, SourceFreshness, SourceStatus
from desk.publish.contract import Copy, Verdict
from desk.sport import FixtureRef, MarketSide
from desk.sports.football.features_builder import build_features
from desk.sports.football.fixtures import (
    MARKET_OUTCOMES_3WAY,
    list_priced_football_fixtures,
)
from desk.sports.football.model import compute as compute_model
from desk.sports.football.priced import list_priced_fixtures_with_stats
from desk.verdict.compare import MarketSnapshot
from desk.verdict.decide import DecisionMeta, decide as decide_verdict

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

    def __init__(self) -> None:
        self._last_stats: IngestStats | None = None
        self._last_decisions: list[DecisionMeta] = []

    def market_outcomes(self) -> tuple[MarketSide, ...]:
        return MARKET_OUTCOMES_3WAY

    def list_fixtures(self) -> Iterable[FixtureRef]:
        return _run_async(list_priced_football_fixtures())

    def list_priced_fixtures(self) -> list[tuple[FixtureRef, MarketSnapshot]]:
        pairs, stats = _run_async(list_priced_fixtures_with_stats())
        # Reset the per-run decision log — the runner will populate it
        # by calling decide_and_explain for each fixture in `pairs`.
        # The Elo seed source row is *not* added here: it depends on the
        # decisions yet to be made (count of fixtures on stub), so the
        # runner sources it via `last_model_sources()` after the loop.
        self._last_stats = IngestStats(
            raw_events=stats.raw_events,
            after_filter=stats.after_filter,
            priced=stats.priced,
            kalshi_hits=stats.kalshi_hits,
            filtered_note=stats.filtered_note,
            priced_note=stats.priced_note,
            sources=list(stats.sources) + [
                SourceStatus(
                    id="wc26_venues",
                    status=SourceFreshness.STATIC,
                    last_ok=None,
                    detail="16 venues",
                ),
            ],
        )
        self._last_decisions = []
        return pairs

    def last_ingest_stats(self) -> IngestStats | None:
        """Stats from the most recent `list_priced_fixtures()` call.

        Read by the runner to build the ops `RunReport`. Returns `None`
        when called before any ingest has happened — the runner records
        an empty funnel in that case.
        """
        return self._last_stats

    # ── Model + verdict (PR 4) ──────────────────────────────────────

    def decide(
        self,
        fx: FixtureRef,
        snapshot: MarketSnapshot,
    ) -> Verdict:
        verdict, _copy, _meta = self.decide_and_explain(fx, snapshot)
        return verdict

    def decide_and_explain(
        self,
        fx: FixtureRef,
        snapshot: MarketSnapshot,
    ) -> tuple[Verdict, Copy, DecisionMeta]:
        """Compute the verdict, the editorial copy, and the decision meta
        in one pass.

        Runs the model once and reuses its output for both branches.
        PR 5 will swap the templated copy for Haiku-generated prose.

        `DecisionMeta` is internal — the runner aggregates it for the
        ops `RunReport` (forced-Pass reasons + Elo provenance). It
        never appears in the published `MatchOutput` contract.
        """
        features = build_features(fx)
        out = compute_model(features)
        market_url = _market_url_for_fixture(fx)
        verdict, meta = decide_verdict(
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
        self._last_decisions.append(meta)

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
        return verdict, copy, meta

    def last_decisions(self) -> list[DecisionMeta]:
        """Decision metas collected during this run's decide_and_explain
        calls. The runner uses these to aggregate forced-Pass counts.
        """
        return list(self._last_decisions)

    def last_model_sources(self) -> list[SourceStatus]:
        """Model-derived source rows for the ops dashboard.

        Computed from `_last_decisions` rather than `_last_stats` because
        the elo_seed status depends on how many fixtures wound up on the
        stub prior — information that only exists post-decision. Stays
        `frozen` until live Elo ingest lands (see
        THE_DESK_DATA_LAYER_SPEC.md §1b); the *count* in the detail tells
        the operator how load-bearing the migration is right now.
        """
        n = len(self._last_decisions)
        stub_n = sum(
            1 for d in self._last_decisions
            if d.elo_sources and "stub" in d.elo_sources
        )
        detail = f"model prior · {stub_n} of {n} fixtures on stub"
        return [
            SourceStatus(
                id="elo_seed",
                status=SourceFreshness.FROZEN,
                last_ok=None,
                detail=detail,
            ),
        ]
