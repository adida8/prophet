"""WC 2026 — groups, bracket, per-team Elo.

Keys are the canonical participant names Polymarket uses for the winner
market (so the field aligns 1-to-1 with `Will <name> win the 2026 FIFA
World Cup?`). 12 groups × 4 teams = 48. Sourced from the FIFA group draw
(Dec 2025) cross-referenced with the actual qualifier list.

Elo values are approximate mid-2026 figures from eloratings.net. They
mirror the values in the match-model `elo_seed.py` for teams that exist
there, and add credible numbers for the qualifiers that don't (mostly
the new federation entrants under the 48-team format). Match-model
calibration drift is acceptable here: the MC sim's edge comes from the
bracket structure, not from a 20-point Elo gap on a longshot.

When the live Elo ingest lands (per the data-layer spec Phase 1b),
replace this with a lookup against that store and delete the constants.
"""

from __future__ import annotations

# 48 confirmed WC 2026 qualifiers, name → Elo (approximate, mid-2026).
TEAM_ELO: dict[str, float] = {
    # Top tier
    "Argentina":            2070.0,
    "France":               2050.0,
    "Spain":                2030.0,
    "Brazil":               2000.0,
    "England":              1990.0,
    "Germany":              1970.0,
    "Portugal":             1950.0,
    "Netherlands":          1940.0,
    # Tier 2 contenders
    "Croatia":              1900.0,
    "Belgium":              1880.0,
    "Uruguay":              1880.0,
    "Colombia":             1870.0,
    "Switzerland":          1840.0,
    "Mexico":               1830.0,
    "Morocco":              1830.0,
    "Czechia":              1830.0,
    "USA":                  1820.0,
    "Ecuador":              1810.0,
    "Japan":                1810.0,
    # Tier 3 — solid mid-table internationals
    "Norway":               1800.0,
    "Senegal":              1800.0,
    "Korea Republic":       1790.0,
    "IR Iran":              1780.0,
    "Türkiye":              1770.0,
    "Austria":              1750.0,
    "Sweden":               1730.0,
    "Algeria":              1730.0,
    "Paraguay":             1730.0,
    "Côte d'Ivoire":        1720.0,
    "Egypt":                1720.0,
    "Tunisia":              1720.0,
    "South Africa":         1700.0,
    "Ghana":                1700.0,
    "Scotland":             1700.0,
    "Bosnia and Herzegovina": 1700.0,
    "Australia":            1700.0,
    "Canada":               1700.0,
    "Uzbekistan":           1670.0,
    # Tier 4 — new-format entrants and weaker qualifiers
    "Jordan":               1620.0,
    "Panama":               1620.0,
    "Iraq":                 1620.0,
    "DR Congo":             1620.0,
    "New Zealand":          1620.0,
    "Saudi Arabia":         1620.0,
    "Qatar":                1600.0,
    "Cabo Verde":           1550.0,
    "Curaçao":              1530.0,
    "Haiti":                1530.0,
}


# 12 groups of 4, ordered A-L. Derived from the Dec 2025 draw and
# cross-referenced against Polymarket fixture adjacency in the
# current data set.
GROUPS: dict[str, tuple[str, ...]] = {
    "A": ("Australia",       "Paraguay",        "Türkiye",       "USA"),
    "B": ("Belgium",          "Egypt",           "IR Iran",       "New Zealand"),
    "C": ("Bosnia and Herzegovina", "Canada",     "Switzerland",   "Qatar"),
    "D": ("Brazil",           "Haiti",           "Morocco",       "Scotland"),
    "E": ("DR Congo",         "Colombia",        "Portugal",      "Uzbekistan"),
    "F": ("Côte d'Ivoire",    "Ecuador",         "Germany",       "Curaçao"),
    "G": ("Cabo Verde",       "Spain",           "Saudi Arabia",  "Uruguay"),
    "H": ("Czechia",          "Korea Republic",  "Mexico",        "South Africa"),
    "I": ("England",          "Ghana",           "Croatia",       "Panama"),
    "J": ("France",           "Iraq",            "Norway",        "Senegal"),
    "K": ("Japan",            "Netherlands",     "Sweden",        "Tunisia"),
    "L": ("Algeria",          "Argentina",       "Austria",       "Jordan"),
}


def field() -> tuple[str, ...]:
    """All 48 participants, group-ordered (A1 A2 A3 A4 B1 B2 ...)."""
    return tuple(t for grp in GROUPS.values() for t in grp)


def elo(team: str) -> float:
    """Elo lookup; defaults to 1500 for anything unknown so the sim
    never crashes on a market participant we don't have data for.
    """
    return TEAM_ELO.get(team, 1500.0)


def elo_is_stub(team: str) -> bool:
    """True when we don't have a real Elo entry for this team."""
    return team not in TEAM_ELO


# Knockout bracket — Round of 32 seeding for the 48-team format.
# Top 2 from each group + the 8 best third-placed teams qualify. Without
# the official FIFA cross-group bracket encoded, v1 uses a plausible
# seeded R32: winners cross-tied with the best third-place finishers,
# runners-up cross-tied internally. The simulator notes this as a
# simplification in §4 of the outrights spec — replace once the FIFA
# bracket is loaded.
#
# Slot codes:
#   "A1" / "A2" / "A3" = winner / runner-up / 3rd of Group A
#   "3RD-1" .. "3RD-8" = the 8 best 3rd-placed teams, ranked
#
# Each tuple is one R32 tie. 16 ties feed R16, then QF, SF, Final.
R32_TIES: tuple[tuple[str, str], ...] = (
    # Group winners vs the 8 best third-place finishers
    ("A1", "3RD-8"),
    ("B1", "3RD-7"),
    ("C1", "3RD-6"),
    ("D1", "3RD-5"),
    ("E1", "3RD-4"),
    ("F1", "3RD-3"),
    ("G1", "3RD-2"),
    ("H1", "3RD-1"),
    # Group runners-up cross-paired
    ("I2", "J2"),
    ("K2", "L2"),
    ("I1", "L1"),
    ("J1", "K1"),
    ("A2", "B2"),
    ("C2", "D2"),
    ("E2", "F2"),
    ("G2", "H2"),
)
