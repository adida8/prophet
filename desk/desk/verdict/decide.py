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
from typing import Literal, Mapping

from desk.publish.contract import Verdict, VerdictState
from desk.verdict.compare import MarketSnapshot, Side, VenuePrice
from desk.verdict.liquidity import LiquidityRules, is_liquid
from desk.verdict.thresholds import Thresholds, current as _current_thresholds

log = logging.getLogger("desk.verdict.decide")

EloSource = Literal["wiki", "clubelo", "stub"]


@dataclass(frozen=True)
class _Edges:
    """Per-side edge, in pp."""
    by_side:        dict[Side, float]
    best_venues:    dict[Side, VenuePrice]


def _compute_edges(model_p: Mapping[Side, float], market: MarketSnapshot, sides: tuple[Side, ...]) -> _Edges | None:
    edges_pp:    dict[Side, float]      = {}
    best_venues: dict[Side, VenuePrice] = {}
    for s in sides:
        bv = market.best_for(s)
        if bv is None:
            return None
        edges_pp[s]    = (model_p[s] - bv.implied_p) * 100.0
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
) -> Verdict:
    """Apply the Pick / Pass / Avoid ladder.

    Phase A.3 (confidence-band gate): if `model_p_lower` is supplied,
    a Pick fires only when the *lower bound* of the model's probability
    clears the threshold against the market — not just the point
    estimate. Forces the engine to be conservative when the Elo prior
    is uncertain.
    """
    th = thresholds if thresholds is not None else _current_thresholds()

    # ── Sanity gate: stub-Elo (PR 4.5) ─────────────────────────────
    # Stub Elo is the v1 fixed-default for unknown clubs. Issuing a
    # confident Pick on top of it is dishonest — the model is just
    # diffing 1500 vs 1500 against whatever the market is doing.
    if elo_sources is not None and "stub" in elo_sources:
        log.debug("forcing Pass: club_elo_stub on %s", match_id or "<unknown>")
        return Verdict(state=VerdictState.PASS)

    # ── Sanity gate: liquidity (PR 4.5) ────────────────────────────
    liq = is_liquid(market, sides, liquidity)
    if not liq.is_liquid:
        log.debug("forcing Pass: %s on %s", liq.reason, match_id or "<unknown>")
        return Verdict(state=VerdictState.PASS)

    edges = _compute_edges(model_p, market, sides)
    if edges is None:
        # Missing market data on at least one side — default to Pass per spec §9.
        return Verdict(state=VerdictState.PASS)

    # ── Pick ───────────────────────────────────────────────────────
    # Phase A.3: when a lower-bound band is provided, a Pick fires only
    # when the lower bound — not the point estimate — clears the
    # threshold. This is the "honest about uncertainty" gate: shaky Elo
    # produces a wide band, and a wide band fails the lower-bound test.
    if model_p_lower is not None:
        pick_candidates = [
            (s, edges.by_side[s])
            for s in sides
            if (model_p_lower[s] - edges.best_venues[s].implied_p) * 100.0 >= th.pick_pp
        ]
    else:
        pick_candidates = [(s, edges.by_side[s]) for s in sides if edges.by_side[s] >= th.pick_pp]

    if pick_candidates:
        side, edge_pp = max(pick_candidates, key=lambda kv: kv[1])
        bv = edges.best_venues[side]
        return Verdict(
            state=VerdictState.PICK,
            side=_name_for_side(side, team_a=team_a, team_b=team_b),
            market_venue=bv.venue,                       # type: ignore[arg-type]
            price=_to_american_odds(bv.implied_p),
            edge_pp=round(edge_pp, 2),
        )

    # ── Avoid ──────────────────────────────────────────────────────
    if all(edges.by_side[s] <= th.avoid_pp for s in sides):
        # PR 4.5 §3.2: populate edge_pp on Avoid with the most-negative
        # edge across all sides — the worst-case "how short is the
        # market on the most overpriced side" signal.
        most_negative = min(edges.by_side[s] for s in sides)
        return Verdict(
            state=VerdictState.AVOID,
            edge_pp=round(most_negative, 2),
        )

    # ── Pass (everyone within ±pass_pp) or default ─────────────────
    return Verdict(state=VerdictState.PASS)
