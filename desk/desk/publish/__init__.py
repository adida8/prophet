"""Publish — Pydantic contract, static-file writer, ETag helper.

The output contract is the only thing Faktor sees. Treat it as a public API.
"""

from desk.publish.contract import (  # noqa: F401
    Citation,
    Competition,
    Copy,
    DeployRegion,
    MarketPriceRow,
    MarketPriceVenue,
    MarketSource,
    MarketVenue,
    MatchOutput,
    MatchOutputIndexEntry,
    OutputIndex,
    Venue,
    VenueType,
    Verdict,
    VerdictState,
)
from desk.publish.etag import content_etag  # noqa: F401
from desk.publish.market_prices import (  # noqa: F401
    build_consensus_fair,
    build_market_prices,
)
from desk.publish.writer import Publisher  # noqa: F401
