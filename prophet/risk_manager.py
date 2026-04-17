"""
Prophet-MVP-v1 — Risk Manager (Kelly Criterion)

Determines position sizing using the Kelly Criterion, hard-capped so
the bot never sim-bets more than MAX_BET_PCT (default 2%) of the
current balance on any single event.

Kelly formula (binary outcome):
    f* = (p * b  -  q) / b
where:
    p = estimated probability of winning   (signal.confidence)
    q = 1 - p
    b = net odds received  =  (payout - fees) / cost

We use a "half-Kelly" for additional safety.
"""

from __future__ import annotations

import logging
import math

import config
from strategies.base import Signal

log = logging.getLogger("prophet.risk")


def kelly_fraction(confidence: float, entry_price: float) -> float:
    """
    Compute the raw Kelly fraction for a binary Kalshi contract.

    Parameters
    ----------
    confidence : float  — strategy's estimated win probability (0-1)
    entry_price : float — cost per contract in dollars (0-1 scale)

    Returns
    -------
    float — optimal fraction of bankroll to wager (before caps)
    """
    p = confidence
    q = 1 - p

    # Net payout if the contract settles at $1.00
    fee = config.TRADING_FEE_PCT
    gross_win = 1.0 - entry_price          # profit per contract if win
    net_win = gross_win - fee              # subtract exit fee
    cost = entry_price + fee               # entry cost including fee

    if cost <= 0 or net_win <= 0:
        return 0.0

    b = net_win / cost  # odds ratio

    f_star = (p * b - q) / b
    return max(f_star, 0.0)


def size_position(signal: Signal, current_balance: float) -> int:
    """
    Return the number of contracts to buy (integer, ≥ 0).

    Applies:
      1. Kelly Criterion (half-Kelly for conservatism)
      2. Hard cap at MAX_BET_PCT of current balance
      3. Minimum 1 contract if Kelly says to bet at all
    """
    frac = kelly_fraction(signal.confidence, signal.price)
    half_kelly = frac / 2  # conservative half-Kelly

    # Dollar budget — the smaller of Kelly and the hard cap
    max_dollars = current_balance * config.MAX_BET_PCT
    kelly_dollars = current_balance * half_kelly
    budget = min(kelly_dollars, max_dollars)

    # Cost per contract (price + entry fee)
    cost_per = signal.price + config.TRADING_FEE_PCT
    if cost_per <= 0:
        return 0

    contracts = int(budget / cost_per)

    # Ensure at least 1 if Kelly is positive, but don't exceed budget
    if contracts == 0 and frac > 0 and cost_per <= max_dollars:
        contracts = 1

    log.info(
        "SIZING  %s  kelly=%.4f  half=%.4f  budget=$%.2f  contracts=%d",
        signal.ticker, frac, half_kelly, budget, contracts,
    )
    return contracts
