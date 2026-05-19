"""Voice-checked editorial copy for the outright verdict.

Same posture as `desk/explainer/stub.py` — templated, not LLM-generated,
runs through the voice rules. The match explainer is the reference.
"""

from __future__ import annotations

from dataclasses import dataclass

from desk.outrights.decide import Position, OutrightVerdict, american_for
from desk.outrights.model import OutrightModelOutput
from desk.outrights.ingest_polymarket import OutrightSnapshot


@dataclass(frozen=True)
class OutrightCopy:
    title:    str
    summary:  str
    blurb:    str
    drivers:  tuple[str, ...]


def _pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def _signed_pp(edge_pp: float) -> str:
    return f"{edge_pp:+.1f}pp"


def _pick_summary(pos: Position) -> str:
    """One-sentence editorial: 'model rates X at A%; market prices that
    at B%; the C pp gap is the basis for the Pick.' Matches the match
    explainer's voice; tweaked for outrights so the YES vs NO framing
    reads naturally.
    """
    if pos.side == "YES":
        return (
            f"The model gives {pos.team} a {_pct(pos.model_p)} chance to lift the trophy; "
            f"the market prices that at {_pct(pos.market_p)}. "
            f"The {_signed_pp(pos.edge_pp)} gap is the basis for the Pick."
        )
    return (
        f"The model gives {pos.team} only a {_pct(1 - pos.model_p)} chance to win — "
        f"the YES side trades at {_pct(1 - pos.market_p)}, the NO at {_pct(pos.market_p)}. "
        f"On the NO position the edge is {_signed_pp(pos.edge_pp)}: the market is paying "
        f"to bet against {pos.team} more than the model thinks it should."
    )


def _pass_summary(verdict: OutrightVerdict) -> str:
    if not verdict.positions:
        return "No priced participants in the field — nothing to evaluate."
    top = verdict.positions[0]
    return (
        f"The model and the market agree on the field. The biggest gap is "
        f"{top.team} on the {top.side} side at {_signed_pp(top.edge_pp)} — "
        f"not wide enough on the lower-bound check to call a Pick."
    )


def _drivers_for_pick(pos: Position, model: OutrightModelOutput) -> list[str]:
    drv: list[str] = []
    drv.append(
        f"{pos.team} reaches the top of its group in {_pct(model.p_groupwin.get(pos.team, 0))} "
        f"of simulations."
    )
    band = f"[{_pct(pos.model_p_lower)}, {_pct(pos.model_p_upper)}]"
    drv.append(
        f"Bootstrap band on the {pos.side.lower()} side: {band}; gate clears at "
        f"{_signed_pp(pos.lower_edge_pp)} on the lower bound."
    )
    drv.append(
        f"Market price on the {pos.side.lower()} side: {_pct(pos.market_p)}  "
        f"({american_for(pos)} on Polymarket)."
    )
    return drv


def build_copy(
    snapshot: OutrightSnapshot,
    model: OutrightModelOutput,
    verdict: OutrightVerdict,
) -> OutrightCopy:
    if verdict.state == "pick" and verdict.candidate is not None:
        pos = verdict.candidate
        title = (
            f"{pos.team} · the model leans {pos.side.lower()} on the World Cup winner market"
        )
        summary = _pick_summary(pos)
        blurb = (
            f"The Desk simulates the 2026 World Cup ten thousand times to produce a "
            f"per-team probability of lifting the trophy. {pos.team} comes out at "
            f"{_pct(pos.model_p if pos.side == 'YES' else 1 - pos.model_p)}; Polymarket prices "
            f"that {pos.side} position at {_pct(pos.market_p) if pos.side == 'NO' else _pct(pos.market_p)}.\n\n"
            f"The position {pos.label} carries a {_signed_pp(pos.edge_pp)} point-estimate edge. "
            f"Even on the more conservative bootstrap lower bound, the edge is "
            f"{_signed_pp(pos.lower_edge_pp)} — which clears the +3.0pp Pick threshold.\n\n"
            f"The Desk does not tip. This is what the model thinks and what the market thinks; "
            f"the gap is editorial."
        )
        drivers = tuple(_drivers_for_pick(pos, model))
        return OutrightCopy(title=title, summary=summary, blurb=blurb, drivers=drivers)

    # Pass
    title = f"World Cup 2026 winner · markets agree across the field"
    summary = _pass_summary(verdict)
    if not verdict.positions:
        blurb = "No priced field yet."
        drivers = ()
    else:
        top = verdict.positions[0]
        blurb = (
            f"The Desk simulates the tournament ten thousand times to produce a per-team "
            f"probability. Across the 48-team field the biggest disagreement with the "
            f"market is on {top.team} ({top.side}) at {_signed_pp(top.edge_pp)} — "
            f"a gap the bootstrap lower bound can't sustain. "
            f"No position clears the +3.0pp Pick gate today.\n\n"
            f"The field can move quickly — qualifying clarifies team ratings, draws "
            f"change the bracket, and the market reprices around news. We re-run on the "
            f"data layer's late-binding cadence and republish when something opens up."
        )
        drivers = (
            f"Top market: {top.team} ({top.side}) at {_signed_pp(top.edge_pp)} point-estimate edge.",
            f"Field size: {len(verdict.positions) // 2} priced participants × YES + NO = {len(verdict.positions)} positions.",
            f"Sims: {model.sims:,}. Bootstrap: 100 samples × 1,000 sims with ±50 Elo perturbation.",
        )
    return OutrightCopy(title=title, summary=summary, blurb=blurb, drivers=drivers)
