"""Confidence-band tests for the football model (Phase A.3).

Verifies the model emits 5th/95th-percentile bounds for each side, that
the band straddles the point estimate, and that wider Elo uncertainty
expands the band as expected.
"""

from __future__ import annotations

import pytest

from desk.sports.football.model import (
    ELO_JACKKNIFE_GRID,
    FootballFeatures,
    compute,
)


def _features(elo_a: float, elo_b: float, **overrides) -> FootballFeatures:
    return FootballFeatures(
        team_a_name="A", team_b_name="B",
        team_a_elo=elo_a, team_b_elo=elo_b,
        is_international=True,
        team_a_iso3="aaa", team_b_iso3="bbb",
        **overrides,
    )


# ── Band straddles point estimate ─────────────────────────────────────

def test_band_straddles_point_estimate() -> None:
    out = compute(_features(2050, 1830))
    assert out.p_a_lower <= out.p_a <= out.p_a_upper
    assert out.p_draw_lower <= out.p_draw <= out.p_draw_upper
    assert out.p_b_lower <= out.p_b <= out.p_b_upper


def test_band_endpoints_are_in_unit_interval() -> None:
    out = compute(_features(2050, 1830))
    for v in (out.p_a_lower, out.p_a_upper,
              out.p_draw_lower, out.p_draw_upper,
              out.p_b_lower, out.p_b_upper):
        assert 0.0 <= v <= 1.0


# ── Band reflects ±50 Elo perturbation ────────────────────────────────

def test_band_width_matches_jackknife_extremes() -> None:
    """When team_a is the favourite, the lower bound should match what
    you'd compute by dropping its Elo by the max grid step (50) and
    raising team_b's by the same. The upper bound is the symmetric flip.
    """
    base_a, base_b = 2050.0, 1830.0
    out = compute(_features(base_a, base_b))

    # Equivalent point estimates at the corners of the jackknife grid.
    lo_a_features = _features(base_a + min(ELO_JACKKNIFE_GRID),
                              base_b + max(ELO_JACKKNIFE_GRID))
    hi_a_features = _features(base_a + max(ELO_JACKKNIFE_GRID),
                              base_b + min(ELO_JACKKNIFE_GRID))
    lo = compute(lo_a_features)
    hi = compute(hi_a_features)

    assert out.p_a_lower == pytest.approx(lo.p_a, abs=1e-9)
    assert out.p_a_upper == pytest.approx(hi.p_a, abs=1e-9)


def test_evenly_matched_teams_have_wide_band_around_50_pct() -> None:
    out = compute(_features(1700, 1700))
    # Around 50/50 with a draw share, p_a is roughly 0.36; the band
    # should swing several pp on either side.
    assert (out.p_a_upper - out.p_a_lower) > 0.05
    # And it should cover the point estimate.
    assert out.p_a_lower <= out.p_a <= out.p_a_upper


def test_lopsided_teams_have_narrow_band_at_extremes() -> None:
    """A heavily favoured team's p_a is already near the top of the
    range; perturbing Elo can't push it much higher, so the band tightens
    at the upper end."""
    out = compute(_features(2300, 1500))
    # p_a is high (near 0.85+); p_a_upper - p_a should be small.
    assert (out.p_a_upper - out.p_a) < 0.05


# ── Bonuses preserved across perturbations ────────────────────────────

def test_host_bonus_applies_inside_the_band() -> None:
    """The host bonus is deterministic and should appear in every grid
    sample — perturbing the prior shouldn't reach the bonus arithmetic.
    """
    f_no_bonus  = _features(1700, 1700)
    f_with_host = _features(1700, 1700, venue_host_iso3="bbb")

    no   = compute(f_no_bonus)
    host = compute(f_with_host)

    # Host bonus shifts the band entirely toward team_b.
    assert host.p_b_lower > no.p_b_lower
    assert host.p_b_upper > no.p_b_upper
    assert host.p_a_lower < no.p_a_lower
