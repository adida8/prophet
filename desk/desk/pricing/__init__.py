"""Pricing module — sport-agnostic price normalisation.

For every priced market, the engine asks one question per side per
venue: **what's the all-in effective implied probability you actually
pay to back this side?** Call that `e` ("true price"). It folds in
margin (sportsbooks), commission (exchanges), and fee + spread
(prediction markets) so a Polymarket quote, a Pinnacle quote, and a
Betfair Exchange quote become directly comparable.

The other number the module produces is **`fair_p`** — the
margin-stripped implied probability for the "market consensus" line.
v1 strips margin multiplicatively (`fair_i = implied_i / Σ implied`);
the API leaves a seam for Shin / power-method later.

These two numbers are deliberately separate. The verdict's edge MUST
compare `model_p` to `min_venue(e)` — comparing it to `fair_p` is the
classic mistake that claims value the margin will eat.

This module is pure functions + dataclasses. No I/O, no sport imports.
"""

from desk.pricing.cost import (
    PolymarketCostInputs,
    SportsbookCostInputs,
    ExchangeCostInputs,
    VenueType,
    true_price,
    true_price_sportsbook,
    true_price_exchange,
    true_price_polymarket,
)
from desk.pricing.devig import (
    DevigMethod,
    devig,
    devig_multiplicative,
)
from desk.pricing.consensus import (
    consensus_fair,
)

__all__ = [
    "PolymarketCostInputs",
    "SportsbookCostInputs",
    "ExchangeCostInputs",
    "VenueType",
    "true_price",
    "true_price_sportsbook",
    "true_price_exchange",
    "true_price_polymarket",
    "DevigMethod",
    "devig",
    "devig_multiplicative",
    "consensus_fair",
]
