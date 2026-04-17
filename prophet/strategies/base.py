"""
Prophet-MVP-v1 — Abstract Strategy Base
All trading strategies inherit from this class.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class Signal:
    """A trading signal emitted by a strategy."""
    ticker: str
    side: str          # "BUY_YES" or "BUY_NO"
    price: float       # the entry price (0-1 scale, e.g. 0.42 = 42¢)
    confidence: float  # 0-1 — used by the Kelly Criterion sizing
    reason: str        # human-readable justification


class Strategy(abc.ABC):
    """
    Base class for all Prophet strategies.

    Subclasses must implement `evaluate`, which receives a tick dict
    from the WebSocket and optionally returns a Signal.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier for the strategy."""
        ...

    @abc.abstractmethod
    def evaluate(self, tick: dict) -> Signal | None:
        """
        Inspect a real-time tick and decide whether to emit a signal.

        Parameters
        ----------
        tick : dict
            A ticker message from the Kalshi WebSocket, typically containing:
              market_ticker, yes_price, no_price, yes_bid, yes_ask,
              no_bid, no_ask, volume, open_interest, etc.

        Returns
        -------
        Signal or None
        """
        ...
