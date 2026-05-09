"""Backtest runner — top-level orchestrator behind `desk backtest`."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from desk.backtest.historical.markets import HistoricalMatch, load_tournament_matches
from desk.backtest.replay import SnapshotRow, Window, replay_tournament
from desk.backtest.tournaments import TOURNAMENTS, Tournament
from desk.backtest.writers import write_dashboard, write_xlsx

log = logging.getLogger("desk.backtest.runner")

ALL_WINDOWS: tuple[Window, ...] = ("T-38", "T-5", "T-1h", "KO")


def run_backtest(
    *,
    tournament_keys:  list[str],
    windows:          tuple[Window, ...] = ALL_WINDOWS,
    limit:            int | None = None,
    workbook_path:    Path,
    dashboard_path:   Path,
) -> dict:
    """Run the backtest. Returns a summary dict for the CLI to print."""
    all_matches:   list[HistoricalMatch] = []
    all_snapshots: list[SnapshotRow]      = []
    used_tours:    list[Tournament]       = []

    for key in tournament_keys:
        if key not in TOURNAMENTS:
            raise ValueError(f"unknown tournament key: {key!r}; "
                             f"known: {sorted(TOURNAMENTS)}")
        tour = TOURNAMENTS[key]
        used_tours.append(tour)

        matches = load_tournament_matches(tour)
        if limit is not None:
            matches = matches[:limit]
        log.info("%s: %d matches loaded", tour.key, len(matches))

        rows = replay_tournament(matches, tour=tour, windows=windows)
        all_matches.extend(matches)
        all_snapshots.extend(rows)

    # ── Persist ─────────────────────────────────────────────────────
    write_xlsx(
        workbook_path=workbook_path,
        matches=all_matches,
        snapshots=all_snapshots,
    )
    write_dashboard(
        dashboard_path=dashboard_path,
        snapshots=all_snapshots,
        competitions=[t.name for t in used_tours],
        run_date=date.today(),
    )

    # ── Headline metrics ────────────────────────────────────────────
    ko = [s for s in all_snapshots if s.window == "KO"]
    n  = max(len(ko), 1)
    mean_brier        = sum(s.brier        for s in ko) / n
    mean_market_brier = sum(s.market_brier for s in ko) / n
    state_counts = {"pick": 0, "pass": 0, "avoid": 0}
    for s in ko:
        state_counts[s.verdict_state] = state_counts.get(s.verdict_state, 0) + 1

    return {
        "tournaments":       [t.key for t in used_tours],
        "matches":           len(all_matches),
        "snapshots":         len(all_snapshots),
        "ko_snapshots":      len(ko),
        "mean_brier":        round(mean_brier, 4),
        "mean_market_brier": round(mean_market_brier, 4),
        "verdict_counts":    state_counts,
        "workbook":          str(workbook_path),
        "dashboard":         str(dashboard_path),
    }
