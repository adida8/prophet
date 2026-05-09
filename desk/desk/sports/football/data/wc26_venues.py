"""WC 2026 venues — the 16 host stadiums and their altitudes.

Hard-coded for PR 3 because (a) the data is small, (b) FIFA published
the final venue list in 2024, and (c) the cost of getting it wrong is
zero — Polymarket already names the venue in `endDate` metadata only,
not in the gamma payload, so this is the engine's source of truth.

Altitude in metres above sea level — used for the altitude bonus.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WC26Venue:
    city:          str
    stadium:       str
    country_iso2:  str    # ISO 3166-1 alpha-2 — for the published `venue.country`
    country_iso3:  str    # ISO3 — for host-bonus comparison against team_iso3
    altitude_m:    float


# Keyed by stadium short slug — what we'll match on once FIFA-metadata
# parsing wires up.
WC26_VENUES: dict[str, WC26Venue] = {
    # USA — 11 host venues
    "metlife":        WC26Venue("East Rutherford",  "MetLife Stadium",         "US", "usa", 8.0),
    "sofi":           WC26Venue("Inglewood",        "SoFi Stadium",            "US", "usa", 35.0),
    "atlanta":        WC26Venue("Atlanta",          "Mercedes-Benz Stadium",   "US", "usa", 320.0),
    "arrowhead":      WC26Venue("Kansas City",      "Arrowhead Stadium",       "US", "usa", 230.0),
    "att":            WC26Venue("Arlington",        "AT&T Stadium",            "US", "usa", 175.0),
    "lincoln":        WC26Venue("Philadelphia",     "Lincoln Financial Field", "US", "usa", 11.0),
    "lumen":          WC26Venue("Seattle",          "Lumen Field",             "US", "usa", 52.0),
    "geha":           WC26Venue("Foxborough",       "Gillette Stadium",        "US", "usa", 80.0),
    "hardrock":       WC26Venue("Miami Gardens",    "Hard Rock Stadium",       "US", "usa", 3.0),
    "nrg":            WC26Venue("Houston",          "NRG Stadium",             "US", "usa", 16.0),
    "levi":           WC26Venue("Santa Clara",      "Levi's Stadium",          "US", "usa", 13.0),
    # Canada
    "bmo":            WC26Venue("Toronto",          "BMO Field",               "CA", "can", 75.0),
    "bcplace":        WC26Venue("Vancouver",        "BC Place",                "CA", "can", 5.0),
    # Mexico
    "azteca":         WC26Venue("Mexico City",      "Estadio Azteca",          "MX", "mex", 2240.0),
    "akron":          WC26Venue("Guadalajara",      "Estadio Akron",           "MX", "mex", 1530.0),
    "monterrey":      WC26Venue("Monterrey",        "Estadio BBVA",            "MX", "mex", 540.0),
}


# Host list per spec §4 PR 3. WC 2026 hosts are USA / CAN / MEX.
WC26_HOST_ISO3: set[str] = {"usa", "can", "mex"}


def venue_by_stadium_name(name: str) -> WC26Venue | None:
    """Loose match by stadium common name."""
    target = name.strip().lower()
    for v in WC26_VENUES.values():
        if v.stadium.lower() == target:
            return v
    return None


def venue_by_slug(slug: str) -> WC26Venue | None:
    return WC26_VENUES.get(slug)
