"""Backtest harness — reads-only side workflow.

Provides a `desk backtest --tournament wc-2022` command that replays the
engine against historical fixtures and writes the result into
`desk_backtest.xlsx` and `desk_backtest_dashboard.html`.

Critical invariant: this package never imports from
`desk/sports/football/ingest/`. All historical data flows through
`desk/backtest/historical/`. That guarantees no test silently uses
today's Elo for a 2022 match.
"""

from desk.backtest.tournaments import TOURNAMENTS, Tournament  # noqa: F401
