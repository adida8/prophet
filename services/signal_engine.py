"""
Adapter between NormalizedMarket snapshots and the Prophet strategy layer.

Converts a NormalizedMarket (or matched pair) into the tick-dict format
that Strategy.evaluate() expects, without touching strategies/ code.
"""

from __future__ import annotations

from core.market_normalizer import NormalizedMarket
from strategies.base import Signal
from strategies.simple_arb import SimpleArbStrategy

_default_strategy = SimpleArbStrategy()


def _to_tick(market: NormalizedMarket, override_yes: float | None = None, override_no: float | None = None) -> dict:
    return {
        "market_ticker": market.platform_id,
        "yes_price": override_yes if override_yes is not None else market.yes_price,
        "no_price":  override_no  if override_no  is not None else market.no_price,
        "yes_bid":   market.best_bid,
        "yes_ask":   market.best_ask,
    }


def evaluate_market(market: NormalizedMarket, strategy=None) -> Signal | None:
    """Run the strategy against a single normalized market snapshot."""
    s = strategy or _default_strategy
    return s.evaluate(_to_tick(market))


def evaluate_matched_pair(
    kalshi: NormalizedMarket,
    poly: NormalizedMarket,
    strategy=None,
) -> Signal | None:
    """
    Evaluate a cross-platform matched pair.
    Uses Kalshi as the canonical ticker (where we execute).
    Synthesizes the cheapest YES + cheapest NO across both platforms.
    """
    best_yes = min(kalshi.yes_price, poly.yes_price)
    best_no  = min(kalshi.no_price,  poly.no_price)
    s = strategy or _default_strategy
    return s.evaluate(_to_tick(kalshi, override_yes=best_yes, override_no=best_no))
