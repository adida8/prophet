"""Build enriched VenuePrices from cached Odds-API rows.

The football pipeline already has `desk/ingest/polymarket_prices.py`
that turns a single gamma event into a `MarketSnapshot`. This module
is the equivalent for the sportsbook adapter: given a fixture +
cached per-venue decimal odds, produce a list of `VenuePrice` rows
with `venue_type`, `region`, `true_price`, `fair_p`, and `overround`
populated.

What lands on the snapshot drives downstream:
- `best_for_true_price(side)` returns the cheapest venue by `e`.
- `fair_p` per row feeds the consensus blend in the explainer.
- The publisher (PR 6 of this build) reads the enriched rows to emit
  the per-venue contract block.

Pure transform — no I/O, no Anthropic, no network. Cache reads happen
in the caller (refresh loop), so this module stays trivially testable
against a list of `PriceRow` rows.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from desk.data.oddsapi.cache import PriceRow
from desk.data.oddsapi.venues import (
    VENUE_REGIONS,
    venue_type_for,
)
from desk.pricing.cost import (
    ExchangeCostInputs,
    PolymarketCostInputs,
    SportsbookCostInputs,
    VenueType,
    true_price as compute_true_price,
)
from desk.pricing.devig import devig_multiplicative
from desk.verdict.compare import Side, VenuePrice

log = logging.getLogger("desk.sports.football.oddsapi_prices")

# Default exchange commission. Betfair Exchange's standard rate; some
# accounts pay 5%, but absent that signal we use the conservative low
# value so we don't over-tax the venue and under-rank it.
DEFAULT_EXCHANGE_COMMISSION = 0.02

# Required side set for v1's 1X2 markets. A venue that didn't price all
# three sides can't be de-vigged — we still emit the rows but leave
# `fair_p` / `overround` empty for that venue.
_SIDES_3WAY: tuple[Side, ...] = ("a", "draw", "b")


def venue_prices_from_oddsapi(
    rows: Iterable[PriceRow],
    *,
    exchange_commission: float = DEFAULT_EXCHANGE_COMMISSION,
) -> list[VenuePrice]:
    """Turn a flat list of cached PriceRows into enriched VenuePrices.

    Groups by venue, de-vigs per venue (multiplicative), computes
    `true_price` per side per venue, returns the flat list ready to
    drop into a `MarketSnapshot`. Out-of-spec venues (unknown id, no
    decimal_odds) are silently skipped; a single weird row never
    breaks the rest.
    """
    by_venue: dict[str, dict[Side, PriceRow]] = defaultdict(dict)
    for r in rows:
        if r.side not in _SIDES_3WAY:
            continue
        if r.decimal_odds <= 1.0:
            continue
        by_venue[r.venue_id][r.side] = r

    out: list[VenuePrice] = []
    for venue_id, side_to_row in by_venue.items():
        try:
            vtype = venue_type_for(venue_id)
        except KeyError:
            log.debug("dropping unknown venue %r", venue_id)
            continue

        # Per-side naive implied (1/d for sportsbooks + exchanges).
        # Polymarket would not come through this path (it's not on the
        # Odds API), but the formula tolerates anything decimal-shaped.
        implied_by_side: dict[Side, float] = {}
        for side, row in side_to_row.items():
            implied_by_side[side] = 1.0 / row.decimal_odds

        # De-vig only when the venue priced all three sides; otherwise
        # we'd strip margin off a partial outcome set and the consensus
        # blend would be misleading. Caller can detect the partial
        # coverage by checking `fair_p is None`.
        if set(implied_by_side.keys()) == set(_SIDES_3WAY):
            ordered = [implied_by_side[s] for s in _SIDES_3WAY]
            fair = devig_multiplicative(ordered)
            fair_by_side: dict[Side, float | None] = dict(zip(_SIDES_3WAY, fair))
            overround = sum(ordered)
        else:
            fair_by_side = {s: None for s in _SIDES_3WAY}
            overround = None

        region = VENUE_REGIONS.get(venue_id)
        for side, row in side_to_row.items():
            implied = implied_by_side[side]
            tp = _true_price_for(
                vtype=vtype, decimal_odds=row.decimal_odds,
                exchange_commission=exchange_commission,
            )
            out.append(VenuePrice(
                venue=venue_id,
                side=side,
                implied_p=implied,
                venue_type=vtype,
                region=region,
                decimal_odds=row.decimal_odds,
                true_price=tp,
                fair_p=fair_by_side.get(side),
                overround=overround,
            ))
    return out


def _true_price_for(
    *,
    vtype: VenueType,
    decimal_odds: float,
    exchange_commission: float,
) -> float:
    """Compute `e` for a single decimal-odds row.

    Polymarket is not part of the Odds API path so this routine doesn't
    handle PREDICTION_MARKET — Poly prices flow through
    `desk/ingest/polymarket_prices.py` and the runner merges the two
    snapshots downstream.
    """
    if vtype == VenueType.SPORTSBOOK:
        return compute_true_price(
            VenueType.SPORTSBOOK, SportsbookCostInputs(decimal_odds=decimal_odds),
        )
    if vtype == VenueType.EXCHANGE:
        return compute_true_price(
            VenueType.EXCHANGE,
            ExchangeCostInputs(back_odds=decimal_odds, commission=exchange_commission),
        )
    # PREDICTION_MARKET is unexpected on the Odds API surface; we
    # treat it like a Polymarket ask = decimal->implied so the row at
    # least gets a price, but the caller is doing something off-spec.
    return compute_true_price(
        VenueType.PREDICTION_MARKET,
        PolymarketCostInputs(ask=1.0 / decimal_odds),
    )


def enrich_polymarket_venue_prices(
    prices: Iterable[VenuePrice],
) -> list[VenuePrice]:
    """Re-emit Polymarket-only VenuePrice rows with the non-US-pivot
    fields populated (venue_type + true_price + fair_p across the
    three sides).

    The legacy gamma adapter emits `VenuePrice(venue="polymarket",
    side, implied_p)` without the extra fields, because it predates
    the pivot. This helper re-runs the math and returns a new list —
    callers swap the old list out for the enriched one when feeding
    the cross-venue snapshot.
    """
    poly_rows: dict[Side, VenuePrice] = {}
    out: list[VenuePrice] = []
    for p in prices:
        if p.venue == "polymarket" and p.side in _SIDES_3WAY:
            poly_rows[p.side] = p
        else:
            out.append(p)

    if set(poly_rows.keys()) == set(_SIDES_3WAY):
        ordered = [poly_rows[s].implied_p for s in _SIDES_3WAY]
        fair = devig_multiplicative(ordered)
        overround = sum(ordered)
        for side, p, fair_p in zip(_SIDES_3WAY, ordered, fair):
            tp = compute_true_price(
                VenueType.PREDICTION_MARKET, PolymarketCostInputs(ask=p),
            )
            out.append(VenuePrice(
                venue="polymarket",
                side=side,
                implied_p=p,
                venue_type=VenueType.PREDICTION_MARKET,
                region=VENUE_REGIONS.get("polymarket"),
                decimal_odds=None,
                true_price=tp,
                fair_p=fair_p,
                overround=overround,
            ))
    else:
        # Partial-coverage Poly: keep the legacy shape so the
        # cross-venue path falls through cleanly.
        out.extend(poly_rows.values())
    return out
