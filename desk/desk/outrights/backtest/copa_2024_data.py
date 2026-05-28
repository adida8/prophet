"""CONMEBOL Copa América 2024 — groups, QF bracket, frozen Elo, market ref.

Source of record for the Copa 2024 backtest. Smallest tournament shape
in the suite: 16 teams, 4 groups of 4, top 2 → QF directly (no R16,
no constrained thirds).

Final result: Argentina beat Colombia 1-0 in the Miami Gardens final
on 2024-07-14 (extra time).

Pre-tournament market consensus is an *approximation* of major-book
pricing circa 2024-06-19. Argentina was a heavy pre-tournament
favourite (reigning World Champions); the market priced them at
~35-40% to repeat.
"""

from __future__ import annotations

import json
from pathlib import Path

TEAM_TO_ISO3: dict[str, str] = {
    "Argentina":     "arg",
    "Peru":          "per",
    "Chile":         "chi",
    "Canada":        "can",
    "Mexico":        "mex",
    "Ecuador":       "ecu",
    "Venezuela":     "ven",
    "Jamaica":       "jam",
    "USA":           "usa",
    "Uruguay":       "uru",
    "Panama":        "pan",
    "Bolivia":       "bol",
    "Brazil":        "bra",
    "Colombia":      "col",
    "Paraguay":      "par",
    "Costa Rica":    "cri",
}


GROUPS: dict[str, tuple[str, ...]] = {
    "A": ("Argentina",   "Peru",       "Chile",        "Canada"),
    "B": ("Mexico",      "Ecuador",    "Venezuela",    "Jamaica"),
    "C": ("USA",         "Uruguay",    "Panama",       "Bolivia"),
    "D": ("Brazil",      "Colombia",   "Paraguay",     "Costa Rica"),
}


def field() -> tuple[str, ...]:
    """All 16 participants, group-ordered."""
    return tuple(t for grp in GROUPS.values() for t in grp)


# Standard cross-group QF pairing — top of A vs runner-up of B, etc.
# 4 ties → SF → Final. Standard "consecutive winners pair" bracket
# (QF1 vs QF2 → SF1; QF3 vs QF4 → SF2).
QF_TIES: tuple[tuple[str, str], ...] = (
    ("A1", "B2"),
    ("B1", "A2"),
    ("C1", "D2"),
    ("D1", "C2"),
)


TRUE_WINNER: str = "Argentina"


def copa_2024_structure():
    """Build the Copa 2024 `TournamentStructure` from this module's data."""
    from desk.outrights.model import TournamentStructure
    return TournamentStructure(
        groups=GROUPS,
        knockout_seeds=QF_TIES,
        qualifier_strategy="top2",
    )


# Pre-tournament market consensus — approximation of major-book pricing
# circa 2024-06-19. Argentina was a heavy favourite (reigning WC22
# winners + most of the squad intact); Brazil + Uruguay rounded out
# the contender tier.
MARKET_REFERENCE_P_WIN: dict[str, float] = {
    "Argentina":  0.380,
    "Brazil":     0.200,
    "Uruguay":    0.100,
    "Colombia":   0.080,
    "Mexico":     0.050,
    "USA":        0.045,
    "Ecuador":    0.035,
    "Chile":      0.030,
    "Paraguay":   0.020,
    "Venezuela":  0.018,
    "Peru":       0.015,
    "Canada":     0.015,
}


_ELO_PATH = (
    Path(__file__).resolve().parents[3]
    / "data" / "backtest" / "elo" / "intl" / "20240619.json"
)


def load_elo_lookup() -> dict[str, float]:
    """Return `{team_name → elo}` for the Copa 2024 field."""
    raw = json.loads(_ELO_PATH.read_text(encoding="utf-8"))
    elo_by_iso3: dict[str, float] = {
        k.lower(): float(v) for k, v in raw["elo"].items()
    }
    out: dict[str, float] = {}
    for team, iso3 in TEAM_TO_ISO3.items():
        out[team] = elo_by_iso3.get(iso3, 1500.0)
    return out
