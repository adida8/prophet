"""Brier score + reliability calculations on logged predictions.

Per `THE_DESK_DATA_LAYER_SPEC.md` §1.4: a coupled (data, hook) unit
passes calibration when its Brier on the validation set is no worse
than the prior phase by more than a defined tolerance, AND the
feature shows sane directional behaviour.

This module is the pure-maths layer — no I/O, no sqlite. The CLI
report assembles its output by joining `predictions` × `outcomes`
from `forward_validation.db` (read in `desk/desk/cli.py`) and
calling the functions here on each row.

Brier on a three-way market:

    Brier(p, outcome) = (p_a - y_a)^2 + (p_draw - y_draw)^2 + (p_b - y_b)^2

where (y_a, y_draw, y_b) is the one-hot resolved outcome. Lower is
better. A perfectly-calibrated coin-flip predictor on a two-way
market scores 0.5; the 3-way analogue baseline is closer to 0.667.

Brier delta = Brier(with_residual) − Brier(without_residual). Negative
means the residual *improved* Brier (less penalty); positive means it
hurt. The §1.4 gate is "no regression", i.e. delta ≤ tolerance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Outcome = Literal["a", "draw", "b"]

# §1.4 tolerance — how much can with_residual Brier exceed without_residual
# Brier before we call it a regression? The spec is vague ("not worse by
# more than a defined tolerance"); 0.005 is a sane v1 default. On a
# ≥100-fixture sample the standard error on mean Brier is about ±0.05
# (Brier variance ≈ 0.25 / sqrt(100)), so 0.005 is comfortably inside
# noise — passing the gate means form-on really isn't worse, not just
# "lost in the noise."
DEFAULT_BRIER_TOLERANCE: float = 0.005

# §5 minimum sample for the coupled unit to graduate Shadow → Live.
DEFAULT_MIN_SAMPLE_SIZE: int = 100


@dataclass(frozen=True)
class BrierPair:
    """One sample's Brier under both branches of the comparison."""
    match_id:           str
    without_residual:   float
    with_residual:      float

    @property
    def delta(self) -> float:
        return self.with_residual - self.without_residual


@dataclass(frozen=True)
class CalibrationReport:
    """Aggregate across a sample of resolved fixtures.

    The §1.4 gate compares `mean_brier_with_residual` against
    `mean_brier_without_residual + tolerance`. When the with-residual
    mean is the smaller (or within tolerance), the coupled unit
    graduates Shadow → Live.
    """
    sample_size:                int
    mean_brier_without_residual: float
    mean_brier_with_residual:    float
    tolerance:                   float
    min_sample_size:             int

    @property
    def brier_delta(self) -> float:
        """Mean Brier delta — negative means residual improved Brier."""
        return self.mean_brier_with_residual - self.mean_brier_without_residual

    @property
    def sample_size_cleared(self) -> bool:
        return self.sample_size >= self.min_sample_size

    @property
    def no_regression(self) -> bool:
        """Brier on the with-residual branch isn't worse than without
        by more than `tolerance`."""
        return self.brier_delta <= self.tolerance

    @property
    def gate_cleared(self) -> bool:
        """The §1.4 gate as we ship it. Sane direction is checked
        separately in `directionally_sane`."""
        return self.sample_size_cleared and self.no_regression

    def headline(self) -> str:
        gate = "✓" if self.gate_cleared else "✗"
        return (
            f"forward-validation [B.1.form] · {gate} "
            f"n={self.sample_size} "
            f"Brier without {self.mean_brier_without_residual:.4f} "
            f"vs with {self.mean_brier_with_residual:.4f} "
            f"(Δ {self.brier_delta:+.4f}; tol {self.tolerance:.4f})"
        )


