"""
Prophet-MVP-v1 — Performance Logger
Appends simulated trades to a CSV and computes running P&L.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config

log = logging.getLogger("prophet.logger")

FIELDNAMES = [
    "timestamp",
    "ticker",
    "side",        # BUY_YES / BUY_NO
    "entry_price",
    "contracts",
    "fee",
    "net_cost",
    "balance_after",
]


def _ensure_csv(path: Path) -> None:
    """Create the CSV with a header row if it doesn't exist yet."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def record_trade(
    ticker: str,
    side: str,
    entry_price: float,
    contracts: int,
    fee: float,
    net_cost: float,
    balance_after: float,
    path: Path | None = None,
) -> None:
    """Append one simulated-trade row to the portfolio CSV."""
    path = path or config.PORTFOLIO_CSV
    _ensure_csv(path)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "side": side,
        "entry_price": round(entry_price, 4),
        "contracts": contracts,
        "fee": round(fee, 4),
        "net_cost": round(net_cost, 4),
        "balance_after": round(balance_after, 2),
    }
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)

    log.info(
        "TRADE  %s  %s  price=%.2f¢  qty=%d  fee=%.4f  cost=%.4f  bal=%.2f",
        ticker, side, entry_price * 100, contracts, fee, net_cost, balance_after,
    )


def get_portfolio_summary(path: Path | None = None) -> dict:
    """
    Read the CSV and return a summary dict:
      total_trades, total_fees, total_invested, current_balance, return_pct
    """
    path = path or config.PORTFOLIO_CSV
    if not path.exists():
        return {
            "total_trades": 0,
            "total_fees": 0.0,
            "total_invested": 0.0,
            "current_balance": config.STARTING_BALANCE,
            "return_pct": 0.0,
        }

    df = pd.read_csv(path)
    if df.empty:
        return {
            "total_trades": 0,
            "total_fees": 0.0,
            "total_invested": 0.0,
            "current_balance": config.STARTING_BALANCE,
            "return_pct": 0.0,
        }

    current_bal = df["balance_after"].iloc[-1]
    return {
        "total_trades": len(df),
        "total_fees": round(df["fee"].sum(), 4),
        "total_invested": round(df["net_cost"].sum(), 4),
        "current_balance": round(current_bal, 2),
        "return_pct": round(
            (current_bal - config.STARTING_BALANCE) / config.STARTING_BALANCE * 100, 2
        ),
    }
