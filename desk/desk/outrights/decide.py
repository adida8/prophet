"""Per-position verdict for the outright winner market.

The site reads one JSON per outright event with a single headline
`verdict.state` (pick / pass / avoid) + the top candidate. So this
module evaluates every YES and every NO position, picks the
maximum-edge candidate clearing the lower-bound gate, and returns one
verdict.

Avoid never fires on this market shape — for the WC winner, "Avoid the
YES" is equivalent to "Pick the NO," which the position framing makes
naturally. So we only produce pick / pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from desk.outrights.ingest_polymarket import OutrightSnapshot
from desk.outrights.model import OutrightModelOutput
from desk.verdict.thresholds import current as current_thresholds


@dataclass(frozen=True)
class Position:
    team:        str
    side:        str             # "YES" or "NO"
    label:       str             # display label, e.g. "YES Argentina"
    model_p:     float           # model's P(this position pays out)
    model_p_lower: float
    model_p_upper: float
    market_p:    float           # price of this position, [0, 1]
    market_url:  str
    edge_pp:     float           # (model_p − market_p) × 100, point estimate
    lower_edge_pp: float         # (model_p_lower − market_p) × 100, the gate


@dataclass(frozen=True)
class OutrightVerdict:
    state:       str             # "pick" | "pass"
    candidate:   Position | None  # the chosen position; None when state is pass
    positions:   tuple[Position, ...]   # the whole ladder, sorted best-edge first


def _decimal_american(p: float) -> str:
    """Return an American-odds string for a probability. For longshot
    binary markets the lower-priced side reads as a + payout; the
    higher-priced as a − payout.
    """
    if p <= 0:
        return ""
    if p >= 1:
        return "−∞"
    if p < 0.5:
        return f"+{int(round((1 - p) / p * 100))}"
    return f"−{int(round(p / (1 - p) * 100))}"


def build_positions(
    snapshot: OutrightSnapshot,
    model: OutrightModelOutput,
) -> list[Position]:
    """Two `Position`s per priced team — YES and NO — read directly off
    market prices (no `1 − YES` derivation; the longshot vig is real
    money and the NO side has its own market).
    """
    out: list[Position] = []
    for p in snapshot.prices:
        # Skip teams the model doesn't know about (defensive — the
        # ingest path normalises names to canonical, but if the field
        # changes and a participant slips through, don't crash).
        if p.team not in model.p_win:
            continue
        mp_yes  = model.p_win[p.team]
        mpL_yes = model.p_win_lower[p.team]
        mpU_yes = model.p_win_upper[p.team]

        out.append(Position(
            team=p.team,
            side="YES",
            label=f"YES {p.team}",
            model_p=mp_yes,
            model_p_lower=mpL_yes,
            model_p_upper=mpU_yes,
            market_p=p.yes_p,
            market_url=p.market_url,
            edge_pp=(mp_yes - p.yes_p) * 100,
            lower_edge_pp=(mpL_yes - p.yes_p) * 100,
        ))
        # NO position — bounds flip
        out.append(Position(
            team=p.team,
            side="NO",
            label=f"NO {p.team}",
            model_p=1.0 - mp_yes,
            model_p_lower=1.0 - mpU_yes,
            model_p_upper=1.0 - mpL_yes,
            market_p=p.no_p,
            market_url=p.market_url,
            edge_pp=((1.0 - mp_yes) - p.no_p) * 100,
            lower_edge_pp=((1.0 - mpU_yes) - p.no_p) * 100,
        ))
    return out


def decide(
    snapshot: OutrightSnapshot,
    model: OutrightModelOutput,
) -> OutrightVerdict:
    positions = build_positions(snapshot, model)
    # Rank by point-estimate edge so the ladder UI shows the most
    # interesting positions first. The gate uses the lower bound.
    positions.sort(key=lambda p: -p.edge_pp)

    pick_pp = current_thresholds().pick_pp
    best = None
    for pos in positions:
        if pos.lower_edge_pp >= pick_pp:
            if best is None or pos.lower_edge_pp > best.lower_edge_pp:
                best = pos

    if best is None:
        return OutrightVerdict(state="pass", candidate=None, positions=tuple(positions))
    return OutrightVerdict(state="pick", candidate=best, positions=tuple(positions))


def american_for(position: Position) -> str:
    return _decimal_american(position.market_p)
