"""
Prophet-MVP-v1 — Simple Arbitrage / Imbalance Strategy

Logic:
  If the 'Yes' price < 0.45 AND the 'No' price > 0.60, there's a
  mispricing imbalance. Buy the cheap 'Yes' side because the implied
  probabilities don't add to ~1.0, leaving room for profit after fees.

  The confidence score is proportional to the size of the gap, capped
  at 0.95 so the Kelly Criterion never goes all-in.
"""

from __future__ import annotations

import logging

import config
from strategies.base import Signal, Strategy

log = logging.getLogger("prophet.strategy.simple_arb")

# ── Thresholds ────────────────────────────────────────────────────────
YES_CEILING = 0.45   # Yes price must be below this
NO_FLOOR = 0.60      # No price must be above this
MIN_EDGE = 0.05      # minimum expected edge after fees to trigger


class SimpleArbStrategy(Strategy):
    """Detect Yes/No imbalance and signal a buy on the cheap side."""

    @property
    def name(self) -> str:
        return "simple_arb"

    def evaluate(self, tick: dict) -> Signal | None:
        ticker = tick.get("market_ticker", "")
        yes_price = tick.get("yes_price", 0)
        no_price = tick.get("no_price", 0)

        # Kalshi prices are in cents (1-99); normalise to 0-1
        if yes_price > 1:
            yes_price /= 100
        if no_price > 1:
            no_price /= 100

        if not (0 < yes_price < 1 and 0 < no_price < 1):
            return None  # invalid / missing data

        # ── Check the imbalance condition ─────────────────────────
        if yes_price >= YES_CEILING or no_price <= NO_FLOOR:
            return None

        # Expected profit: (1 - yes_price) is the payout if "Yes" wins.
        # Subtract the 0.8% fee on both entry and exit (round-trip).
        fee_rt = config.TRADING_FEE_PCT * 2
        expected_profit = (1 - yes_price) - fee_rt
        edge = expected_profit - yes_price  # net edge per contract

        if edge < MIN_EDGE:
            return None

        # Confidence: scale edge into [0.3, 0.95]
        confidence = min(0.95, 0.3 + edge * 3)

        reason = (
            f"Imbalance detected — Yes={yes_price:.2f}, No={no_price:.2f}. "
            f"Edge after fees: {edge:.4f}. Confidence: {confidence:.2f}"
        )
        log.info("SIGNAL  %s  %s", ticker, reason)

        return Signal(
            ticker=ticker,
            side="BUY_YES",
            price=yes_price,
            confidence=confidence,
            reason=reason,
        )
