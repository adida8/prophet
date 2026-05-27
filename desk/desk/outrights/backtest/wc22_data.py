"""WC 2022 — groups, bracket, frozen-Elo team lookup, market reference.

Source of record for the WC22 backtest. Group draws + R16 bracket are
from FIFA's published 2022 World Cup data; Elo snapshot is the existing
desk/data/backtest/elo/intl/20221120.json (the night before kickoff);
canonical team names follow the same convention as the live WC26 path.

WC 2022 differs structurally from WC 2026:
  * 8 groups of 4 (vs 12 groups of 4 in 2026)
  * Top 2 of each group → R16 directly (vs top 2 + 8 best thirds → R32)
  * 16-team knockout bracket (vs 32-team in 2026)

Final result: Argentina lifted the trophy on 2022-12-18.

Pre-tournament market consensus (`MARKET_REFERENCE_P_WIN`) is an
*approximation* of major-book outright pricing circa 2022-11-19 — the
sum is >1.0 because of the natural book overround. Used by the
backtest only for relative-comparison context; not load-bearing for
scoring (which scores against the actual winner). Replace with
recovered Pinnacle / Polymarket closing snapshots when available.
"""

from __future__ import annotations

import json
from pathlib import Path

# Canonical team names follow the WC26 outright pipeline convention:
# display strings as they would appear in Polymarket's `Will <team>
# win the 2022 FIFA World Cup?` question shape. Elo is keyed by ISO3
# in `desk/data/backtest/elo/intl/20221120.json`.
TEAM_TO_ISO3: dict[str, str] = {
    "Argentina":           "arg",
    "Australia":           "aus",
    "Belgium":             "bel",
    "Brazil":              "bra",
    "Cameroon":            "cmr",
    "Canada":              "can",
    "Costa Rica":          "crc",
    "Croatia":             "cro",
    "Denmark":             "den",
    "Ecuador":             "ecu",
    "England":             "eng",
    "France":              "fra",
    "Germany":             "ger",
    "Ghana":               "gha",
    "IR Iran":             "irn",
    "Japan":               "jpn",
    "Korea Republic":      "kor",
    "Mexico":              "mex",
    "Morocco":             "mar",
    "Netherlands":         "ned",
    "Poland":              "pol",
    "Portugal":            "por",
    "Qatar":               "qat",
    "Saudi Arabia":        "ksa",
    "Senegal":             "sen",
    "Serbia":              "srb",
    "Spain":               "esp",
    "Switzerland":         "sui",
    "Tunisia":             "tun",
    "Uruguay":             "uru",
    "USA":                 "usa",
    "Wales":               "wal",
}


# WC 2022 actual groups — verified against FIFA's published draw.
GROUPS: dict[str, tuple[str, ...]] = {
    "A": ("Qatar",       "Ecuador",      "Senegal",        "Netherlands"),
    "B": ("England",     "IR Iran",      "USA",            "Wales"),
    "C": ("Argentina",   "Saudi Arabia", "Mexico",         "Poland"),
    "D": ("France",      "Australia",    "Denmark",        "Tunisia"),
    "E": ("Spain",       "Costa Rica",   "Germany",        "Japan"),
    "F": ("Belgium",     "Canada",       "Morocco",        "Croatia"),
    "G": ("Brazil",      "Serbia",       "Switzerland",    "Cameroon"),
    "H": ("Portugal",    "Ghana",        "Uruguay",        "Korea Republic"),
}


def field() -> tuple[str, ...]:
    """All 32 participants, group-ordered."""
    return tuple(t for grp in GROUPS.values() for t in grp)


# R16 bracket — FIFA's published cross-group assignments. Each tuple is
# one R16 tie; the simulator pairs winners 0-vs-1, 2-vs-3, … for QF →
# SF → Final after this round.
R16_TIES: tuple[tuple[str, str], ...] = (
    # Upper half
    ("A1", "B2"),    # NED vs USA
    ("C1", "D2"),    # ARG vs AUS
    ("E1", "F2"),    # ESP vs CRO  (Japan won E in actual; this is structure)
    ("G1", "H2"),    # BRA vs KOR
    # Lower half
    ("B1", "A2"),    # ENG vs SEN
    ("D1", "C2"),    # FRA vs POL
    ("F1", "E2"),    # BEL vs JPN  (Morocco won F in actual)
    ("H1", "G2"),    # POR vs SUI
)


# Actual final result.
TRUE_WINNER: str = "Argentina"


def wc22_structure():
    """Build the WC 2022 `TournamentStructure` from this module's data.

    Imported lazily to mirror `wc26_structure()` and avoid carrying
    the model import at module-load time.
    """
    from desk.outrights.model import TournamentStructure
    return TournamentStructure(
        groups=GROUPS,
        knockout_seeds=R16_TIES,
        qualifier_strategy="top2",
    )


# Pre-tournament market consensus — approximation of major-book outright
# pricing circa 2022-11-19 (Pinnacle + consensus). Sum exceeds 1.0 due
# to book overround. Used for relative comparison context in the
# backtest dashboard; not load-bearing for the Brier on the actual
# winner. Replace with recovered Pinnacle / Polymarket snapshots when
# available.
MARKET_REFERENCE_P_WIN: dict[str, float] = {
    "Brazil":      0.180,
    "France":      0.150,
    "Argentina":   0.120,
    "England":     0.120,
    "Spain":       0.105,
    "Germany":     0.090,
    "Netherlands": 0.080,
    "Portugal":    0.070,
    "Belgium":     0.060,
    "Denmark":     0.030,
    "Uruguay":     0.028,
    "Croatia":     0.025,
}


_ELO_PATH = (
    Path(__file__).resolve().parents[3]
    / "data" / "backtest" / "elo" / "intl" / "20221120.json"
)


def load_elo_lookup() -> dict[str, float]:
    """Return `{team_name → elo}` for the WC 2022 field, sourced from
    the frozen pre-tournament Elo snapshot.

    Teams with no entry in the snapshot fall back to 1500 (the rating
    floor `wc26_data.elo` also uses). On WC22, every participant has
    a real number — the fallback exists for forward-compatibility.
    """
    raw = json.loads(_ELO_PATH.read_text(encoding="utf-8"))
    elo_by_iso3: dict[str, float] = {
        k.lower(): float(v) for k, v in raw["elo"].items()
    }
    out: dict[str, float] = {}
    for team, iso3 in TEAM_TO_ISO3.items():
        # `sui` for Switzerland in the snapshot; matches our TEAM_TO_ISO3.
        out[team] = elo_by_iso3.get(iso3, 1500.0)
    return out
