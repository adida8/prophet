"""Pick / Pass / Avoid decision logic.

Given a model output and a market snapshot, compute edges per side
and apply the threshold ladder from spec §4 PR 4:

    Pick   any side: model_p − best_market_p ≥ pick_pp
    Avoid  every side: model_p − best_market_p ≤ avoid_pp
    Pass   every side: |model_p − best_market_p| < pass_pp
    else   Pass

Pick wins ties when more than one branch could fire — it's the only
state with a CTA, so we take it whenever it's available.

Sanity gates (PR 4.5):
- Liquidity filter — extreme implied probabilities (≤ 2% or ≥ 98%) on
  any side force Pass (the venue is signalling "no opinion").
- Stub-Elo gate — when either team's Elo came from the v1 fixed-default
  stub rather than a real source, we force Pass. Removed in v1.1 when
  ClubElo / Wikipedia ingest is wired live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Mapping, Optional

from desk.publish.contract import Verdict, VerdictState
from desk.verdict.compare import MarketSnapshot, Side, VenuePrice
from desk.verdict.liquidity import LiquidityRules, is_liquid
from desk.verdict.thresholds import Thresholds, current as _current_thresholds

log = logging.getLogger("desk.verdict.decide")

EloSource = Literal["wiki", "clubelo", "stub"]
ForcedPassReason = Literal["illiquid", "stub_elo"]


@dataclass(frozen=True)
class DecisionMeta:
    """Internal-only metadata about how a verdict was reached.

    Sister return value of `decide()`. Carries the *why* behind a forced
    Pass and the Elo provenance for both teams. Never written to the
    public `MatchOutput` contract — surfaced only to the ops dashboard
    via the runner's `RunReport`.

    `forced_pass_reason` is set only when a sanity gate (PR 4.5)
    overrode the threshold ladder. A natural Pass from threshold logic
    leaves it `None`.

    `elo_sources` mirrors the input `(team_a_source, team_b_source)`
    tuple when supplied, or `None` when the caller didn't pass one
    (e.g. backtest scenarios where provenance isn't tracked).
    """
    forced_pass_reason: Optional[ForcedPassReason] = None
    elo_sources:        Optional[tuple[EloSource, EloSource]] = None


@dataclass(frozen=True)
class _Edges:
    """Per-side edge, in pp."""
    by_side:        dict[Side, float]
    best_venues:    dict[Side, VenuePrice]


def _compute_edges(
    model_p: Mapping[Side, float],
    market: MarketSnapshot,
    sides: tuple[Side, ...],
    *,
    cross_venue_edge: bool = False,
) -> _Edges | None:
    """Per-side best venue + edge in pp.

    When `cross_venue_edge` is True AND the snapshot's rows carry
    `true_price`, edge is computed as `model_p − true_price` (the
    actual cost of acting); otherwise it's the legacy
    `model_p − implied_p`. Mixed snapshots (some rows have true_price,
    some don't) fall back to legacy semantics inside
    `best_for_true_price` — see desk/verdict/compare.py.
    """
    edges_pp:    dict[Side, float]      = {}
    best_venues: dict[Side, VenuePrice] = {}
    for s in sides:
        bv = (
            market.best_for_true_price(s) if cross_venue_edge
            else market.best_for(s)
        )
        if bv is None:
            return None
        # Edge runs against `true_price` whenever it's populated on
        # the chosen venue; otherwise the naive implied stands in.
        cost = bv.true_price if (cross_venue_edge and bv.true_price is not None) else bv.implied_p
        edges_pp[s]    = (model_p[s] - cost) * 100.0
        best_venues[s] = bv
    return _Edges(by_side=edges_pp, best_venues=best_venues)


def _to_american_odds(p: float) -> str:
    """Standard US-format odds string from an implied probability."""
    if p <= 0.0:   return "+9999"
    if p >= 1.0:   return "-9999"
    if p < 0.5:
        odds = (1.0 - p) / p * 100.0
        return f"+{int(round(odds))}"
    if p == 0.5:
        return "+100"
    odds = -p / (1.0 - p) * 100.0
    return f"{int(round(odds))}"


def _name_for_side(side: Side, *, team_a: str, team_b: str) -> str:
    return {"a": team_a, "b": team_b, "draw": "draw"}[side]


def decide(
    *,
    model_p:        Mapping[Side, float],     # {"a": 0.46, "draw": 0.25, "b": 0.29}
    market:         MarketSnapshot,
    sides:          tuple[Side, ...],
    team_a:         str,
    team_b:         str,
    thresholds:     Thresholds | None = None,
    elo_sources:    tuple[EloSource, EloSource] | None = None,  # (a, b) — PR 4.5
    liquidity:      LiquidityRules | None = None,
    match_id:       str | None = None,        # for logs only
    model_p_lower:  Mapping[Side, float] | None = None,         # Phase A.3
    market_url:     str | None = None,        # deep link to venue page (CTA)
    cross_venue_edge: bool | None = None,     # non-US pivot — None = read flag
) -> tuple[Verdict, DecisionMeta]:
    """Apply the Pick / Pass / Avoid ladder.

    Phase A.3 (confidence-band gate): if `model_p_lower` is supplied,
    a Pick fires only when the *lower bound* of the model's probability
    clears the threshold against the market — not just the point
    estimate. Forces the engine to be conservative when the Elo prior
    is uncertain.

    Returns `(verdict, meta)` — see `DecisionMeta`. PR 2 of the ops
    dashboard spec promoted the meta from internal log lines to a
    structured side-channel so the runner can roll up forced-Pass
    counts without parsing logs.
    """
    th = thresholds if thresholds is not None else _current_thresholds()

    # Resolve the cross-venue edge flag. Explicit kwarg wins; otherwise
    # read the env-driven config once per call so tests + the live
    # refresh loop can flip the lever independently.
    if cross_venue_edge is None:
        from desk import config
        cross_venue_edge = bool(config.CROSS_VENUE_EDGE_ENABLED)

    # ── Sanity gate: stub-Elo (PR 4.5) ─────────────────────────────
    # Stub Elo is the v1 fixed-default for unknown clubs. Issuing a
    # confident Pick on top of it is dishonest — the model is just
    # diffing 1500 vs 1500 against whatever the market is doing.
    if elo_sources is not None and "stub" in elo_sources:
        log.debug("forcing Pass: club_elo_stub on %s", match_id or "<unknown>")
        return (
            Verdict(state=VerdictState.PASS, market_url=market_url),
            DecisionMeta(forced_pass_reason="stub_elo", elo_sources=elo_sources),
        )

    # ── Sanity gate: liquidity (PR 4.5) ────────────────────────────
    liq = is_liquid(market, sides, liquidity)
    if not liq.is_liquid:
        log.debug("forcing Pass: %s on %s", liq.reason, match_id or "<unknown>")
        return (
            Verdict(state=VerdictState.PASS, market_url=market_url),
            DecisionMeta(forced_pass_reason="illiquid", elo_sources=elo_sources),
        )

    edges = _compute_edges(
        model_p, market, sides, cross_venue_edge=cross_venue_edge,
    )
    if edges is None:
        # Missing market data on at least one side — default to Pass per spec §9.
        return (
            Verdict(state=VerdictState.PASS, market_url=market_url),
            DecisionMeta(elo_sources=elo_sources),
        )

    # ── Pick ───────────────────────────────────────────────────────
    # Phase A.3: when a lower-bound band is provided, a Pick fires only
    # when the lower bound — not the point estimate — clears the
    # threshold. This is the "honest about uncertainty" gate: shaky Elo
    # produces a wide band, and a wide band fails the lower-bound test.
    if model_p_lower is not None:
        # Lower-bound gate runs against the same cost surface as
        # `_compute_edges` chose — true_price when on + populated,
        # naive implied_p otherwise.
        def _cost(s: Side) -> float:
            bv = edges.best_venues[s]
            if cross_venue_edge and bv.true_price is not None:
                return bv.true_price
            return bv.implied_p

        pick_candidates = [
            (s, edges.by_side[s])
            for s in sides
            if (model_p_lower[s] - _cost(s)) * 100.0 >= th.pick_pp
        ]
    else:
        pick_candidates = [(s, edges.by_side[s]) for s in sides if edges.by_side[s] >= th.pick_pp]

    if pick_candidates:
        side, edge_pp = max(pick_candidates, key=lambda kv: kv[1])
        bv = edges.best_venues[side]
        if market_url is None:
            # A Pick without a CTA destination is unusable. Fall back to
            # Pass rather than violating the contract — better to under-
            # call than to publish a Pick with no link.
            log.warning("forcing Pass: pick on %s but market_url missing", match_id or "<unknown>")
            return (
                Verdict(state=VerdictState.PASS),
                DecisionMeta(elo_sources=elo_sources),
            )
        return (
            Verdict(
                state=VerdictState.PICK,
                side=_name_for_side(side, team_a=team_a, team_b=team_b),
                market_venue=bv.venue,                       # type: ignore[arg-type]
                price=_to_american_odds(bv.implied_p),
                edge_pp=round(edge_pp, 2),
                market_url=market_url,
                model_p=round(model_p[side], 4),
                market_p=round(bv.implied_p, 4),
            ),
            DecisionMeta(elo_sources=elo_sources),
        )

    # ── Avoid ──────────────────────────────────────────────────────
    if all(edges.by_side[s] <= th.avoid_pp for s in sides):
        # PR 4.5 §3.2: populate edge_pp on Avoid with the most-negative
        # edge across all sides — the worst-case "how short is the
        # market on the most overpriced side" signal.
        most_negative = min(edges.by_side[s] for s in sides)
        return (
            Verdict(
                state=VerdictState.AVOID,
                edge_pp=round(most_negative, 2),
                market_url=market_url,
            ),
            DecisionMeta(elo_sources=elo_sources),
        )

    # ── Pass (everyone within ±pass_pp) or default ─────────────────
    return (
        Verdict(state=VerdictState.PASS, market_url=market_url),
        DecisionMeta(elo_sources=elo_sources),
    )
