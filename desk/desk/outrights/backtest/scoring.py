"""Outright backtest scoring metrics.

One tournament = one true winner = one realised outcome. Calibration
on a single observation is noisy, so the dashboard surfaces several
complementary metrics:

  * **Brier (winner-take-all)** — Σ (p_i − 1[i = winner])². Absolute
    value is high on a 32-team field (uniform prior ≈ 0.94); the
    informative read is relative to a reference baseline (uniform,
    market consensus when available).
  * **Log score** — -log(p_winner). Punishes confident wrong calls
    hard. Cleaner single-number metric than Brier for "did we have
    the winner near the top of our distribution?".
  * **Rank of winner** — 1-indexed position of the true winner in the
    descending P(win) ranking. Robust to long-tail probability mass
    that Brier penalises but doesn't really matter.
  * **Top-N hit** — did the winner land in our top 3 / top 5 / top 8?
    Easy-to-interpret credibility check.

For comparison, the same metrics are computed against
`MARKET_REFERENCE_P_WIN` (when available) and a uniform 1/N baseline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBundle:
    """All metrics for one P(win) distribution against one true winner."""
    label:        str
    brier:        float    # Σ (p_i − 1[i = winner])²
    log_score:    float    # -log(p_winner); +inf if p_winner = 0
    winner_p:    float    # P(winner) under this distribution
    winner_rank:  int      # 1-indexed
    top3_hit:     bool
    top5_hit:     bool
    top8_hit:     bool


def _normalise(p_by_team: dict[str, float]) -> dict[str, float]:
    """Renormalise to sum to 1. Defensive — the MC sim's output already
    sums to 1, but a market reference set is overround-loaded."""
    total = sum(p_by_team.values())
    if total <= 0:
        return {t: 0.0 for t in p_by_team}
    return {t: p / total for t, p in p_by_team.items()}


def score(
    label: str,
    p_by_team: dict[str, float],
    *,
    winner: str,
    field: tuple[str, ...],
) -> ScoreBundle:
    """Score one P(win) distribution. `field` is the full set of teams
    to score against (so teams missing from `p_by_team` count as p=0).
    """
    p = {t: p_by_team.get(t, 0.0) for t in field}
    p = _normalise(p) if abs(sum(p.values()) - 1.0) > 0.05 else p

    brier = 0.0
    for team, prob in p.items():
        true_outcome = 1.0 if team == winner else 0.0
        brier += (prob - true_outcome) ** 2

    winner_p = p.get(winner, 0.0)
    log_score = -math.log(max(winner_p, 1e-12))

    ranked = sorted(p, key=lambda t: -p[t])
    try:
        winner_rank = ranked.index(winner) + 1
    except ValueError:
        winner_rank = len(field) + 1

    return ScoreBundle(
        label=label,
        brier=brier,
        log_score=log_score,
        winner_p=winner_p,
        winner_rank=winner_rank,
        top3_hit=winner_rank <= 3,
        top5_hit=winner_rank <= 5,
        top8_hit=winner_rank <= 8,
    )


def uniform_distribution(field: tuple[str, ...]) -> dict[str, float]:
    """Reference baseline — perfectly uninformed prior."""
    n = len(field)
    return {t: 1.0 / n for t in field}
