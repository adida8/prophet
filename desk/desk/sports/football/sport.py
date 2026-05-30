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
import os
from typing import Iterable

from desk.explainer import build_copy
from desk.ops.report import IngestStats, SourceFreshness, SourceStatus
from desk.publish.contract import (
    Copy,
    HardSignalAdjustment as ContractHardSignalAdjustment,
    MarketPriceRow,
    MarketSource,
    Verdict,
)
from desk.publish.market_prices import (
    build_consensus_fair,
    build_market_prices,
)
from desk.sport import FixtureRef, MarketSide
from desk.sports.football.features_builder import build_features
from desk.sports.football.fixtures import (
    MARKET_OUTCOMES_3WAY,
    list_priced_football_fixtures,
)
from desk.sports.football.hard_signals import (
    HardSignalAdjustment,
    apply_hard_signals,
)
from desk.sports.football.market_links import (
    build_market_sources,
    market_url_for_fixture as _market_url_for_fixture,
)
from desk.sports.football.model import FootballFeatures, compute as compute_model
from desk.sports.football.priced import list_priced_fixtures_with_stats
from desk.sports.football.signals_glue import tags_for as _football_signals_tags
from desk.sports.football.team_news import build_team_news, iso3_for_team
from desk.verdict.compare import MarketSnapshot
from desk.verdict.decide import DecisionMeta, decide as decide_verdict

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

    def __init__(self) -> None:
        self._last_stats: IngestStats | None = None
        self._last_decisions: list[DecisionMeta] = []
        # Hard-signal adjustments applied in the most recent run. The
        # runner reads these for ops telemetry; PR 5's explainer can
        # cite them in copy. None when no adjustments — keep distinct
        # from "no signals applied" (= []) vs "this is a stale list".
        self._last_hard_signal_adjustments: list[HardSignalAdjustment] = []
        # Forward-validation side channel — Phase B.1 Shadow. For each
        # fixture in the most recent run, holds (published_output,
        # shadow_output) where published_output is the model run with
        # config.FORM_RANK_RESIDUAL_ENABLED's actual value, and
        # shadow_output is the same features run with the flag forced
        # ON. The runner reads this dict to dual-log into the
        # forward_validation sqlite. Empty dict on fresh init.
        self._last_model_outputs: dict[str, tuple] = {}
        # Stash the features per fixture too — useful for the
        # forward-validation feature_set payload (Brier comparison
        # at scoring time needs to know which features were active).
        self._last_features: dict[str, FootballFeatures] = {}

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
        self._last_hard_signal_adjustments = []
        self._last_model_outputs = {}
        self._last_features = {}
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
        verdict, *_ = self.decide_and_explain(fx, snapshot)
        return verdict

    def decide_and_explain(
        self,
        fx: FixtureRef,
        snapshot: MarketSnapshot,
        *,
        signals_runtime=None,
        api_football_runtime=None,
        elo_runtime=None,
    ) -> tuple[
        Verdict,
        Copy,
        DecisionMeta,
        list[ContractHardSignalAdjustment],
        list[MarketSource],
        list[MarketPriceRow],
        dict | None,
    ]:
        """Compute the verdict, the editorial copy, the decision meta,
        the per-match hard-signal audit list, and the outbound
        market-source links in one pass.

        Runs the model once and reuses its output for both branches.
        PR 5 will swap the templated copy for Haiku-generated prose.

        When `signals_runtime` is provided AND the fixture is inside the
        late-binding window, news-signal injuries / suspensions nudge
        each team's Elo before the model runs (bounded, per news-
        signals spec §9). When omitted or outside the window, the path
        is a no-op — the model sees the seed Elo as before.

        `DecisionMeta` is internal — the runner aggregates it for the
        ops `RunReport` (forced-Pass reasons + Elo provenance). It
        never appears in the published `MatchOutput` contract.

        The 4th element is the per-fixture hard-signal audit, converted
        to the public `HardSignalAdjustment` contract type. The runner
        threads it onto `MatchOutput.hard_signal_adjustments` so the
        published JSON carries enough to answer 'did this signal change
        the verdict?'. Empty list when no adjustments fired.

        The 5th element is the outbound `MarketSource` list — every
        venue we link a trade CTA for, each with its deep link, whether
        the Pick rode on it, and which sides it priced. The runner
        threads it onto `MatchOutput.market_sources`. See
        `desk/sports/football/market_links.py`.
        """
        features = build_features(
            fx,
            form_source=api_football_runtime,
            elo_source=elo_runtime,
        )
        hard_adjustments: list[HardSignalAdjustment] = []
        signal_pairs: list = []
        if signals_runtime is not None:
            try:
                signal_pairs = list(signals_runtime.hard_signals_for(fx))
            except Exception as e:  # noqa: BLE001 — never block the model on signals
                log.warning("hard-signal lookup failed for %s: %s", fx.match_id, e)
                signal_pairs = []
            if signal_pairs:
                features, hard_adjustments = apply_hard_signals(
                    features, fx=fx, signals=signal_pairs,
                )
                if hard_adjustments:
                    log.info(
                        "hard signals: %s: %d adjustment(s); a=%.1f b=%.1f Elo",
                        fx.match_id, len(hard_adjustments),
                        sum(a.delta_elo for a in hard_adjustments if a.side == "a"),
                        sum(a.delta_elo for a in hard_adjustments if a.side == "b"),
                    )
        self._last_hard_signal_adjustments.extend(hard_adjustments)

        # ── Team news (Slice A) — build per-side payloads for the blurb
        # writer. Pulls api-football injury rows from the runtime cache
        # (when present) + filters the hard-signal pool by team. Failures
        # degrade silently to TeamNews(materiality="none"); the blurb
        # path treats absent data the same as "no info to share".
        team_a_iso3 = iso3_for_team(fx.team_a)
        team_b_iso3 = iso3_for_team(fx.team_b)
        a_injuries: list = []
        b_injuries: list = []
        a_penalty: float | None = None
        b_penalty: float | None = None
        a_lineup_row = None
        b_lineup_row = None
        a_cards: list = []
        b_cards: list = []
        # Q2 squad-paragraph: at-risk-cards threading is gated. Default
        # is on once the data path exists, but the operator can disable
        # the surfacing while at-risk derivations are being eyeballed.
        cards_enabled = os.environ.get("DESK_CARD_AT_RISK", "1") != "0"
        if api_football_runtime is not None:
            try:
                if team_a_iso3:
                    a_injuries = list(api_football_runtime.injuries_for_iso3(team_a_iso3))
                    a_penalty = api_football_runtime.injury_penalty_for_iso3(team_a_iso3)
                    a_lineup_row = api_football_runtime.lineup_for_match_iso3(
                        match_id=fx.match_id, iso3=team_a_iso3,
                    )
                    if cards_enabled:
                        a_cards = list(api_football_runtime.cards_for_iso3(
                            team_a_iso3, competition=fx.competition_code,
                        ))
                if team_b_iso3:
                    b_injuries = list(api_football_runtime.injuries_for_iso3(team_b_iso3))
                    b_penalty = api_football_runtime.injury_penalty_for_iso3(team_b_iso3)
                    b_lineup_row = api_football_runtime.lineup_for_match_iso3(
                        match_id=fx.match_id, iso3=team_b_iso3,
                    )
                    if cards_enabled:
                        b_cards = list(api_football_runtime.cards_for_iso3(
                            team_b_iso3, competition=fx.competition_code,
                        ))
            except Exception as e:  # noqa: BLE001 — never block prose on team-news lookup
                log.warning("team-news lookup failed for %s: %s", fx.match_id, e)
        try:
            team_a_news = build_team_news(
                team_name=fx.team_a, iso3=team_a_iso3,
                injury_rows=a_injuries, signals=signal_pairs,
                elo_penalty=a_penalty, lineup_row=a_lineup_row,
                card_rows=a_cards,
            )
            team_b_news = build_team_news(
                team_name=fx.team_b, iso3=team_b_iso3,
                injury_rows=b_injuries, signals=signal_pairs,
                elo_penalty=b_penalty, lineup_row=b_lineup_row,
                card_rows=b_cards,
            )
        except Exception as e:  # noqa: BLE001 — builder shouldn't raise; belt-and-braces
            log.warning("team-news builder failed for %s: %s", fx.match_id, e)
            team_a_news = team_b_news = None

        # Editorial citations covering this fixture — used by the
        # templated explainer to append a press-chorus sentence to the
        # blurb when ≥ 2 outlets carry it, and ridden onto the published
        # Copy unchanged. Failures degrade silently to no citations; the
        # blurb body still ships.
        editorial_cites: list = []
        if signals_runtime is not None:
            try:
                editorial_cites = list(signals_runtime.editorial_citations_for(fx))
            except Exception as e:  # noqa: BLE001 — never block prose on signals
                log.warning("editorial citations lookup failed for %s: %s",
                            fx.match_id, e)

        out = compute_model(features)

        # Forward-validation Shadow path — produce a second prediction
        # with B.1 form residual AND B.3 injury penalty forced ON.
        # Captures the combined "all-hooks-on" Brier alongside the
        # published path so the §1.4 gate can score either lever.
        has_form    = (features.team_a_form_delta is not None
                       or features.team_b_form_delta is not None)
        has_injury  = (features.team_a_injury_elo_penalty is not None
                       or features.team_b_injury_elo_penalty is not None)
        if has_form or has_injury:
            shadow_out = compute_model(
                features,
                force_residual=True if has_form else None,
                force_injury_penalty=True if has_injury else None,
            )
        else:
            shadow_out = out
        self._last_model_outputs[fx.match_id] = (out, shadow_out)
        self._last_features[fx.match_id] = features

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

        # Cross-venue "best place to act" — surfaces in the picked
        # driver line as "Cheapest way in on France is William Hill
        # at an effective 60%." (ADR 0004). Only fires when:
        #   - The verdict is a Pick.
        #   - The DESK_CROSS_VENUE_EDGE flag is on (config-derived).
        #   - The cheapest-true-price venue differs from the verdict's
        #     headline market_venue (no information being added
        #     otherwise).
        best_venue_label: str | None = None
        best_venue_true_price: float | None = None
        cross_enabled = bool(getattr(__import__("desk.config",
            fromlist=["CROSS_VENUE_EDGE_ENABLED"]),
            "CROSS_VENUE_EDGE_ENABLED", False))
        if cross_enabled and verdict.state in ("pick",):
            from desk.data.oddsapi.venues import VENUE_DISPLAY_NAMES
            picked_side = None
            side_to_team = {"a": fx.team_a, "b": fx.team_b, "draw": "draw"}
            for s, name in side_to_team.items():
                if verdict.side == name:
                    picked_side = s
                    break
            if picked_side is not None:
                bv = snapshot.best_for_true_price(picked_side)
                if bv is not None and bv.venue != (verdict.market_venue or ""):
                    best_venue_label = VENUE_DISPLAY_NAMES.get(
                        bv.venue, bv.venue.title())
                    best_venue_true_price = bv.true_price or bv.implied_p

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
            "editorial_citations": editorial_cites,
            "team_a_news":        team_a_news,
            "team_b_news":        team_b_news,
            "best_venue_label":      best_venue_label,
            "best_venue_true_price": best_venue_true_price,
        })
        # Ride the citation list onto the published Copy. The blurb
        # already saw them inside build_copy; the contract surfaces them
        # as a separate structured list for the front-of-house.
        if editorial_cites:
            copy = copy.model_copy(update={"editorial_citations": editorial_cites})

        # Convert the internal dataclass audit log to the public contract
        # shape. The pydantic model carries the same fields plus the
        # source's display name + the signal's published_at, which we
        # carry through `apply_hard_signals` so the renderer can show
        # "Guardian · 9 Jun" without re-resolving the source registry.
        contract_adjustments = [
            ContractHardSignalAdjustment(
                side=a.side,
                team=a.team,
                delta_elo=a.delta_elo,
                capped=a.capped,
                reason=a.reason,
                signal_type=a.signal_type,
                signal_url=a.signal_url,
                source_id=a.source_id,
                source_name=a.source_name,
                published_at=a.published_at,
            )
            for a in hard_adjustments
        ]

        # Outbound venue links — every CTA venue, deep-linked, with the
        # picked flag + which sides each priced into the calculation.
        market_sources = build_market_sources(fx, snapshot, verdict)

        # Cross-venue contract block (ADR 0004). The publisher emits
        # [] / None on legacy snapshots (no true_price on any row),
        # so flag-off behaviour stays byte-identical to today.
        cross_enabled = bool(getattr(__import__("desk.config",
            fromlist=["CROSS_VENUE_EDGE_ENABLED"]),
            "CROSS_VENUE_EDGE_ENABLED", False))
        if cross_enabled:
            market_prices = build_market_prices(snapshot)
            consensus     = build_consensus_fair(snapshot)
        else:
            market_prices = []
            consensus     = None

        return (
            verdict, copy, meta, contract_adjustments, market_sources,
            market_prices, consensus,
        )

    # ── News-signals glue ───────────────────────────────────────────

    def signals_tags_for(self, fx: FixtureRef) -> frozenset[str]:
        """Tag set the news-signals resolver uses to pick covering
        outlets. Sport-agnostic resolver, football-specific tags."""
        return _football_signals_tags(fx)

    def last_hard_signal_adjustments(self) -> list[HardSignalAdjustment]:
        """Hard-signal adjustments collected during the last run's
        decide_and_explain calls. Read by the runner for ops telemetry
        and by PR 5's explainer for attributed prose."""
        return list(self._last_hard_signal_adjustments)

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
