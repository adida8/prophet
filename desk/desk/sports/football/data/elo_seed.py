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

# Lowercase ISO3 → Elo. Audited 2026-05-19 against eloratings.net
# mid-2026 values. The data layer spec's Phase 1b replaces this with
# live ingest; this seed is the floor until that lands.
NATIONAL_ELO: dict[str, float] = {
    # Top tier
    "arg": 2140.0,
    "fra": 2030.0,
    "esp": 2010.0,
    "bra": 1970.0,
    "eng": 1950.0,
    "por": 1930.0,
    "ned": 1900.0,
    "ger": 1900.0,
    "ita": 1880.0,
    "bel": 1860.0,
    "cro": 1860.0,
    # Strong mid
    "col": 1870.0,
    "uru": 1850.0,
    "che": 1830.0,    # Switzerland
    "sui": 1830.0,    # alias
    "mex": 1830.0,
    "aut": 1830.0,
    "den": 1830.0,
    "usa": 1810.0,
    "mar": 1820.0,
    "srb": 1810.0,
    "sen": 1790.0,
    "ecu": 1790.0,
    "jpn": 1790.0,
    "kor": 1770.0,
    "egy": 1760.0,
    "nor": 1760.0,
    "alg": 1750.0,
    "tur": 1750.0,
    "sco": 1750.0,
    "nga": 1750.0,
    "aus": 1740.0,
    "irn": 1740.0,
    "cze": 1740.0,
    "civ": 1720.0,
    "ven": 1730.0,
    "par": 1730.0,
    "wal": 1730.0,
    "pol": 1730.0,
    "irl": 1700.0,
    "chi": 1700.0,
    # Co-hosts (qualified, Elo above pre-2024 reads)
    "can": 1860.0,
    # Lower tier
    "rou": 1690.0,
    "mli": 1690.0,
    "cmr": 1670.0,
    "isl": 1670.0,
    "tun": 1650.0,
    "ksa": 1650.0,
    "ghu": 1620.0,    # safety alias
    "gha": 1620.0,
    "rsa": 1620.0,
    "crc": 1620.0,
    "cod": 1620.0,    # DR Congo
    "qat": 1640.0,
    "bol": 1640.0,    # altitude side
    "uzb": 1610.0,
    "swe": 1660.0,
    "fin": 1660.0,
    "per": 1660.0,
    "bih": 1660.0,
    "nir": 1610.0,
    "pan": 1560.0,
    "cpv": 1540.0,    # Cabo Verde
    "irq": 1540.0,
    "jor": 1530.0,
    "jam": 1530.0,
    "nzl": 1550.0,
    "hon": 1490.0,
    "cuw": 1480.0,    # Curaçao
    "hai": 1450.0,
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


def national_elo_source(iso3: str) -> str:
    """Source provenance for the national-Elo lookup.

    Returns "wiki" if the seed table covers this team (real Wikipedia
    data module value), "stub" if we fell back to the default.
    PR 4.5: the verdict step refuses to issue Picks when either side
    is "stub".
    """
    return "wiki" if iso3.lower() in NATIONAL_ELO else "stub"


def club_elo_source(club_id: str) -> str:
    """Source provenance for the club-Elo lookup. v1.1 swaps in live ClubElo."""
    return "clubelo" if club_id.lower() in CLUB_ELO else "stub"


# Lowercase ISO3 of nations whose senior teams we treat as
# altitude-acclimatised. Source: living above ~1500m as standard
# training environment.
ALTITUDE_ACCLIMATISED: set[str] = {"bol", "ecu", "col", "per", "mex"}


def is_altitude_acclimatised(iso3: str) -> bool:
    return iso3.lower() in ALTITUDE_ACCLIMATISED
