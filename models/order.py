"""
Prophet-MVP-v1 — Order & Position data models.

Shared between the paper and live execution paths so the dashboard and
logger can treat both the same way.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class OrderStatus(str, Enum):
    PENDING = "pending"        # Sent to API, awaiting response
    RESTING = "resting"        # On the book, not yet filled
    FILLED = "filled"          # Fully executed
    CANCELLED = "cancelled"    # Cancelled by user or system
    FAILED = "failed"          # API error


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Order:
    id: str
    ticker: str
    side: str                              # "yes" or "no"
    price: int                             # Cents (Kalshi native)
    contracts: int
    status: OrderStatus
    mode: ExecutionMode
    kalshi_order_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    filled_at: datetime | None = None
    fill_price: int | None = None          # Actual fill price in cents
    fee_cents: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["mode"] = self.mode.value
        d["created_at"] = self.created_at.isoformat()
        d["filled_at"] = self.filled_at.isoformat() if self.filled_at else None
        return d


@dataclass
class Position:
    ticker: str
    side: str
    contracts: int
    avg_entry_price: int                   # Cents
    current_price: int | None = None
    unrealized_pnl: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class SafetyError(RuntimeError):
    """Raised when a trade would violate a safety rail."""

    def __init__(self, rule: str, message: str):
        super().__init__(message)
        self.rule = rule
        self.message = message
