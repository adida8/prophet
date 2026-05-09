"""Verdict — sport-agnostic. Operates on probabilities and market prices.

Public surface:
    decide(model, market, sides) → Verdict (the contract one)
    Thresholds                   — read-once constants (override via .env)
    MarketSnapshot, VenuePrice   — the input shape from ingest

The verdict step never imports from `sports/football/`. Football's
feature builder produces a `ModelOutput`; the verdict treats it as
opaque probabilities.
"""

from desk.verdict.compare import MarketSnapshot, VenuePrice  # noqa: F401
from desk.verdict.decide import decide                        # noqa: F401
from desk.verdict.thresholds import Thresholds                # noqa: F401
