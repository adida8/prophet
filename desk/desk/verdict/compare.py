"""Market snapshots — multi-venue prices for one match.

A `VenuePrice` carries one venue's quote for one side. In v1 every
price was a normalised Polymarket-style implied probability and the
verdict took `min(implied_p)` across venues as "best price" — that's
still what `MarketSnapshot.best_for(side)` returns by default, so any
caller using the legacy API is byte-identical.

The non-US pivot (THE_DESK_NONUS_SPORTSBOOK_SCOPING.md) added two
extra optional fields per quote:

  `venue_type`  — sportsbook | exchange | prediction_market. Drives
                  the `true_price` formula in `desk/pricing/cost.py`.
  `true_price`  — effective implied probability paid all-in (margin +
                  fee + spread + commission). When set, the snapshot's
                  `best_for_true_price(side)` returns the cheapest
                  venue by `true_price` instead of by `implied_p`.

Both fields default to None so legacy callers / fixtures don't break.
A caller asking for `best_for_true_price` on a snapshot whose rows
weren't enriched falls back to `best_for` semantics — explicit, never
silently mixed.

Bookkeeping fields (`region`, `decimal_odds`, `fair_p`) are carried
through unchanged so the publisher can surface per-venue rows without
re-deriving anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from desk.pricing.cost import VenueType

Side = Literal["a", "b", "draw"]


@dataclass(frozen=True)
class VenuePrice:
    """One venue's price for one side.

    `implied_p`  — naive implied prob (`1/decimal` for books, `ask` for
                   Polymarket). LEGACY-COMPATIBLE: pre-pivot callers
                   pass only this; all the non-US-pivot fields default
                   to None.

    `venue_type` — what kind of venue (drives the cost formula).
    `region`     — `uk`, `eu`, `global`, etc — surfaces on the
                   comparison card.
    `decimal_odds` — raw book quote, when the source carries it.
    `true_price` — effective implied probability paid (`e`). Cheapest
                   venue by this is the "best place to act".
    `fair_p`     — venue's de-vigged opinion for this side. Consensus
                   narrative only; never drives edge.
    `overround`  — sum of de-vig inputs (1.04..1.07 on a sharp 1X2,
                   1.30..1.50 on outrights). Renders as the book's
                   margin %.
    """
    venue:        str
    side:         Side
    implied_p:    float
    venue_type:   Optional[VenueType] = None
    region:       Optional[str]       = None
    decimal_odds: Optional[float]     = None
    true_price:   Optional[float]     = None
    fair_p:       Optional[float]     = None
    overround:    Optional[float]     = None


@dataclass(frozen=True)
class MarketSnapshot:
    """One match's market state across all venues that priced it."""
    match_id: str
    asof:     datetime
    prices:   tuple[VenuePrice, ...] = field(default_factory=tuple)

    def best_for(self, side: Side) -> VenuePrice | None:
        """Cheapest venue for `side` by NAIVE implied probability.

        Pre-pivot semantics, kept verbatim so the WC-2022 backtest is
        byte-identical with the cross-venue feature flag off. Returns
        None when no venue priced this side.
        """
        candidates = [p for p in self.prices if p.side == side]
        if not candidates:
            return None
        return min(candidates, key=lambda p: p.implied_p)

    def best_for_true_price(self, side: Side) -> VenuePrice | None:
        """Cheapest venue for `side` by **true price** (`e`).

        Used by the non-US pricing path. Falls back to `best_for` rules
        when any candidate's `true_price` is None — mixing true_price
        rows with naive-implied rows would be a real bug, so we'd
        rather honour the legacy semantics explicitly than silently
        rank apples vs oranges.
        """
        candidates = [p for p in self.prices if p.side == side]
        if not candidates:
            return None
        if any(p.true_price is None for p in candidates):
            return min(candidates, key=lambda p: p.implied_p)
        return min(candidates, key=lambda p: p.true_price)   # type: ignore[arg-type]

    def has_full_coverage(self, sides: tuple[Side, ...]) -> bool:
        return all(self.best_for(s) is not None for s in sides)

    def stale(self, *, now: datetime, max_age_sec: int = 300) -> bool:
        """Spec §9: data older than 5 minutes → treat as stale, default to Pass."""
        if self.asof.tzinfo is None:
            asof = self.asof.replace(tzinfo=timezone.utc)
        else:
            asof = self.asof
        return (now - asof).total_seconds() > max_age_sec
