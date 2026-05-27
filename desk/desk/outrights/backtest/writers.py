"""HTML dashboard writer for the outright backtest.

Standalone single-page render — much simpler than the match backtest's
region-replacement scheme. The outright backtest has one tournament
worth of data (32-team ladder + a handful of scoring rows) and one
true outcome; a fresh HTML file each run is cleaner than maintaining
a scaffold.

Style follows the Odds Primer design language at a basic level
(Source Serif 4 + Inter Tight + JetBrains Mono via system stack
fallbacks; no external CDN deps so the file works offline).
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from pathlib import Path

from desk.outrights.backtest.runner import WC22BacktestResult
from desk.outrights.backtest.scoring import ScoreBundle

log = logging.getLogger("desk.outrights.backtest.writers")


def _h(s: str) -> str:
    return html.escape(s, quote=True)


def _kpi(label: str, value: str, hint: str = "") -> str:
    hint_html = f'<div class="kpi-hint">{_h(hint)}</div>' if hint else ""
    return (
        '<div class="kpi">'
        f'<div class="kpi-label">{_h(label)}</div>'
        f'<div class="kpi-value">{_h(value)}</div>'
        f'{hint_html}'
        '</div>'
    )


def _score_row(s: ScoreBundle) -> str:
    return (
        '<tr>'
        f'<td class="label">{_h(s.label)}</td>'
        f'<td class="num">{s.winner_p:.4f}</td>'
        f'<td class="num">{s.winner_rank}</td>'
        f'<td class="num">{s.brier:.4f}</td>'
        f'<td class="num">{s.log_score:.4f}</td>'
        f'<td>{"✓" if s.top3_hit else ""}</td>'
        f'<td>{"✓" if s.top5_hit else ""}</td>'
        f'<td>{"✓" if s.top8_hit else ""}</td>'
        '</tr>'
    )


def write_dashboard(
    result: WC22BacktestResult,
    *,
    dashboard_path: Path,
) -> Path:
    """Write a single self-contained HTML dashboard."""
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Top-of-ladder rows for the model — sort descending by p_win.
    ladder = sorted(result.field, key=lambda t: -result.model.p_win.get(t, 0.0))

    ladder_rows: list[str] = []
    for i, team in enumerate(ladder, start=1):
        p     = result.model.p_win.get(team, 0.0)
        lo    = result.model.p_win_lower.get(team, 0.0)
        hi    = result.model.p_win_upper.get(team, 0.0)
        elo   = result.elo_lookup.get(team, 1500.0)
        win_flag = " · winner" if team == result.winner else ""
        rank_cls = "winner" if team == result.winner else ""
        ladder_rows.append(
            f'<tr class="{rank_cls}">'
            f'<td class="num">{i}</td>'
            f'<td>{_h(team)}{_h(win_flag)}</td>'
            f'<td class="num">{elo:.0f}</td>'
            f'<td class="num">{p * 100:.2f}%</td>'
            f'<td class="num">{lo * 100:.2f}–{hi * 100:.2f}%</td>'
            f'</tr>'
        )
    ladder_html = "\n".join(ladder_rows)

    # KPI strip — the headline numbers.
    kpis_html = "\n".join([
        _kpi("Sims", f"{result.model.sims:,}", "Monte Carlo runs"),
        _kpi("True winner", result.winner, "WC 2022 actual"),
        _kpi("Model rank", f"#{result.model_score.winner_rank}",
             "winner's position in our distribution"),
        _kpi("Model P(win)", f"{result.model_score.winner_p * 100:.2f}%",
             "what the engine gave the winner pre-tournament"),
        _kpi("Brier (model)", f"{result.model_score.brier:.4f}",
             "winner-take-all; lower better"),
        _kpi("Brier (uniform)", f"{result.uniform_score.brier:.4f}",
             "baseline reference"),
    ])

    # Scoring comparison table.
    score_rows = [_score_row(result.model_score), _score_row(result.uniform_score)]
    if result.market_score is not None:
        score_rows.append(_score_row(result.market_score))
    score_table_html = "\n".join(score_rows)

    # Headline verdict colour — based on whether the winner was in top-5.
    if result.model_score.top3_hit:
        verdict = "✓ Winner in top 3"
        verdict_cls = "verdict-good"
    elif result.model_score.top5_hit:
        verdict = "✓ Winner in top 5"
        verdict_cls = "verdict-ok"
    elif result.model_score.top8_hit:
        verdict = "Winner in top 8"
        verdict_cls = "verdict-amber"
    else:
        verdict = f"Winner ranked #{result.model_score.winner_rank}"
        verdict_cls = "verdict-bad"

    html_str = _TEMPLATE.format(
        now=_h(now),
        verdict=_h(verdict),
        verdict_cls=verdict_cls,
        kpis=kpis_html,
        score_table=score_table_html,
        ladder=ladder_html,
        sims=result.model.sims,
        winner=_h(result.winner),
        n_teams=len(result.field),
    )

    dashboard_path.write_text(html_str, encoding="utf-8")
    log.info("wc22 backtest dashboard → %s", dashboard_path)
    return dashboard_path


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Outright backtest · WC 2022</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root {{
      --ink:        #18191c;
      --ink-soft:   #4a4d55;
      --paper:      #faf9f5;
      --rule:       #e3e1d8;
      --accent:     #b13a2b;
      --good:       #2c6a48;
      --amber:      #b87600;
      --bad:        #b13a2b;
      --serif:      'Source Serif 4', Georgia, 'Times New Roman', serif;
      --sans:       'Inter Tight', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      --mono:       'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 0; background: var(--paper); color: var(--ink);
      font-family: var(--serif); font-size: 16px; line-height: 1.55;
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 36px 28px 80px; }}
    h1 {{
      font-family: var(--sans); font-weight: 700; font-size: 32px;
      letter-spacing: -0.01em; margin: 0 0 4px;
    }}
    .sub {{
      font-family: var(--sans); font-size: 14px; color: var(--ink-soft);
      letter-spacing: 0.02em; text-transform: uppercase;
      margin: 0 0 28px;
    }}
    .verdict {{
      display: inline-block; padding: 10px 18px; border-radius: 4px;
      font-family: var(--sans); font-weight: 600; font-size: 15px;
      margin: 0 0 32px;
    }}
    .verdict-good   {{ background: #e7f0e9; color: var(--good); }}
    .verdict-ok     {{ background: #eff5ec; color: var(--good); }}
    .verdict-amber  {{ background: #f6efde; color: var(--amber); }}
    .verdict-bad    {{ background: #f8e8e4; color: var(--bad); }}
    .kpis {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 14px; margin: 0 0 36px;
    }}
    .kpi {{
      background: #fff; border: 1px solid var(--rule);
      padding: 14px 16px; border-radius: 4px;
    }}
    .kpi-label {{
      font-family: var(--sans); font-size: 12px; color: var(--ink-soft);
      letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 6px;
    }}
    .kpi-value {{
      font-family: var(--mono); font-size: 22px; font-weight: 600;
    }}
    .kpi-hint {{ font-size: 12px; color: var(--ink-soft); margin-top: 4px; }}
    h2 {{
      font-family: var(--sans); font-weight: 600; font-size: 18px;
      letter-spacing: 0.01em; margin: 36px 0 12px;
      padding-bottom: 8px; border-bottom: 1px solid var(--rule);
    }}
    table {{
      width: 100%; border-collapse: collapse;
      font-family: var(--sans); font-size: 14px; background: #fff;
      border: 1px solid var(--rule); border-radius: 4px; overflow: hidden;
    }}
    th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--rule); }}
    th {{
      background: #f5f3eb; font-weight: 600; font-size: 12px;
      letter-spacing: 0.04em; text-transform: uppercase; color: var(--ink-soft);
    }}
    td.num {{ text-align: right; font-family: var(--mono); }}
    tr.winner {{ background: #fdf4d4; font-weight: 600; }}
    tr.winner td {{ color: var(--ink); }}
    .ladder {{ max-height: 720px; overflow: auto; }}
    .ladder table {{ border-radius: 0; }}
    p.note {{ color: var(--ink-soft); font-size: 14px; margin: 8px 0 24px; }}
    .meta {{
      font-family: var(--sans); font-size: 12px; color: var(--ink-soft);
      margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--rule);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Outright backtest · WC 2022</h1>
    <p class="sub">The Desk · MC sim against frozen pre-tournament Elo</p>

    <div class="verdict {verdict_cls}">{verdict}</div>

    <div class="kpis">
      {kpis}
    </div>

    <h2>Scoring</h2>
    <p class="note">
      Brier is winner-take-all (Σ (p − truth)²; lower better). Log score
      is −log(p(winner)) — punishes confident misses harder than Brier.
      Top-N checks whether the actual winner appeared in our top
      3 / 5 / 8 ranks pre-tournament.
    </p>
    <table>
      <thead>
        <tr>
          <th>Source</th>
          <th class="num">P({winner})</th>
          <th class="num">Rank</th>
          <th class="num">Brier</th>
          <th class="num">Log score</th>
          <th>Top 3</th>
          <th>Top 5</th>
          <th>Top 8</th>
        </tr>
      </thead>
      <tbody>
        {score_table}
      </tbody>
    </table>

    <h2>Full ladder — model P(win)</h2>
    <p class="note">
      All {n_teams} participants ranked by the model's pre-tournament
      P(win) from {sims:,} sims. Bootstrap band is 5th / 95th
      percentile across 30 perturbed samples × 200 sims each.
    </p>
    <div class="ladder">
    <table>
      <thead>
        <tr>
          <th class="num">#</th>
          <th>Team</th>
          <th class="num">Elo</th>
          <th class="num">P(win)</th>
          <th class="num">90% band</th>
        </tr>
      </thead>
      <tbody>
        {ladder}
      </tbody>
    </table>
    </div>

    <div class="meta">
      Generated {now}. Inputs: WC 2022 group draw + R16 bracket +
      pre-tournament Elo snapshot (2022-11-20). True winner: {winner}.
    </div>
  </div>
</body>
</html>
"""
