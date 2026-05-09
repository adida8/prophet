"""Liquidity filter — extreme-price guard.

Polymarket sometimes prices a market side at +9999 (~1% implied) or
its opposite (~99%). Those quotes are "no opinion" — the venue is
willing to trade either edge but isn't expressing a view. The verdict
step should treat such markets as illiquid and default to Pass rather
than issue a confident Pick against a price the venue itself doesn't
believe.

Order-book depth check is a placeholder for v1.1 — Polymarket's gamma
endpoint doesn't expose it cheaply, so we lean on the implied-probability
extremes for now.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from desk.verdict.compare import MarketSnapshot, Side


@dataclass(frozen=True)
class LiquidityRules:
    """Decimals 0..1 — symmetric around 0.5."""
    min_p:        float       # any side at or below this → reject
    max_p:        float       # any side at or above this → reject
    min_depth_usd: float = 0.0  # placeholder; v1 doesn't read it

    @classmethod
    def from_env(cls) -> "LiquidityRules":
        min_p = float(os.getenv("DESK_LIQUIDITY_MIN_P", "0.02"))
        return cls(
            min_p=min_p,
            max_p=1.0 - min_p,
            min_depth_usd=float(os.getenv("DESK_LIQUIDITY_MIN_DEPTH_USD", "0")),
        )


@dataclass(frozen=True)
class LiquidityCheck:
    """Result of a market liquidity check."""
    is_liquid: bool
    reason:    str | None = None     # populated only when is_liquid=False


def is_liquid(
    snapshot: MarketSnapshot,
    sides:    tuple[Side, ...],
    rules:    LiquidityRules | None = None,
) -> LiquidityCheck:
    """Return whether `snapshot` is tradeable.

    A snapshot is illiquid when ANY side has a best implied probability
    at or beyond the configured tails. The check is deliberately simple
    — false positives (rejecting a borderline market) are cheap, false
    negatives (issuing a Pick on a thin market) are reputationally
    expensive.
    """
    rules = rules if rules is not None else LiquidityRules.from_env()

    for s in sides:
        bv = snapshot.best_for(s)
        if bv is None:
            return LiquidityCheck(False, f"market_thin:no_quote_for_{s}")
        if bv.implied_p <= rules.min_p:
            return LiquidityCheck(False, f"market_thin:long_shot_{s}_at_{bv.implied_p:.3f}")
        if bv.implied_p >= rules.max_p:
            return LiquidityCheck(False, f"market_thin:short_favourite_{s}_at_{bv.implied_p:.3f}")

    return LiquidityCheck(True, None)
