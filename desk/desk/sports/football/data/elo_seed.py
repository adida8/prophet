"""Seed Elo for international sides + a handful of clubs.

This is a frozen v1 snapshot — the live Wikipedia / ClubElo ingest
pipelines (see `ingest/elo_intl.py`, `ingest/elo_club.py`) replace these
values once they're online. Lookups fall back to a default when a team
hasn't been seeded yet, so the engine never crashes on an unfamiliar
fixture.

Numbers are approximate Elo as of mid-2026, sourced from public Elo
ratings (eloratings.net for nations, clubelo.com for clubs). Keep them
short — model accuracy comes from the live ingest, not this seed.
"""

from __future__ import annotations

DEFAULT_NATIONAL_ELO: float = 1500.0
DEFAULT_CLUB_ELO:     float = 1500.0

# Lowercase ISO3 → Elo
NATIONAL_ELO: dict[str, float] = {
    # Top tier
    "fra": 2050.0,
    "arg": 2070.0,
    "esp": 2030.0,
    "bra": 2000.0,
    "eng": 1990.0,
    "ger": 1970.0,
    "por": 1950.0,
    "ned": 1940.0,
    "ita": 1930.0,
    "bel": 1880.0,
    # Mid
    "usa": 1820.0,
    "mex": 1830.0,
    "cro": 1900.0,
    "uru": 1880.0,
    "col": 1870.0,
    "ecu": 1810.0,
    "sen": 1800.0,
    "mar": 1830.0,
    "jpn": 1810.0,
    "kor": 1790.0,
    "aus": 1760.0,
    "can": 1720.0,
    "qat": 1720.0,
    # Lower tier (WC 2026 contenders + altitude side for tests)
    "rsa": 1620.0,
    "alg": 1740.0,
    "cmr": 1730.0,
    "egy": 1730.0,
    "tun": 1670.0,
    "gha": 1660.0,
    "civ": 1740.0,
    "irn": 1750.0,
    "uzb": 1640.0,
    "ksa": 1640.0,
    "che": 1840.0,    # Switzerland
    "sui": 1840.0,    # alias
    "par": 1700.0,
    "ven": 1690.0,
    "bol": 1700.0,    # altitude side
    "cze": 1830.0,
    "srb": 1850.0,
    "bih": 1700.0,
    "isl": 1680.0,
    "wal": 1810.0,
}

# Club id (`{league}-{short}`) → Elo. Seed only the obvious top-tier
# clubs that show up in priced markets early; the live ingest populates
# the rest.
CLUB_ELO: dict[str, float] = {
    "epl-mun": 1810.0,    # Manchester United
    "epl-liv": 1880.0,    # Liverpool
    "epl-mci": 1990.0,    # Manchester City
    "epl-ars": 1940.0,    # Arsenal
    "epl-che": 1850.0,    # Chelsea
    "epl-tot": 1830.0,    # Tottenham
    "laliga-rma": 2000.0, # Real Madrid
    "laliga-bar": 1980.0, # Barcelona
    "bundesliga-bay": 1990.0,
    "bundesliga-bvb": 1860.0,
    "ligue1-psg": 1980.0,
}


def national_elo(iso3: str) -> float:
    return NATIONAL_ELO.get(iso3.lower(), DEFAULT_NATIONAL_ELO)


def club_elo(club_id: str) -> float:
    return CLUB_ELO.get(club_id.lower(), DEFAULT_CLUB_ELO)


# Lowercase ISO3 of nations whose senior teams we treat as
# altitude-acclimatised. Source: living above ~1500m as standard
# training environment.
ALTITUDE_ACCLIMATISED: set[str] = {"bol", "ecu", "col", "per", "mex"}


def is_altitude_acclimatised(iso3: str) -> bool:
    return iso3.lower() in ALTITUDE_ACCLIMATISED
