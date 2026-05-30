"""Locked launch venue set + venue-type classification.

Anywhere code reaches "is this venue a book or an exchange?", it goes
through this module — keeps the dispatch tables in one place so adding
the next exchange (Smarkets? Matchbook?) is a one-line edit.

The Odds API uses lowercase bookmaker keys (`pinnacle`,
`betfair_ex_uk`, `williamhill`, `skybet`). Polymarket is not on The
Odds API but lives in the same lookup so cross-venue code can ask one
table.
"""

from __future__ import annotations

from typing import Mapping

from desk.pricing.cost import VenueType


# Order matters: render order on the UI mirrors this list (sharp anchor
# first, then exchange, then consumer books, then prediction market).
LAUNCH_VENUE_IDS: tuple[str, ...] = (
    "pinnacle",
    "betfair_ex_uk",
    "betfair_ex_eu",
    "williamhill",
    "skybet",
    "polymarket",
)


VENUE_DISPLAY_NAMES: Mapping[str, str] = {
    "pinnacle":      "Pinnacle",
    "betfair_ex_uk": "Betfair Exchange (UK)",
    "betfair_ex_eu": "Betfair Exchange (EU)",
    "williamhill":   "William Hill",
    "skybet":        "Sky Bet",
    "polymarket":    "Polymarket",
}


VENUE_TYPES: Mapping[str, VenueType] = {
    "pinnacle":      VenueType.SPORTSBOOK,
    "williamhill":   VenueType.SPORTSBOOK,
    "skybet":        VenueType.SPORTSBOOK,
    "betfair_ex_uk": VenueType.EXCHANGE,
    "betfair_ex_eu": VenueType.EXCHANGE,
    "polymarket":    VenueType.PREDICTION_MARKET,
}


VENUE_REGIONS: Mapping[str, str] = {
    "pinnacle":      "eu",
    "betfair_ex_uk": "uk",
    "betfair_ex_eu": "eu",
    "williamhill":   "uk",
    "skybet":        "uk",
    "polymarket":    "global",
}


def venue_type_for(venue_id: str) -> VenueType:
    """Lookup venue type or raise. Callers should only ever ask about
    venues we know about — unknown venue == ingest bug we want to find."""
    try:
        return VENUE_TYPES[venue_id]
    except KeyError as e:
        raise KeyError(
            f"unknown venue_id {venue_id!r}; "
            f"known: {sorted(VENUE_TYPES.keys())}"
        ) from e


def venue_region(venue_id: str) -> str:
    """ISO-ish region code (`uk`, `eu`, `global`) or "?" if unknown."""
    return VENUE_REGIONS.get(venue_id, "?")
