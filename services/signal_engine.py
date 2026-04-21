"""
Adapter between NormalizedMarket / ComparedMarket snapshots and the Prophet
strategy layer. Converts market data into the tick-dict format Strategy.evaluate()
expects, without touching strategies/ code.
"""

from __future__ import annotations

from typing import Optional

from core.market_normalizer import NormalizedMarket
from risk_manager import kelly_fraction
from strategies.base import Signal
from strategies.simple_arb import SimpleArbStrategy

_default_strategy = SimpleArbStrategy()


# ── Low-level adapters ────────────────────────────────────────────────

def _to_tick(
    market: NormalizedMarket,
    override_yes: Optional[float] = None,
    override_no:  Optional[float] = None,
) -> dict:
    return {
        "market_ticker": market.platform_id,
        "yes_price": override_yes if override_yes is not None else market.yes_price,
        "no_price":  override_no  if override_no  is not None else market.no_price,
        "yes_bid":   market.best_bid,
        "yes_ask":   market.best_ask,
    }


def evaluate_market(market: NormalizedMarket, strategy=None) -> Optional[Signal]:
    """Run the strategy against a single normalized market snapshot."""
    s = strategy or _default_strategy
    return s.evaluate(_to_tick(market))


def evaluate_matched_pair(
    kalshi: NormalizedMarket,
    poly: NormalizedMarket,
    strategy=None,
) -> Optional[Signal]:
    """
    Evaluate a cross-platform matched pair.
    Uses Kalshi as the canonical ticker (where we execute).
    Synthesizes the cheapest YES + cheapest NO across both platforms.
    """
    best_yes = min(kalshi.yes_price, poly.yes_price)
    best_no  = min(kalshi.no_price,  poly.no_price)
    s = strategy or _default_strategy
    return s.evaluate(_to_tick(kalshi, override_yes=best_yes, override_no=best_no))


# ── ComparedMarket adapter ────────────────────────────────────────────

def evaluate_compared(compared, strategy=None) -> Optional[dict]:
    """
    Evaluate a ComparedMarket and return an enriched signal dict, or None.

    The returned dict is safe to serialise to JSON for the /api/signal endpoint.
    """
    from services.odds_comparator import ComparedMarket, PlatformPrice

    s = strategy or _default_strategy

    # Build the best-cross-platform tick
    yes_prices = {p: v.yes_price for p, v in compared.platforms.items() if v.yes_price > 0}
    no_prices  = {p: v.no_price  for p, v in compared.platforms.items() if v.no_price  > 0}

    if not yes_prices:
        return None

    best_yes = min(yes_prices.values())
    best_no  = min(no_prices.values()) if no_prices else round(1.0 - best_yes, 4)

    # Use Kalshi ticker if available (execution platform), else use "polymarket:<id>"
    kalshi_pp = compared.platforms.get("kalshi")
    canonical_ticker = (
        next(iter(compared.id.split(":")), compared.id)  # strip prefix for fuzzy IDs
        if not kalshi_pp
        else compared.id
    )

    tick = {
        "market_ticker": canonical_ticker,
        "yes_price": best_yes,
        "no_price":  best_no,
    }

    signal = s.evaluate(tick)
    if signal is None:
        return None

    # Kelly sizing at a hypothetical $1,000 reference balance
    frac  = kelly_fraction(signal.confidence, signal.price)
    kelly_pct = round(frac * 50, 2)  # half-Kelly percentage

    return {
        "market_id":      compared.id,
        "title":          compared.title,
        "category":       compared.category,
        "source":         compared.source,
        "side":           signal.side,
        "price":          round(signal.price, 4),
        "confidence":     round(signal.confidence, 4),
        "kelly_pct":      kelly_pct,
        "reason":         signal.reason,
        "best_yes_platform": compared.best_yes_platform,
        "best_yes_price":    compared.best_yes_price,
        "best_no_platform":  compared.best_no_platform,
        "best_no_price":     compared.best_no_price,
        "price_gap":         compared.price_gap,
        "arb_edge_pct":      compared.arb_edge_pct,
        "platforms": {
            p: {"yes_price": v.yes_price, "no_price": v.no_price, "url": v.url}
            for p, v in compared.platforms.items()
        },
    }


def evaluate_all(compared_markets: list, strategy=None) -> list[dict]:
    """Run evaluate_compared over a list, returning only markets with signals."""
    results = []
    for cm in compared_markets:
        sig = evaluate_compared(cm, strategy)
        if sig:
            results.append(sig)
    results.sort(key=lambda s: s["confidence"], reverse=True)
    return results
