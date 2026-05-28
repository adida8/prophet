"""UEFA Euro 2024 — groups, R16 bracket, frozen Elo, market reference.

Source of record for the Euro 2024 backtest. Group draws + R16
bracket are from UEFA's published Euro 2024 data (Wikipedia: "UEFA
Euro 2024 knockout stage"); Elo snapshot is at
desk/data/backtest/elo/intl/20240613.json (one day before kickoff);
canonical team names follow the same convention as the live WC26
path and the WC22 backtest.

Euro 2024 differs structurally from both WC variants:
  * 6 groups of 4 (vs 8 in WC22, 12 in WC26)
  * Top 2 of each group + 4 best 3rd-place teams → R16
  * 16-team knockout bracket (R16 → QF → SF → Final)
  * Constrained third-place slots like WC26 — each `3RD@{groups}`
    slot can only take a third from one of the listed groups, per
    UEFA's published table

Final result: Spain beat England 2-1 in the Berlin final on 2024-07-14.

Pre-tournament market consensus (`MARKET_REFERENCE_P_WIN`) is an
*approximation* of major-book pre-tournament odds circa 2024-06-13.
Sum exceeds 1.0 due to book overround. Used for relative-comparison
context in the backtest dashboard; not load-bearing for scoring.
"""

from __future__ import annotations

import json
from pathlib import Path

TEAM_TO_ISO3: dict[str, str] = {
    "Germany":         "ger",
    "Scotland":        "sco",
    "Hungary":         "hun",
    "Switzerland":     "sui",
    "Spain":           "esp",
    "Croatia":         "cro",
    "Italy":           "ita",
    "Albania":         "alb",
    "Slovenia":        "svn",
    "Denmark":         "den",
    "Serbia":          "srb",
    "England":         "eng",
    "Poland":          "pol",
    "Netherlands":     "ned",
    "Austria":         "aut",
    "France":          "fra",
    "Belgium":         "bel",
    "Slovakia":        "svk",
    "Romania":         "rom",
    "Ukraine":         "ukr",
    "Türkiye":         "tur",
    "Georgia":         "geo",
    "Portugal":        "por",
    "Czechia":         "cze",
}


# Euro 2024 groups — verified against UEFA's published draw.
GROUPS: dict[str, tuple[str, ...]] = {
    "A": ("Germany",     "Scotland",    "Hungary",     "Switzerland"),
    "B": ("Spain",       "Croatia",     "Italy",       "Albania"),
    "C": ("Slovenia",    "Denmark",     "Serbia",      "England"),
    "D": ("Poland",      "Netherlands", "Austria",     "France"),
    "E": ("Belgium",     "Slovakia",    "Romania",     "Ukraine"),
    "F": ("Türkiye",     "Georgia",     "Portugal",    "Czechia"),
}


def field() -> tuple[str, ...]:
    """All 24 participants, group-ordered."""
    return tuple(t for grp in GROUPS.values() for t in grp)


# R16 bracket — UEFA's published cross-group assignments. The
# constraint sets `3RD@{groups}` reflect the UEFA Euro 2024 third-
# place table (only thirds from listed groups can fill each slot).
#
# Bracket order matches the standard QF pairing: ties 0-vs-1, 2-vs-3,
# 4-vs-5, 6-vs-7 → QF1..QF4. QF winners pair in standard order
# (QF1+QF2 → SF1; QF3+QF4 → SF2; SF1+SF2 → Final).
R16_TIES: tuple[tuple[str, str], ...] = (
    # QF1 region
    ("B1",          "3RD@ADEF"),     # Match 1: 1B vs 3rd from {A,D,E,F}
    ("A1",          "C2"),           # Match 2: 1A vs 2C
    # QF2 region
    ("F1",          "3RD@ABC"),      # Match 3: 1F vs 3rd from {A,B,C}
    ("D2",          "E2"),           # Match 4: 2D vs 2E
    # QF3 region
    ("E1",          "3RD@ABCD"),     # Match 5: 1E vs 3rd from {A,B,C,D}
    ("D1",          "F2"),           # Match 6: 1D vs 2F
    # QF4 region
    ("C1",          "3RD@DEF"),      # Match 7: 1C vs 3rd from {D,E,F}
    ("A2",          "B2"),           # Match 8: 2A vs 2B
)


TRUE_WINNER: str = "Spain"


def euro_2024_structure():
    """Build the Euro 2024 `TournamentStructure` from this module's data."""
    from desk.outrights.model import TournamentStructure
    return TournamentStructure(
        groups=GROUPS,
        knockout_seeds=R16_TIES,
        qualifier_strategy="top2_plus_4_thirds",
    )


# Pre-tournament market consensus — approximation of major-book
# outright pricing circa 2024-06-13. Sum exceeds 1.0 due to overround.
MARKET_REFERENCE_P_WIN: dict[str, float] = {
    "France":      0.245,
    "England":     0.184,
    "Germany":     0.137,
    "Spain":       0.137,
    "Portugal":    0.111,
    "Italy":       0.062,
    "Netherlands": 0.057,
    "Belgium":     0.050,
    "Croatia":     0.020,
    "Denmark":     0.014,
    "Switzerland": 0.011,
}


_ELO_PATH = (
    Path(__file__).resolve().parents[3]
    / "data" / "backtest" / "elo" / "intl" / "20240613.json"
)


def load_elo_lookup() -> dict[str, float]:
    """Return `{team_name → elo}` for the Euro 2024 field, sourced from
    the frozen pre-tournament Elo snapshot."""
    raw = json.loads(_ELO_PATH.read_text(encoding="utf-8"))
    elo_by_iso3: dict[str, float] = {
        k.lower(): float(v) for k, v in raw["elo"].items()
    }
    out: dict[str, float] = {}
    for team, iso3 in TEAM_TO_ISO3.items():
        out[team] = elo_by_iso3.get(iso3, 1500.0)
    return out
