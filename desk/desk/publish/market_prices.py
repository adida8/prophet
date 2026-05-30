"""Build `MarketPriceRow`s from a `MarketSnapshot`.

Pure transform — reads the enriched VenuePrice tuples on a snapshot
and emits the contract sub-models. Per ADR 0004 this is the
publisher's job; the sport adapter delivers the snapshot, the
publisher serialises it.

`is_best` is decided here: cheapest venue per side by `true_price`,
or by `implied_p` when no row carries `true_price` (legacy snapshot).
At most one `is_best=true` per side.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Literal

from desk.data.oddsapi.venues import (
    LAUNCH_VENUE_IDS,
    VENUE_DISPLAY_NAMES,
)
from desk.publish.contract import (
    MarketPriceRow,
    MarketPriceVenue,
    MarketVenue,
    VenueType,
)
from desk.pricing.cost import VenueType as PricingVenueType
from desk.pricing.consensus import consensus_fair
from desk.verdict.compare import MarketSnapshot, VenuePrice

log = logging.getLogger("desk.publish.market_prices")

Side = Literal["a", "draw", "b"]

# Bridge between the pricing module's enum (where venue_type values
# come from on the snapshot) and the contract enum (what gets
# serialised). Same string values so the cast is mechanical.
_VENUE_TYPE_MAP = {
    PricingVenueType.SPORTSBOOK:        VenueType.SPORTSBOOK,
    PricingVenueType.EXCHANGE:          VenueType.EXCHANGE,
    PricingVenueType.PREDICTION_MARKET: VenueType.PREDICTION_MARKET,
}


def build_market_prices(snapshot: MarketSnapshot) -> list[MarketPriceRow]:
    """Group snapshot prices by side → one `MarketPriceRow` per side.

    Returns [] when the snapshot has no enriched rows. Caller should
    check the cross-venue flag before publishing the rows.
    """
    by_side: dict[Side, list[VenuePrice]] = defaultdict(list)
    for p in snapshot.prices:
        if p.side not in ("a", "draw", "b"):
            continue
        by_side[p.side].append(p)

    rows: list[MarketPriceRow] = []
    for side, candidates in by_side.items():
        # Order: render order from LAUNCH_VENUE_IDS, then anything
        # else (e.g. unknown venues survive but sit at the bottom).
        order = {v: i for i, v in enumerate(LAUNCH_VENUE_IDS)}
        candidates_sorted = sorted(
            candidates,
            key=lambda p: (order.get(p.venue, 99), p.venue),
        )

        # Decide best by true_price if every row has one; fall back to
        # implied_p otherwise.
        if all(p.true_price is not None for p in candidates_sorted):
            best = min(candidates_sorted, key=lambda p: p.true_price)  # type: ignore[arg-type]
        else:
            best = min(candidates_sorted, key=lambda p: p.implied_p)

        venues: list[MarketPriceVenue] = []
        for p in candidates_sorted:
            try:
                venue_enum = MarketVenue(p.venue)
            except ValueError:
                # Unknown venue id — log + skip rather than crash.
                # Most likely an ingest bug; CTA tests catch it.
                log.debug("dropping venue %r from market_prices: not in enum", p.venue)
                continue
            vtype = (_VENUE_TYPE_MAP.get(p.venue_type)   # type: ignore[arg-type]
                     if p.venue_type is not None else None)
            if vtype is None:
                # Without a venue_type we can't render properly.
                # Default to prediction_market for legacy Polymarket
                # rows (the only pre-pivot path) so they still flow
                # through.
                vtype = VenueType.PREDICTION_MARKET
            venues.append(MarketPriceVenue(
                venue=venue_enum,
                name=VENUE_DISPLAY_NAMES.get(p.venue, p.venue.title()),
                venue_type=vtype,
                region=p.region,
                decimal_odds=p.decimal_odds,
                implied_p=p.implied_p,
                true_price=p.true_price,
                fair_p=p.fair_p,
                overround=p.overround,
                is_best=(p is best),
            ))
        if venues:
            rows.append(MarketPriceRow(side=side, venues=venues))
    return rows


def build_consensus_fair(snapshot: MarketSnapshot) -> dict[Side, float] | None:
    """Sharp-weighted consensus `fair_p` per side. None when no side
    has a usable de-vigged opinion."""
    by_side: dict[Side, list[tuple[str, float]]] = defaultdict(list)
    for p in snapshot.prices:
        if p.side not in ("a", "draw", "b"):
            continue
        if p.fair_p is None:
            continue
        by_side[p.side].append((p.venue, p.fair_p))

    out: dict[Side, float] = {}
    for side, pairs in by_side.items():
        if not pairs:
            continue
        try:
            out[side] = consensus_fair(pairs)
        except ValueError:
            # Math layer rejected the input (all-zero weights, etc).
            # Skip the side rather than choke the whole publish.
            continue
    return out or None
