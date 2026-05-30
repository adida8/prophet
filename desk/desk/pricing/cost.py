"""Effective entry cost `e` — the all-in implied probability you pay.

Three venue types, three formulas (THE_DESK_NONUS_SPORTSBOOK_SCOPING.md §2):

    SPORTSBOOK            Pinnacle, William Hill, Sky Bet
                          margin baked into the price, no commission
                          e = 1 / decimal_odds

    EXCHANGE              Betfair Exchange (UK/EU)
                          peer-to-peer back/lay; commission `c` on net win
                          d_eff = 1 + (b - 1) * (1 - c)
                          e     = 1 / d_eff

    PREDICTION_MARKET     Polymarket
                          ask `p` in [0,1] = naive implied
                          e = ask + taker_fee + half_spread

Defaults are conservative — half-spread + taker fee on Polymarket are
the scope-doc's launch numbers (0.75% fee at the 50/50 peak per
THE_DESK_NONUS_SPORTSBOOK_SCOPING.md §1; spread is the bid/ask gap on
the actual book and varies by liquidity).

This module returns a single bounded float per side per venue. Bounds:
the result is clamped to [0, 1] so a misconfigured spread / commission
can never produce a negative price. Anything outside that range is a
caller bug — assert in tests, not at runtime, so the math stays linear.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VenueType(str, Enum):
    """How a venue charges. Drives which `true_price_*` helper to call.

    String-valued so the value survives JSON round-trips intact (used
    later by the published contract per ADR 0004)."""
    SPORTSBOOK        = "sportsbook"
    EXCHANGE          = "exchange"
    PREDICTION_MARKET = "prediction_market"


# ── Per-venue-type input shapes ───────────────────────────────────────

@dataclass(frozen=True)
class SportsbookCostInputs:
    """A book quote, decimal odds. No commission, no fee.

    `decimal_odds` is the payout multiplier on a 1-unit stake including
    stake return — Pinnacle's classic "5.40 on Argentina" sits here.
    """
    decimal_odds: float


@dataclass(frozen=True)
class ExchangeCostInputs:
    """An exchange back quote + commission on net winnings.

    `back_odds` is the decimal price someone offered to lay (i.e. what
    you'd be backing at). `commission` is the exchange's % on net win,
    e.g. 0.02 for Betfair's standard 2% (some accounts pay 5%).
    """
    back_odds:  float
    commission: float = 0.02


@dataclass(frozen=True)
class PolymarketCostInputs:
    """A Polymarket-style binary outcome with an ask + fee + spread.

    `ask` — best price to buy YES, in [0,1].
    `taker_fee` — taker fee fraction of position (0.0075 ≈ 0.75% at the
                  50/50 peak per THE_DESK_NONUS_SPORTSBOOK_SCOPING.md §1).
    `half_spread` — half the bid/ask gap, i.e. the slippage from the
                    midpoint. Defaults to 0 (caller supplies real spread
                    when the book carries one).
    """
    ask:         float
    taker_fee:   float = 0.0075
    half_spread: float = 0.0


# ── Per-venue-type formulas ───────────────────────────────────────────

def true_price_sportsbook(inputs: SportsbookCostInputs) -> float:
    """e = 1 / decimal_odds. Margin lives in the price."""
    d = inputs.decimal_odds
    if d <= 1.0:
        raise ValueError(
            f"decimal_odds must be > 1.0 (got {d}); "
            "1.0 would mean you wager and win nothing on top."
        )
    return _clamp(1.0 / d)


def true_price_exchange(inputs: ExchangeCostInputs) -> float:
    """Commission-adjusted effective payout.

    Net win on a 1-unit stake = (back_odds - 1) * (1 - commission).
    Total return (incl. stake) = 1 + net win.
    Implied probability you pay = 1 / total return.
    """
    b = inputs.back_odds
    c = inputs.commission
    if b <= 1.0:
        raise ValueError(
            f"back_odds must be > 1.0 (got {b})."
        )
    if not (0.0 <= c < 1.0):
        raise ValueError(
            f"commission must be in [0, 1) (got {c}); "
            "Betfair charges 2-5% — c = 0.02 .. 0.05."
        )
    d_eff = 1.0 + (b - 1.0) * (1.0 - c)
    return _clamp(1.0 / d_eff)


def true_price_polymarket(inputs: PolymarketCostInputs) -> float:
    """e = ask + taker_fee + half_spread.

    Caller already encodes spread + fee as fractions of position; we
    sum them onto the naive implied (= ask) directly. Negative spread /
    fee is a caller bug.
    """
    ask    = inputs.ask
    fee    = inputs.taker_fee
    spread = inputs.half_spread
    if not (0.0 <= ask <= 1.0):
        raise ValueError(f"ask must be in [0, 1] (got {ask}).")
    if fee < 0.0:
        raise ValueError(f"taker_fee must be ≥ 0 (got {fee}).")
    if spread < 0.0:
        raise ValueError(f"half_spread must be ≥ 0 (got {spread}).")
    return _clamp(ask + fee + spread)


# ── Dispatch helper ───────────────────────────────────────────────────

def true_price(venue_type: VenueType, inputs) -> float:
    """Dispatch on `venue_type`. Caller picks the inputs dataclass to
    match — type-check is the linter's job, not ours."""
    if venue_type == VenueType.SPORTSBOOK:
        return true_price_sportsbook(inputs)
    if venue_type == VenueType.EXCHANGE:
        return true_price_exchange(inputs)
    if venue_type == VenueType.PREDICTION_MARKET:
        return true_price_polymarket(inputs)
    raise ValueError(f"unknown venue_type: {venue_type!r}")


def _clamp(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x
