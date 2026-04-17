"""
Prophet-MVP-v1 — Simple Arbitrage Strategy

Evaluates Kalshi markets for mispriced YES/NO contracts.
Thresholds are loaded from data/settings.json on every call,
so changes from the dashboard take effect immediately.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import config

log = logging.getLogger("prophet.strategy")

SETTINGS_PATH = config.DATA_DIR / "settings.json"

DEFAULTS = {
    "yes_ceiling": 0.42,
    "no_floor": 0.58,
    "min_edge": 0.03,
}


def _load_settings() -> dict:
    """Read thresholds from settings.json, creating it with defaults if missing."""
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(DEFAULTS, indent=2))
        return dict(DEFAULTS)
    try:
        data = json.loads(SETTINGS_PATH.read_text())
        return {
            "yes_ceiling": float(data.get("yes_ceiling", DEFAULTS["yes_ceiling"])),
            "no_floor": float(data.get("no_floor", DEFAULTS["no_floor"])),
            "min_edge": float(data.get("min_edge", DEFAULTS["min_edge"])),
        }
    except (json.JSONDecodeError, ValueError):
        log.warning("Corrupt settings.json — using defaults")
        return dict(DEFAULTS)


def evaluate(ticker: str, yes_price: float, no_price: float) -> dict | None:
    """
    Check if a market has a tradeable edge.

    Returns a signal dict if an opportunity exists, None otherwise.
    Signal: {"ticker", "side", "price", "edge", "reason"}
    """
    settings = _load_settings()
    yes_ceil = settings["yes_ceiling"]
    no_floor = settings["no_floor"]
    min_edge = settings["min_edge"]

    # YES is cheap — market underpricing the outcome
    if yes_price < yes_ceil:
        edge = yes_ceil - yes_price
        if edge >= min_edge:
            log.info(
                "SIGNAL  %s  BUY_YES  price=%.2f  ceil=%.2f  edge=%.4f",
                ticker, yes_price, yes_ceil, edge,
            )
            return {
                "ticker": ticker,
                "side": "BUY_YES",
                "price": yes_price,
                "edge": round(edge, 4),
                "reason": f"YES @ {yes_price:.2f} < ceiling {yes_ceil:.2f}",
            }

    # NO is cheap — market overpricing the outcome
    if no_price > no_floor:
        edge = no_price - no_floor
        if edge >= min_edge:
            log.info(
                "SIGNAL  %s  BUY_NO  price=%.2f  floor=%.2f  edge=%.4f",
                ticker, no_price, no_floor, edge,
            )
            return {
                "ticker": ticker,
                "side": "BUY_NO",
                "price": no_price,
                "edge": round(edge, 4),
                "reason": f"NO @ {no_price:.2f} > floor {no_floor:.2f}",
            }

    return None
