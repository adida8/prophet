"""Historical match + closing-odds loader.

Reads from one of two places per tournament:

1. `desk/data/backtest/manual/{file}.csv` — hand-curated. Expected for
   tournaments football-data.co.uk doesn't publish (most internationals).
2. football-data.co.uk historical CSV — fallback, currently unused for
   the WC 2022 / Euro 2024 / Copa 2024 set because their international
   coverage stops at 2018.

Every CSV row carries match identity, kickoff, final score, and the
closing odds we'll compare the engine's verdict against.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from desk.backtest.tournaments import Tournament

log = logging.getLogger("desk.backtest.historical.markets")

_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data" / "backtest"
)


@dataclass(frozen=True)
class HistoricalMatch:
    """Full record for one historical match."""
    match_id:        str
    tournament:      str            # human-readable, e.g. "FIFA World Cup 2022"
    competition:     str            # short code, e.g. "wc"
    season:          str            # e.g. "2022"
    stage:           str            # "Group A" / "Quarter-final" / etc.
    kickoff_utc:     datetime
    team_a:          str
    team_a_iso3:     str
    team_b:          str
    team_b_iso3:     str
    venue_city:      str
    venue_country:   str            # ISO-2
    venue_altitude_m: float
    goals_a:         int
    goals_b:         int
    winner_90min:    str            # "a" / "b" / "draw"
    close_a:         float          # decimal odds
    close_draw:      float
    close_b:         float
    close_source:    str

    # Implied closing-market probabilities, devigged by simple normalisation.
    @property
    def market_p_a(self) -> float:
        return self._devig()[0]

    @property
    def market_p_draw(self) -> float:
        return self._devig()[1]

    @property
    def market_p_b(self) -> float:
        return self._devig()[2]

    def _devig(self) -> tuple[float, float, float]:
        a, d, b = 1.0 / self.close_a, 1.0 / self.close_draw, 1.0 / self.close_b
        s = a + d + b
        return (a / s, d / s, b / s)


def _parse_csv_row(row: dict, tour: Tournament) -> Optional[HistoricalMatch]:
    try:
        return HistoricalMatch(
            match_id=row["match_id"].strip(),
            tournament=tour.name,
            competition=tour.competition,
            season=tour.season,
            stage=row.get("stage", "").strip(),
            kickoff_utc=datetime.fromisoformat(row["kickoff_utc"].replace("Z", "+00:00")).astimezone(timezone.utc),
            team_a=row["team_a"].strip(),
            team_a_iso3=row["team_a_iso3"].strip().lower(),
            team_b=row["team_b"].strip(),
            team_b_iso3=row["team_b_iso3"].strip().lower(),
            venue_city=row.get("venue_city", "").strip(),
            venue_country=row.get("venue_country", "").strip().upper(),
            venue_altitude_m=float(row.get("venue_altitude_m") or 0),
            goals_a=int(row["goals_a"]),
            goals_b=int(row["goals_b"]),
            winner_90min=row["winner_90min"].strip().lower(),
            close_a=float(row["close_a"]),
            close_draw=float(row["close_draw"]),
            close_b=float(row["close_b"]),
            close_source=row.get("close_source", "").strip(),
        )
    except (KeyError, ValueError) as e:
        log.warning("skipping malformed row %s: %s", row.get("match_id"), e)
        return None


def load_tournament_matches(tour: Tournament) -> list[HistoricalMatch]:
    """Load every match for the given tournament.

    Manual CSV is preferred; football-data.co.uk fallback is left here as
    a placeholder for the future when their international archive returns.
    """
    if tour.manual_csv_basename:
        path = _DATA_DIR / "manual" / tour.manual_csv_basename
        if not path.exists():
            raise FileNotFoundError(
                f"manual CSV not found: {path}. Tournaments without a "
                "football-data.co.uk URL must ship a curated CSV."
            )
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        out = [m for m in (_parse_csv_row(r, tour) for r in rows) if m is not None]
        log.info("loaded %d matches from manual CSV %s", len(out), path.name)
        return out

    raise NotImplementedError(
        f"tournament {tour.key} has no manual CSV and no live "
        "football-data.co.uk URL wired (their archive lacks international "
        "coverage; see brief §3.1 manual-fallback path)"
    )
