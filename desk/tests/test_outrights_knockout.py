"""Tests for the three-stage knockout-tie resolution.

The previous knockout model re-normalised the regulation-time draw
mass to the winning sides — equivalent to "Elo-weighted coin flip".
This was too tilted toward favourites because penalty shootouts
empirically are much closer to 50/50 than skill gaps would predict.

The new model resolves a KO tie in three stages: 90 minutes (full
Elo distribution), extra time (50% of post-90 draws, re-normalised
like regulation), penalty shootout (remaining draws, capped Elo tilt
of ±10pp from 50/50).
"""

from __future__ import annotations

import random

from desk.outrights.model import (
    ET_SETTLED_SHARE,
    PENS_ELO_SENSITIVITY,
    PENS_TILT_CAP,
    _sample_knockout,
)


def _ko_win_rate(elo_a: float, elo_b: float, *, sims: int = 8000, seed: int = 0) -> float:
    rng = random.Random(seed)
    wins = sum(1 for _ in range(sims) if _sample_knockout(rng, elo_a, elo_b) == 0)
    return wins / sims


def test_equal_teams_resolve_near_coin_flip() -> None:
    rate = _ko_win_rate(1800, 1800, sims=10_000, seed=42)
    assert abs(rate - 0.5) < 0.025, f"equal teams should ~50/50, got {rate:.4f}"


def test_huge_favourite_dominates_but_not_perfectly() -> None:
    """450 Elo gap (Argentina vs Saudi Arabia) — favourite still wins
    nearly always, but not 100% because some ties go to pens and pens
    have a capped tilt."""
    rate = _ko_win_rate(2070, 1620, sims=10_000, seed=42)
    # Strong: should win >85% of ties. Not 100% because pens are flatter.
    assert 0.85 < rate < 0.95, f"450-Elo favourite KO rate out of range: {rate:.4f}"


def test_modest_favourite_modestly_favoured() -> None:
    """100 Elo gap — favourite tilted but well under 70%."""
    rate = _ko_win_rate(1900, 1800, sims=10_000, seed=42)
    assert 0.55 < rate < 0.70, f"100-Elo favourite KO rate out of range: {rate:.4f}"


def test_underdog_wins_some_of_the_time_even_huge_gap() -> None:
    """An 800-Elo gap (extreme outlier) should still let the underdog
    win a small fraction of ties — pens cap prevents 100% dominance."""
    rate = _ko_win_rate(2100, 1300, sims=10_000, seed=42)
    assert rate < 0.99, f"underdog should win some KO ties, dom rate {rate:.4f}"


def test_pens_tilt_cap_is_bounded() -> None:
    """The pens-only tilt cap is ±PENS_TILT_CAP. Sanity-check the
    constant is in a reasonable range — too tight and pens are pure
    coin flip; too wide and we're back to Elo-weighted."""
    assert 0.05 <= PENS_TILT_CAP <= 0.20


def test_et_settled_share_is_in_range() -> None:
    """Historical WC KO data: ~50% of post-90' draws end in extra
    time, the rest go to pens. The constant should be in that ballpark."""
    assert 0.30 <= ET_SETTLED_SHARE <= 0.70


def test_pens_sensitivity_implies_modest_tilt_for_modest_gap() -> None:
    """A 200-Elo gap should produce a ~55/45 pens outcome — the
    historical empirical penalty-shootout outcome for sides with a
    skill gap on the order of a 'top-tier vs upper-middle' matchup."""
    expected_tilt = 200 * PENS_ELO_SENSITIVITY
    assert 0.04 <= expected_tilt <= 0.08
