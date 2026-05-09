"""HTML dashboard writer.

Read the existing `desk_backtest_dashboard.html`, find the
`<!-- BACKTEST_DATA_START -->` / `<!-- BACKTEST_DATA_END -->` markers
inside each replaceable region, and swap their bodies with values
computed from the SnapshotRow array.

If the markers don't exist yet (old scaffold), this writer adds them
on first run and persists.

Replaced regions:

  1. Masthead subtitle + "Scaffold" badge → real status line
  2. Disclaimer banner                     → run-date + competition list
  3. KPI strip                             → 5 boxes computed from snapshots
  4. Reliability bins JS                   → real bin data
  5. Match-by-match table                  → one row per KO snapshot
  6. Verdict mix bars + edge profile       → computed counts and pp values
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from desk.backtest.replay import SnapshotRow

log = logging.getLogger("desk.backtest.writers.dashboard")

# ── Region markers ────────────────────────────────────────────────────

START_TPL = "<!-- BACKTEST_DATA_START:{name} -->"
END_TPL   = "<!-- BACKTEST_DATA_END:{name} -->"

REGIONS = ("masthead", "disclaimer", "kpis", "verdict_mix", "edge_profile",
           "match_table", "bins")


def _between(name: str) -> re.Pattern:
    return re.compile(
        re.escape(START_TPL.format(name=name))
        + r".*?"
        + re.escape(END_TPL.format(name=name)),
        re.DOTALL,
    )


def _wrap(name: str, body: str) -> str:
    return f"{START_TPL.format(name=name)}\n{body}\n{END_TPL.format(name=name)}"


# ── Region builders ───────────────────────────────────────────────────

def _ko_only(snapshots: Iterable[SnapshotRow]) -> list[SnapshotRow]:
    return [s for s in snapshots if s.window == "KO"]


def _build_masthead(*, run_date: date, competitions: list[str], n_matches: int) -> str:
    comps = " · ".join(competitions) if competitions else "—"
    return (
        f'    <div>\n'
        f'      <h1>The Desk · Backtest</h1>\n'
        f'      <div class="subtitle">{html.escape(comps)} · {n_matches} matches · '
        f'generated {run_date.isoformat()}</div>\n'
        f'    </div>\n'
        f'    <div class="badge">Backtest · live</div>'
    )


def _build_disclaimer(*, run_date: date, competitions: list[str], n_matches: int) -> str:
    comps = ", ".join(competitions) if competitions else "—"
    return (
        f'    <strong>Status:</strong> backtest run {run_date.isoformat()} across '
        f'{n_matches} matches from {html.escape(comps)}. Closing-line baseline: '
        f'hand-curated approximation derived from public Pinnacle archives '
        f'(football-data.co.uk does not publish post-2018 international CSVs). '
        f'Late-binding injury features are stubbed in this v1 backtest — '
        f'features at T−3 and T−1h reuse the T−5 set.'
    )


def _build_kpis(snapshots: list[SnapshotRow]) -> str:
    ko = _ko_only(snapshots)
    if not ko:
        return ""
    n = len(ko)

    mean_brier        = sum(s.brier        for s in ko) / n
    mean_market_brier = sum(s.market_brier for s in ko) / n

    state_counts = {"pick": 0, "pass": 0, "avoid": 0}
    for s in ko:
        state_counts[s.verdict_state] = state_counts.get(s.verdict_state, 0) + 1

    pick_rows = [s for s in ko if s.verdict_state == "pick"]
    mean_edge = (sum((s.verdict_edge_pp or 0) for s in pick_rows) / len(pick_rows)) if pick_rows else 0.0

    hits = 0
    for s in pick_rows:
        if s.verdict_side is None:
            continue
        if s.verdict_side == "draw" and s.actual_draw == 1:
            hits += 1
        elif s.verdict_side == s.team_a and s.actual_a == 1:
            hits += 1
        elif s.verdict_side == s.team_b and s.actual_b == 1:
            hits += 1

    return f'''    <div class="kpi">
      <div class="label">Matches tested</div>
      <div class="value">{n}</div>
      <div class="unit">KO snapshots</div>
    </div>
    <div class="kpi">
      <div class="label">Mean Brier · model</div>
      <div class="value">{mean_brier:.3f}</div>
      <div class="unit">closing-market: {mean_market_brier:.3f}</div>
    </div>
    <div class="kpi">
      <div class="label">Verdicts issued</div>
      <div class="value">{n}</div>
      <div class="unit">{state_counts.get("pick", 0)} Pick · {state_counts.get("pass", 0)} Pass · {state_counts.get("avoid", 0)} Avoid</div>
    </div>
    <div class="kpi">
      <div class="label">Mean edge on Picks</div>
      <div class="value">{mean_edge:+.1f}</div>
      <div class="unit">percentage points</div>
    </div>
    <div class="kpi">
      <div class="label">Pick hit rate</div>
      <div class="value">{hits}/{len(pick_rows)}</div>
      <div class="unit">90′ outcomes</div>
    </div>'''


def _build_verdict_mix(snapshots: list[SnapshotRow]) -> str:
    ko = _ko_only(snapshots)
    n = max(len(ko), 1)
    counts = {"pick": 0, "pass": 0, "avoid": 0}
    for s in ko:
        counts[s.verdict_state] = counts.get(s.verdict_state, 0) + 1
    return f'''          <div class="row">
            <div class="label">Pick</div>
            <div class="bar-track"><div class="bar-fill" style="width: {counts["pick"]*100/n:.0f}%;"></div></div>
            <div class="count">{counts["pick"]}</div>
          </div>
          <div class="row">
            <div class="label">Pass</div>
            <div class="bar-track"><div class="bar-fill pass" style="width: {counts["pass"]*100/n:.0f}%;"></div></div>
            <div class="count">{counts["pass"]}</div>
          </div>
          <div class="row">
            <div class="label">Avoid</div>
            <div class="bar-track"><div class="bar-fill avoid" style="width: {counts["avoid"]*100/n:.0f}%;"></div></div>
            <div class="count">{counts["avoid"]}</div>
          </div>'''


def _build_edge_profile(snapshots: list[SnapshotRow]) -> str:
    """Top-5 picks by absolute edge."""
    picks = sorted(
        (s for s in _ko_only(snapshots) if s.verdict_state == "pick"),
        key=lambda s: abs(s.verdict_edge_pp or 0), reverse=True,
    )[:8]
    if not picks:
        return '          <div style="color: var(--note);">No Pick verdicts in this run.</div>'
    lines = []
    for s in picks:
        edge = s.verdict_edge_pp or 0
        lines.append(
            f'          <div>{html.escape(s.verdict_side or "—"):<24} <span style="color: var(--flame); font-weight: 700;">{edge:+.1f}pp</span></div>'
        )
    return "\n".join(lines)


def _build_match_table(snapshots: list[SnapshotRow]) -> str:
    rows: list[str] = []
    for s in sorted(_ko_only(snapshots), key=lambda r: r.kickoff_utc):
        verdict_pill_cls = {"pick": "pick", "pass": "pass", "avoid": "avoid"}.get(s.verdict_state, "pass")
        verdict_label    = {"pick": "Pick", "pass": "Pass", "avoid": "Avoid"}.get(s.verdict_state, "—")
        side = s.verdict_side or "—"
        edge = f"{s.verdict_edge_pp:+.1f}pp" if s.verdict_edge_pp is not None else "—"
        result = _format_result(s)
        resolution = _resolution_pill(s)
        rows.append(
            f'        <tr>\n'
            f'          <td class="match">{html.escape(s.team_a)} v {html.escape(s.team_b)}</td>\n'
            f'          <td>{s.kickoff_utc.strftime("%-d %b %Y")}</td>\n'
            f'          <td><span class="pill {verdict_pill_cls}">{verdict_label}</span></td>\n'
            f'          <td>{html.escape(side)}</td>\n'
            f'          <td class="num">{edge}</td>\n'
            f'          <td class="num">{s.brier:.3f}</td>\n'
            f'          <td>{result}</td>\n'
            f'          <td>{resolution}</td>\n'
            f'        </tr>'
        )
    return "\n".join(rows)


def _format_result(s: SnapshotRow) -> str:
    actual = "draw" if s.actual_draw else (s.team_a if s.actual_a else s.team_b)
    return html.escape(f"{actual}")


def _resolution_pill(s: SnapshotRow) -> str:
    if s.verdict_state != "pick":
        return '<span class="pill na">n/a</span>'
    actual = "draw" if s.actual_draw else (s.team_a if s.actual_a else s.team_b)
    if s.verdict_side and s.verdict_side == actual:
        return '<span class="pill hit">Hit</span>'
    return '<span class="pill miss">Miss</span>'


def _build_bins(snapshots: list[SnapshotRow]) -> str:
    """10-decile reliability bins from KO (probability, outcome) pairs."""
    pairs: list[tuple[float, int]] = []
    for s in _ko_only(snapshots):
        pairs.append((s.p_a,    s.actual_a))
        pairs.append((s.p_draw, s.actual_draw))
        pairs.append((s.p_b,    s.actual_b))

    bins: list[dict] = []
    for i in range(10):
        lo, hi = i / 10.0, (i + 1) / 10.0
        b = [pp for pp in pairs if lo <= pp[0] < hi or (i == 9 and pp[0] == 1.0)]
        if not b:
            continue
        n = len(b)
        observed = sum(o for _, o in b) / n
        predicted = sum(p for p, _ in b) / n
        bins.append({"x": round(predicted, 3), "y": round(observed, 3), "n": n})
    return f"const bins = {json.dumps(bins, indent=2)};"


# ── Top-level ─────────────────────────────────────────────────────────

def _ensure_markers(html_text: str) -> str:
    """If the scaffold doesn't yet carry our markers, wrap each replaceable
    region exactly once. Idempotent — repeated calls are no-ops.
    """
    def _add_if_missing(html_text: str, name: str, pattern: str, builder) -> str:
        if START_TPL.format(name=name) in html_text:
            return html_text
        return re.sub(pattern, builder, html_text, count=1, flags=re.DOTALL)

    edits = [
        ("masthead",
         r'<div class="masthead">\s*\n(.*?)\n  </div>',
         lambda m: f'<div class="masthead">\n{_wrap("masthead", m.group(1))}\n  </div>'),
        ("disclaimer",
         r'<div class="disclaimer">\s*\n(.*?)\n  </div>',
         lambda m: f'<div class="disclaimer">\n{_wrap("disclaimer", m.group(1))}\n  </div>'),
        ("kpis",
         r'<div class="kpis">\s*\n(.*?)\n  </div>\s*\n\s*<!-- Reliability',
         lambda m: f'<div class="kpis">\n{_wrap("kpis", m.group(1))}\n  </div>\n\n  <!-- Reliability'),
        ("verdict_mix",
         r'(<div class="bars">\s*\n)(.*?)(\n        </div>)',
         lambda m: f'{m.group(1)}{_wrap("verdict_mix", m.group(2))}{m.group(3)}'),
        ("edge_profile",
         r"(<div style=\"font-family: 'JetBrains Mono'[^\"]*\"[^>]*>\s*\n)(.*?)(\n        </div>)",
         lambda m: f'{m.group(1)}{_wrap("edge_profile", m.group(2))}{m.group(3)}'),
        ("match_table",
         r"(<tbody>\s*\n)(.*?)(\n      </tbody>)",
         lambda m: f'{m.group(1)}{_wrap("match_table", m.group(2))}{m.group(3)}'),
        ("bins",
         r"(// Reliability diagram data[^\n]*\n// Each bin[^\n]*\n)(const bins = \[.*?\];)",
         lambda m: f'{m.group(1)}{_wrap("bins", m.group(2))}'),
    ]
    for name, pat, repl in edits:
        html_text = _add_if_missing(html_text, name, pat, repl)
    return html_text


def write_dashboard(
    *,
    dashboard_path: Path,
    snapshots: list[SnapshotRow],
    competitions: list[str],
    run_date: date | None = None,
) -> None:
    run_date = run_date or datetime.now().date()
    n_matches = len({s.match_id for s in _ko_only(snapshots)})

    text = dashboard_path.read_text(encoding="utf-8")
    text = _ensure_markers(text)

    replacements: dict[str, str] = {
        "masthead":     _build_masthead(run_date=run_date, competitions=competitions, n_matches=n_matches),
        "disclaimer":   _build_disclaimer(run_date=run_date, competitions=competitions, n_matches=n_matches),
        "kpis":         _build_kpis(snapshots),
        "verdict_mix":  _build_verdict_mix(snapshots),
        "edge_profile": _build_edge_profile(snapshots),
        "match_table":  _build_match_table(snapshots),
        "bins":         _build_bins(snapshots),
    }

    for name, body in replacements.items():
        if not body:
            continue
        text = _between(name).sub(_wrap(name, body), text)

    dashboard_path.write_text(text, encoding="utf-8")
    log.info("wrote dashboard with %d snapshots → %s", len(snapshots), dashboard_path)