def brier_3way(
    p_a: float, p_draw: float, p_b: float, outcome: Outcome,
) -> float:
    """Brier score on one 3-way market prediction. Lower is better."""
    y_a    = 1.0 if outcome == "a"    else 0.0
    y_draw = 1.0 if outcome == "draw" else 0.0
    y_b    = 1.0 if outcome == "b"    else 0.0
    return (p_a - y_a) ** 2 + (p_draw - y_draw) ** 2 + (p_b - y_b) ** 2


def aggregate_calibration(
    pairs: list[BrierPair],
    *,
    tolerance:       float = DEFAULT_BRIER_TOLERANCE,
    min_sample_size: int   = DEFAULT_MIN_SAMPLE_SIZE,
) -> CalibrationReport:
    """Build a `CalibrationReport` from a list of (without, with)
    Brier pairs. Empty list = sample_size 0, gate never cleared."""
    n = len(pairs)
    if n == 0:
        return CalibrationReport(
            sample_size=0,
            mean_brier_without_residual=0.0,
            mean_brier_with_residual=0.0,
            tolerance=tolerance,
            min_sample_size=min_sample_size,
        )
    sum_without = sum(p.without_residual for p in pairs)
    sum_with    = sum(p.with_residual    for p in pairs)
    return CalibrationReport(
        sample_size=n,
        mean_brier_without_residual=sum_without / n,
        mean_brier_with_residual=sum_with / n,
        tolerance=tolerance,
        min_sample_size=min_sample_size,
    )


# ── Reliability bins — secondary diagnostic, not part of the gate ──

@dataclass(frozen=True)
class ReliabilityBin:
    """One prediction-probability bin for the reliability diagram."""
    lower_pct:     float       # bin lower edge, e.g. 0.20
    upper_pct:     float       # bin upper edge, e.g. 0.30
    n:             int
    mean_p:        float       # mean predicted prob in bin
    observed_rate: float       # fraction that resolved as the side

    @property
    def midpoint(self) -> float:
        return (self.lower_pct + self.upper_pct) / 2

    @property
    def gap(self) -> float:
        return self.mean_p - self.observed_rate


def reliability_bins(
    samples: list[tuple[float, bool]],
    *,
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Group (predicted_p, resolved_as_side) samples into n_bins
    even-width bins and compute mean_p + observed_rate per bin.

    Used to diagnose direction: if the model says 70% and the side
    actually wins 30% of the time, the residual is mis-calibrated —
    even when mean Brier passes the §1.4 gate.
    """
    if not samples:
        return []
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, hit in samples:
        # Clamp to [0,1] defensively; out-of-range = bug in caller.
        p_clamped = max(0.0, min(1.0, p))
        idx = min(int(p_clamped * n_bins), n_bins - 1)
        bins[idx].append((p_clamped, hit))

    out: list[ReliabilityBin] = []
    for i, contents in enumerate(bins):
        if not contents:
            continue
        n = len(contents)
        mean_p = sum(p for p, _ in contents) / n
        rate   = sum(1.0 for _, hit in contents if hit) / n
        out.append(ReliabilityBin(
            lower_pct=i / n_bins,
            upper_pct=(i + 1) / n_bins,
            n=n,
            mean_p=mean_p,
            observed_rate=rate,
        ))
    return out


def directional_sanity(
    pairs: list[BrierPair],
    *,
    min_improvement_rate: float = 0.45,
) -> bool:
    """Sane direction check — among samples where with_residual differs
    materially from without_residual, the with-residual branch should
    win at least `min_improvement_rate` of the time. Below 0.45 means
    the residual is moving probabilities the WRONG way — the model is
    learning negatively. A 50/50 random shift would clear this; <45%
    is a directional regression even if mean Brier is fine.
    """
    if not pairs:
        return False
    material = [p for p in pairs if not math.isclose(p.delta, 0.0, abs_tol=1e-6)]
    if not material:
        return True
    wins = sum(1 for p in material if p.with_residual < p.without_residual)
    return (wins / len(material)) >= min_improvement_rate
