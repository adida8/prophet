"""Compute form_delta from a team's last-N played fixtures.

Per `THE_DESK_OPTIMIZATION_SPEC.md` §4.B.1:

    `form_delta(team)`: weighted last-N results (3-1-0 points,
    exponential decay over the last 10 matches), normalised so the
    long-run mean is zero. A team in a hot streak gets a positive
    delta; a team in a slump, negative.

Implementation:
  * sample = up to LAST_N=10 fixtures, freshest first
  * weight_i = exp(-DECAY_LAMBDA * i) so the most recent fixture gets
    weight 1.0; the 10th-most-recent gets ~0.13. Captures recency
    without losing all history.
  * weighted_points = sum(w_i * points_i) / sum(w_i)
  * form_delta = weighted_points - LONG_RUN_BASELINE_PPG

LONG_RUN_BASELINE_PPG is the league-average points-per-game across all
teams, which would be ~1.5 if W:D:L was 0.4:0.25:0.35 (typical for
elite international football). For v1 we use 1.5 as a fixed baseline —
the operator can re-tune it with backtest data later.

Units: form_delta is in **points per match above baseline**. The model
hook multiplies by `FORM_WEIGHT` (20 Elo per point) to produce an Elo
contribution. A team averaging 2.5 pts/game over its last 10 (very hot)
→ form_delta ≈ +1.0 → +20 Elo nudge.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from desk.data.api_football.cache import FixtureResult

LAST_N: int = 10
DECAY_LAMBDA: float = 0.2
LONG_RUN_BASELINE_PPG: float = 1.5

# Minimum sample to publish a form_delta — fewer than this and we
# return None (absent), so the model hook contributes zero.
MIN_SAMPLE_SIZE: int = 3


def compute_form_delta(
    fixtures: Sequence[FixtureResult],
) -> tuple[float, int] | None:
    """Return (form_delta, sample_size). None when too few fixtures
    are available (fewer than MIN_SAMPLE_SIZE).

    Caller is responsible for passing in only `status.short == "FT"`
    fixtures, freshest first. The function does not re-sort.
    """
    sample = [f for f in fixtures if f.status_short == "FT"][:LAST_N]
    n = len(sample)
    if n < MIN_SAMPLE_SIZE:
        return None

    weights = [math.exp(-DECAY_LAMBDA * i) for i in range(n)]
    weight_sum = sum(weights)
    weighted_points = sum(w * f.points for w, f in zip(weights, sample)) / weight_sum
    return (weighted_points - LONG_RUN_BASELINE_PPG, n)
