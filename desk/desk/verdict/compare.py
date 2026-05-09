"""Market snapshots — multi-venue prices for one match.

Polymarket and Kalshi each publish their own implied probabilities for
each side of a 3-way football market. The verdict step asks: for each
side, what's the *best* price the bettor could find across venues?

"Best" for the bettor = lowest implied probability (= highest payout).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Side = Literal["a", "b", "draw"]


@dataclass(frozen=True)
class VenuePrice:
    venue:     str       # "polymarket" or "kalshi"
    side:      Side
    implied_p: float     # 0..1


@dataclass(frozen=True)
class MarketSnapshot:
    match_id: str
    asof:     datetime
    prices:   tuple[VenuePrice, ...] = field(default_factory=tuple)

    def best_for(self, side: Side) -> VenuePrice | None:
        """Lowest implied probability for `side` across venues.

        Returns None when no venue priced this side. The verdict step
        falls back to Pass when any side is missing.
        """
        candidates = [p for p in self.prices if p.side == side]
        if not candidates:
            return None
        return min(candidates, key=lambda p: p.implied_p)

    def has_full_coverage(self, sides: tuple[Side, ...]) -> bool:
        return all(self.best_for(s) is not None for s in sides)

    def stale(self, *, now: datetime, max_age_sec: int = 300) -> bool:
        """Spec §9: data older than 5 minutes → treat as stale, default to Pass."""
        if self.asof.tzinfo is None:
            asof = self.asof.replace(tzinfo=timezone.utc)
        else:
            asof = self.asof
        return (now - asof).total_seconds() > max_age_sec
