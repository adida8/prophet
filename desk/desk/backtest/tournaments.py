"""Tournament configuration for the backtest harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tournament:
    """A historical tournament we can replay."""
    key:                  str    # CLI key, e.g. "wc-2022"
    name:                 str    # human-readable
    competition:          str    # short code: "wc" / "euro" / "cma"
    season:               str    # year(s)
    asof_elo_snapshot:    str    # YYYYMMDD — pre-tournament Elo file under data/backtest/elo/intl/
    footballdata_path:    str | None = None    # legacy URL fragment if football-data.co.uk had it
    manual_csv_basename:  str = ""             # filename under data/backtest/manual/


TOURNAMENTS: dict[str, Tournament] = {
    "wc-2022": Tournament(
        key="wc-2022",
        name="FIFA World Cup 2022",
        competition="wc",
        season="2022",
        asof_elo_snapshot="20221120",
        # football-data.co.uk doesn't actually publish WC 2022 — confirmed via
        # 404 / homepage-fallback probing 2026-05-09. Manual CSV is canonical.
        footballdata_path=None,
        manual_csv_basename="wc_2022.csv",
    ),
    # NOTE: Euro 2024 + Copa 2024 wired in a follow-up. The harness is
    # tournament-agnostic — adding either is just a new entry here plus
    # the matching CSV under data/backtest/manual/.
}
