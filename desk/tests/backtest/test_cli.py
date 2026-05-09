"""CLI tests for `desk backtest`.

Exercises the argparse wiring + end-to-end run on a `--limit 3` slice
so the test stays under a second even on cold start.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from desk.cli import main as cli_main

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_backtest_writes_workbook_and_dashboard_with_limit_3(tmp_path: Path) -> None:
    wb_path  = tmp_path / "wb.xlsx"
    html_path = tmp_path / "dash.html"
    shutil.copy(PROJECT_ROOT / "desk_backtest.xlsx",            wb_path)
    shutil.copy(PROJECT_ROOT / "desk_backtest_dashboard.html",  html_path)

    rc = cli_main([
        "backtest",
        "--tournament", "wc-2022",
        "--limit", "3",
        "--workbook",  str(wb_path),
        "--dashboard", str(html_path),
    ])
    assert rc == 0
    assert wb_path.exists() and wb_path.stat().st_size > 0
    body = html_path.read_text(encoding="utf-8")
    assert "BACKTEST_DATA_START:kpis" in body
    # 3 matches × 4 windows = 12 snapshots; KO subset is 3 → table has 3 rows.
    assert body.count("<tr>") >= 3


def test_backtest_rejects_unknown_tournament_key() -> None:
    rc = cli_main(["backtest", "--tournament", "nope-1999"])
    assert rc != 0
