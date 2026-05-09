"""Pick / Pass / Avoid decision logic.

Given a model output and a market snapshot, compute edges per side
and apply the threshold ladder from spec §4 PR 4:

    Pick   any side: model_p − best_market_p ≥ pick_pp
    Avoid  every side: model_p − best_market_p ≤ avoid_pp
    Pass   every side: |model_p − best_market_p| < pass_pp
    else   Pass

Pick wins ties when more than one branch could fire — it's the only
state with a CTA, so we take it whenever it's available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from desk.publish.contract import Verdict, VerdictState
from desk.verdict.compare import MarketSnapshot, Side, VenuePrice
from desk.verdict.thresholds import Thresholds, current as _current_thresholds


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
) -> Verdict:
    th = thresholds if thresholds is not None else _current_thresholds()

    edges = _compute_edges(model_p, market, sides)
    if edges is None:
        # Missing market data on at least one side — default to Pass per spec §9.
        return Verdict(state=VerdictState.PASS)

    # ── Pick ───────────────────────────────────────────────────────
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
        return Verdict(state=VerdictState.AVOID)

    # ── Pass (everyone within ±pass_pp) or default ─────────────────
    return Verdict(state=VerdictState.PASS)
