"""Verdict thresholds.

Read once at process start. Override at runtime via `.env`:
    DESK_PICK_PP=3.0
    DESK_PASS_PP=1.0
    DESK_AVOID_PP=-1.5

PR 4 reads them via this module so the threshold constants live in one
place. v2's admin backend will mutate them via the
`PATCH /admin/thresholds` endpoint (spec §11).

Phase A.4 (THE_DESK_OPTIMIZATION_SPEC §3) — Avoid threshold review.
The Avoid rule fires when every side's edge `model_p - best_market_p`
sits at or below `avoid_pp`. In a single-venue closing-odds backtest
(WC 2022) the rule is structurally impossible: both probability
triplets sum to 1, so the per-side edges sum to 0, and there is
always a side with positive edge. Relaxed from −2.0 → −1.5 per spec
prescription, with the understanding that the rule activates in the
multi-venue live setting (Polymarket + Kalshi + others), where
`sum(best_for(side))` is < 1 by overround and the per-side edges
shift up.

Backtest binning (WC 2022 closing odds, all 64 KO snapshots):
    every side ≤ -2.0pp:  0 matches
    every side ≤ -1.5pp:  0 matches  (structural — not a tuning gap)
    every side ≤ -0.5pp:  0 matches
    minimum max-side edge across matches: +1.95pp.

The Avoid concept needs a structural redefinition (e.g., max-side
edge ≤ avoid_pp, or a market-distortion metric) to fire on
single-venue data. Tracked for v1.2 ADR.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    """All values are percentage points (pp), not decimals."""
    pick_pp:  float
    pass_pp:  float
    avoid_pp: float

    @classmethod
    def from_env(cls) -> "Thresholds":
        return cls(
            pick_pp=float(os.getenv("DESK_PICK_PP",  "3.0")),
            pass_pp=float(os.getenv("DESK_PASS_PP",  "1.0")),
            avoid_pp=float(os.getenv("DESK_AVOID_PP", "-1.5")),
        )


def current() -> Thresholds:
    """Always reads env at call time so tests can monkeypatch."""
    return Thresholds.from_env()
