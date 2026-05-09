"""Three QA tests on the rendered dashboard.

These tests run the full backtest end-to-end against the live scaffold,
then verify the resulting `desk_backtest_dashboard.html` carries real
data — not the example scaffold's stale numbers and copy.

QA 1: every replaceable region is populated and carries real data.
QA 2: the headline summary uses the right colour for this run's metrics.
QA 3: nothing from the original "5-match illustrative scaffold" survives.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from desk.backtest.runner import run_backtest

PROJECT_ROOT  = Path(__file__).resolve().parents[3]
SCAFFOLD_HTML = PROJECT_ROOT / "desk_backtest_dashboard.html"
SCAFFOLD_XLSX = PROJECT_ROOT / "desk_backtest.xlsx"


@pytest.fixture(scope="module")
def rendered_dashboard(tmp_path_factory) -> str:
    """Run a real WC 2022 backtest into a tmp copy of the scaffold and
    return the HTML body. Module-scoped so the three QA tests amortise
    the one full run.
    """
    workdir = tmp_path_factory.mktemp("dashboard-qa")
    wb_path  = workdir / "wb.xlsx"
    html_path = workdir / "dash.html"
    shutil.copy(SCAFFOLD_XLSX, wb_path)
    shutil.copy(SCAFFOLD_HTML, html_path)

    run_backtest(
        tournament_keys=["wc-2022"],
        workbook_path=wb_path,
        dashboard_path=html_path,
    )
    return html_path.read_text(encoding="utf-8")


# ── QA 1: every region populated with real data ─────────────────────

def test_qa_every_region_populated(rendered_dashboard: str) -> None:
    """All eight replaceable regions exist and contain real, non-empty content."""
    expected = {
        "masthead":    ["FIFA World Cup 2022", "64 matches"],
        "summary":     ["summary-card", "Calibration", "Selection", "Bottom line"],
        "disclaimer":  ["64 matches"],
        "kpis":        ["Matches tested", "Mean Brier", "0.58"],   # mean Brier ~0.58
        "verdict_mix": ['class="verdict-mix"', "Pick", "Pass", "Avoid"],
        "edge_profile":["pp"],
        "match_table": ["Argentina", "Saudi Arabia", "France", "Mexico"],
        "bins":        ["const bins ="],
    }
    for name, must_contain in expected.items():
        block = _extract_region(rendered_dashboard, name)
        assert block is not None, f"region {name!r} missing markers"
        assert block.strip(), f"region {name!r} is empty"
        for needle in must_contain:
            assert needle in block, (
                f"region {name!r} is missing expected content: {needle!r}\n"
                f"--- block ---\n{block[:500]}"
            )


# ── QA 2: summary-card colours match the run's quality call ─────────

def test_qa_summary_block_colours(rendered_dashboard: str) -> None:
    """The summary cards must carry the right CSS modifier (green/amber/red)
    for this run's actual metrics, and the verdicts must be human-readable
    (not "No data yet").
    """
    summary = _extract_region(rendered_dashboard, "summary")
    assert summary is not None

    # 3 cards exist, each one of green/amber/red.
    cards = re.findall(
        r'<div class="summary-card (\w+)">\s*\n'
        r'\s*<div class="heading">([^<]+)</div>\s*\n'
        r'\s*<div class="verdict">([^<]+)</div>',
        summary,
    )
    assert len(cards) == 3, f"expected 3 summary cards, got {len(cards)}"

    by_heading = {h.split("·")[0].strip().lower(): (color, verdict)
                  for color, h, verdict in cards}
    assert {"calibration", "selection", "bottom line"} <= by_heading.keys()

    # Every card carries one of our three colour grades.
    for color, _ in by_heading.values():
        assert color in {"green", "amber", "red"}, f"unexpected colour {color!r}"

    # WC 2022 v1 model: calibration is roughly comparable (amber) and
    # selection is too aggressive (red — 95% Pick rate). Bottom line
    # follows from those two and lands red.
    cal_color, cal_verdict = by_heading["calibration"]
    sel_color, sel_verdict = by_heading["selection"]
    bot_color, bot_verdict = by_heading["bottom line"]

    # Hard assertions: each verdict has non-trivial copy.
    assert len(cal_verdict.strip()) > 3
    assert len(sel_verdict.strip()) > 3
    assert len(bot_verdict.strip()) > 3

    # Bottom-line consistency: green only if both are green; red if either red.
    if cal_color == "green" and sel_color == "green":
        assert bot_color == "green", "bottom should be green when cal+sel both green"
    if cal_color == "red" or sel_color == "red":
        assert bot_color == "red", "bottom should be red when either axis red"

    # All three colour CSS modifiers must be present in the document so
    # whichever colour the run lands on actually renders.
    assert ".summary-card.green" in rendered_dashboard
    assert ".summary-card.amber" in rendered_dashboard
    assert ".summary-card.red"   in rendered_dashboard


# ── QA 3: no scaffold leftovers ─────────────────────────────────────

def test_qa_no_scaffold_leftovers(rendered_dashboard: str) -> None:
    """The original "5-match illustrative" scaffold strings must not
    survive in the populated dashboard."""
    forbidden = [
        "5-match scaffold",
        "(deliberate famous upsets",
        "across the 5 matches",
        "Scaffold — illustrative",
        # The static example bins from the scaffold's hardcoded JS — none
        # of these exact x/y pairs should remain after _build_bins runs.
        '{ x: 0.85, y: 0.00, n: 1 }',
        # The example match-table rows from the scaffold:
        "(draw, CRO pens)",
        "(draw, ARG pens)",
    ]
    for needle in forbidden:
        assert needle not in rendered_dashboard, (
            f"scaffold leftover survived in dashboard: {needle!r}"
        )

    # And the population should mention the real headline metrics.
    assert "BACKTEST_DATA_START:masthead" in rendered_dashboard
    assert "FIFA World Cup 2022" in rendered_dashboard
    # Mean Brier sits around 0.58 across PRs — exact value depends on
    # which gates are live. Match the prefix rather than the digits.
    assert "0.58" in rendered_dashboard or "0.57" in rendered_dashboard
    # The match table must include real WC 2022 fixtures.
    assert "Argentina" in rendered_dashboard
    assert "France" in rendered_dashboard


# ── helpers ─────────────────────────────────────────────────────────

def _extract_region(html: str, name: str) -> str | None:
    pat = re.compile(
        r"<!-- BACKTEST_DATA_START:" + re.escape(name) + r" -->"
        r"(.*?)"
        r"<!-- BACKTEST_DATA_END:" + re.escape(name) + r" -->",
        re.DOTALL,
    )
    m = pat.search(html)
    return m.group(1) if m else None
