"""Brier scoring + reliability + directional sanity."""

from __future__ import annotations

import pytest

from desk.verdict.scoring import (
    BrierPair, aggregate_calibration, brier_3way,
    directional_sanity, reliability_bins,
)


def test_brier_perfect_prediction():
    # Predicted 100% on outcome "a", outcome was "a" → Brier = 0.
    assert brier_3way(1.0, 0.0, 0.0, "a") == pytest.approx(0.0)


def test_brier_worst_prediction():
    # Predicted 100% on outcome "b", outcome was "a" → Brier = 2.
    assert brier_3way(0.0, 0.0, 1.0, "a") == pytest.approx(2.0)


def test_brier_uniform_three_way():
    # 1/3 each, outcome "a" → Brier = (2/3)^2 + (1/3)^2 + (1/3)^2 = 6/9.
    assert brier_3way(1/3, 1/3, 1/3, "a") == pytest.approx(6/9)


def test_aggregate_empty_sample_never_clears_gate():
    report = aggregate_calibration([])
    assert report.sample_size == 0
    assert not report.gate_cleared


def test_aggregate_simple_mean():
    pairs = [
        BrierPair("m1", without_residual=0.5, with_residual=0.4),
        BrierPair("m2", without_residual=0.6, with_residual=0.5),
    ]
    report = aggregate_calibration(pairs, min_sample_size=1)
    assert report.sample_size == 2
    assert report.mean_brier_without_residual == pytest.approx(0.55)
    assert report.mean_brier_with_residual == pytest.approx(0.45)
    assert report.brier_delta == pytest.approx(-0.10)
    assert report.no_regression
    assert report.gate_cleared


def test_aggregate_regression_flagged():
    pairs = [
        BrierPair("m1", without_residual=0.3, with_residual=0.6),
    ]
    report = aggregate_calibration(pairs, tolerance=0.005, min_sample_size=1)
    assert not report.no_regression
    assert not report.gate_cleared


def test_aggregate_tolerance_window():
    """A small Brier delta within tolerance still clears the gate."""
    pairs = [BrierPair("m1", without_residual=0.5, with_residual=0.503)]
    report = aggregate_calibration(pairs, tolerance=0.005, min_sample_size=1)
    assert report.no_regression
    assert report.gate_cleared


def test_aggregate_min_sample_blocks_small_sample():
    pairs = [BrierPair("m1", without_residual=0.5, with_residual=0.4)]
    report = aggregate_calibration(pairs, min_sample_size=100)
    assert report.sample_size == 1
    assert not report.gate_cleared


def test_directional_sanity_clear_improvement():
    pairs = [
        BrierPair("m1", without_residual=0.6, with_residual=0.4),  # win
        BrierPair("m2", without_residual=0.5, with_residual=0.3),  # win
        BrierPair("m3", without_residual=0.5, with_residual=0.7),  # loss
    ]
    # 2/3 = 67% improvements → >= 45%, sane.
    assert directional_sanity(pairs)


def test_directional_sanity_flags_wrong_direction():
    pairs = [
        BrierPair("m1", without_residual=0.5, with_residual=0.7),  # loss
        BrierPair("m2", without_residual=0.5, with_residual=0.8),  # loss
        BrierPair("m3", without_residual=0.5, with_residual=0.9),  # loss
    ]
    # 0/3 = 0% improvements → < 45%, NOT sane.
    assert not directional_sanity(pairs)


def test_directional_sanity_ignores_equal_deltas():
    """Pairs with no material delta shouldn't count in the wins/losses
    denominator."""
    pairs = [
        BrierPair("m1", without_residual=0.5, with_residual=0.5),  # no-op
        BrierPair("m2", without_residual=0.5, with_residual=0.3),  # win
    ]
    assert directional_sanity(pairs)


def test_reliability_bins_basic_calibration():
    samples = [
        (0.05, False), (0.05, False), (0.05, False),
        (0.55, True),  (0.55, False), (0.55, True),
        (0.95, True),  (0.95, True),  (0.95, True),
    ]
    bins = reliability_bins(samples, n_bins=10)
    by_mid = {round(b.midpoint, 2): b for b in bins}
    assert by_mid[0.05].observed_rate == 0.0
    assert by_mid[0.55].observed_rate == pytest.approx(2/3, abs=0.01)
    assert by_mid[0.95].observed_rate == 1.0


def test_reliability_bins_handles_empty_input():
    assert reliability_bins([], n_bins=10) == []
