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

REGIONS = ("masthead", "summary", "disclaimer", "kpis", "verdict_mix",
           "edge_profile", "match_table", "bins")


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
    """Emit the deck line + the three bar rows in one shot.

    The deck text mentions the match count, so it has to live inside the
    replaceable region (otherwise the scaffold's stale "across the 5
    matches" copy survives).
    """
    ko = _ko_only(snapshots)
    n = max(len(ko), 1)
    counts = {"pick": 0, "pass": 0, "avoid": 0}
    for s in ko:
        counts[s.verdict_state] = counts.get(s.verdict_state, 0) + 1
    return f'''        <div class="deck">How The Desk's call broke down across the {n} matches.</div>
        <div class="verdict-mix">
          <div class="row">
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


# ── Summary block ─────────────────────────────────────────────────────

def _calibration_grade(delta_brier: float) -> tuple[str, str, str]:
    """Return (color, verdict, detail) for the calibration card.

    `delta_brier` = mean(model) − mean(closing market). Negative means the
    model is better calibrated.
    """
    if delta_brier < -0.005:
        return ("green", "Better than market",
                f"Model Brier is {abs(delta_brier):.4f} below the closing line. "
                "Calibration is the credibility number; this clears the bar.")
    if delta_brier > 0.02:
        return ("red", "Behind the market",
                f"Model Brier is {delta_brier:.4f} above the closing line — "
                "the engine is meaningfully less calibrated than the price you'd "
                "see on Pinnacle. Needs work before public surfacing.")
    if delta_brier > 0.005:
        return ("amber", "Slightly behind",
                f"Model Brier sits {delta_brier:.4f} above the closing line. "
                "Within striking distance; expected to close once form / "
                "weather / injury features ship in PR 5.")
    return ("amber", "Comparable",
            f"Model Brier is within {abs(delta_brier):.4f} of the closing "
            "line — essentially a tie across this sample. Calibration is "
            "credible at v1 model depth.")


def _selection_grade(pick_rate: float, n_picks: int, n_matches: int) -> tuple[str, str, str]:
    """Pick rate quality call. Target 5–20% per editorial brief."""
    pct = pick_rate * 100
    if 0.05 <= pick_rate <= 0.20:
        return ("green", "Disciplined",
                f"{n_picks}/{n_matches} ({pct:.0f}%) Pick rate sits inside the 5–20% target.")
    if pick_rate < 0.05:
        return ("amber", "Too cautious",
                f"{n_picks}/{n_matches} ({pct:.0f}%) Picks — engine rarely sees an edge. "
                "Likely OK at v1 model depth; revisit after PR 5.")
    if pick_rate > 0.50:
        return ("red", "Too aggressive",
                f"{n_picks}/{n_matches} ({pct:.0f}%) Pick rate. The v1 model "
                "lacks form / weather / injury features, so it disagrees with "
                "the closing market on most fixtures. Discipline arrives with PR 5.")
    return ("amber", "Slightly hot",
            f"{n_picks}/{n_matches} ({pct:.0f}%) Pick rate sits above the "
            "5–20% target — within tolerance but worth watching.")


def _bottom_line(calibration_color: str, selection_color: str) -> tuple[str, str, str]:
    """Compose the third card from the two assessments."""
    if calibration_color == "green" and selection_color == "green":
        return ("green", "Ready to surface",
                "Both calibration and selection clear their bars. Safe to ship publicly.")
    if calibration_color == "red" or selection_color == "red":
        return ("red", "Hold for v1.1",
                "One axis is meaningfully behind the bar. Surface internally for "
                "review; don't post publicly until calibration / selection settles.")
    if calibration_color == "amber" and selection_color == "amber":
        return ("amber", "Calibration-credible, selection-loose",
                "The headline number (calibration) holds. Pick rate is the known "
                "weakness; PR 5's late-binding features tighten it.")
    return ("amber", "Mixed signal",
            "Calibration and selection point in different directions — read both "
            "cards before drawing conclusions.")


def _build_summary(snapshots: list[SnapshotRow]) -> str:
    ko = _ko_only(snapshots)
    if not ko:
        return ('    <div class="summary-card amber">'
                '<div class="heading">Summary</div>'
                '<div class="verdict">No data yet</div>'
                '<div class="detail">Run desk backtest --tournament wc-2022.</div>'
                '</div>')

    n = len(ko)
    mean_brier        = sum(s.brier        for s in ko) / n
    mean_market_brier = sum(s.market_brier for s in ko) / n
    delta = mean_brier - mean_market_brier

    n_picks = sum(1 for s in ko if s.verdict_state == "pick")
    pick_rate = n_picks / n

    cal_color, cal_v, cal_d   = _calibration_grade(delta)
    sel_color, sel_v, sel_d   = _selection_grade(pick_rate, n_picks, n)
    bot_color, bot_v, bot_d   = _bottom_line(cal_color, sel_color)

    return (
        f'    <div class="summary-card {cal_color}">\n'
        f'      <div class="heading">Calibration · model vs market</div>\n'
        f'      <div class="verdict">{html.escape(cal_v)}</div>\n'
        f'      <div class="detail">{html.escape(cal_d)}</div>\n'
        f'    </div>\n'
        f'    <div class="summary-card {sel_color}">\n'
        f'      <div class="heading">Selection · pick discipline</div>\n'
        f'      <div class="verdict">{html.escape(sel_v)}</div>\n'
        f'      <div class="detail">{html.escape(sel_d)}</div>\n'
        f'    </div>\n'
        f'    <div class="summary-card {bot_color}">\n'
        f'      <div class="heading">Bottom line</div>\n'
        f'      <div class="verdict">{html.escape(bot_v)}</div>\n'
        f'      <div class="detail">{html.escape(bot_d)}</div>\n'
        f'    </div>'
    )


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
        # Insert a brand-new "summary" block right before the KPI strip on
        # first run. Subsequent runs find the marker and skip.
        ("summary",
         r'(<!-- KPI strip -->)',
         lambda m: f'<!-- Headline summary -->\n  <div class="summary">\n{_wrap("summary", "    <!-- populated on first backtest run -->")}\n  </div>\n\n  {m.group(1)}'),
        ("kpis",
         r'<div class="kpis">\s*\n(.*?)\n  </div>\s*\n\s*<!-- Reliability',
         lambda m: f'<div class="kpis">\n{_wrap("kpis", m.group(1))}\n  </div>\n\n  <!-- Reliability'),
        # The verdict-mix block lives between <h3>Verdict mix</h3> and the
        # next <h3> ("Edge profile"). Wrap everything in between (deck +
        # verdict-mix div) so the writer can rewrite copy + bars in one pass.
        ("verdict_mix",
         r'(<h3>Verdict mix</h3>)(.*?)(<h3[^>]*>Edge profile</h3>)',
         lambda m: f'{m.group(1)}\n{_wrap("verdict_mix", "<!-- populated -->")}\n        {m.group(3)}'),
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
    # Inject the summary CSS once on first run so the colors aren't inline.
    css_anchor = "/* ===== Verdict mix bars ===== */"
    if "summary-card" not in html_text:
        html_text = html_text.replace(css_anchor, _SUMMARY_CSS + "\n  " + css_anchor, 1)

    for name, pat, repl in edits:
        html_text = _add_if_missing(html_text, name, pat, repl)
    return html_text


# Summary-block CSS injected once into the scaffold's <style> block.
_SUMMARY_CSS = """  /* ===== Headline summary ===== */
  .summary {
    display: grid;
    grid-template-columns: 1fr 1fr 2fr;
    gap: 12px;
    margin-bottom: 28px;
  }
  @media (max-width: 800px) { .summary { grid-template-columns: 1fr; } }
  .summary-card {
    background: var(--card);
    border-left: 6px solid var(--ink);
    padding: 16px 18px;
  }
  .summary-card.green { border-left-color: #2a7a2a; background: #f0f7ee; }
  .summary-card.amber { border-left-color: #c8861a; background: #fbf3df; }
  .summary-card.red   { border-left-color: #b83a2a; background: #fbe8e3; }
  .summary-card .heading {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--note);
    margin-bottom: 4px;
  }
  .summary-card .verdict {
    font-family: Georgia, 'Source Serif 4', serif;
    font-weight: 800;
    font-size: 22px;
    color: var(--ink);
    line-height: 1.15;
    margin-bottom: 6px;
  }
  .summary-card .detail {
    font-size: 13px;
    color: var(--body);
    line-height: 1.4;
  }
"""


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
        "summary":      _build_summary(snapshots),
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
