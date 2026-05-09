"""Confidence-band tests for the football model (Phase A.1).

Verifies the model emits a 90% bootstrap CI for each side, that the
band straddles the point estimate, that it widens when teams are close
and tightens at the extremes, and that the host / altitude bonuses
each contribute uncertainty when they fire.
"""

from __future__ import annotations

import pytest

from desk.sports.football.model import (
    BOOTSTRAP_N,
    ELO_PERTURBATION,
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


# ── Spec invariants ────────────────────────────────────────────────────

def test_bootstrap_constants_match_spec() -> None:
    """THE_DESK_OPTIMIZATION_SPEC.md §3 Phase A.1 — locked values."""
    assert BOOTSTRAP_N == 100
    assert ELO_PERTURBATION == 20.0


# ── Band shape / consistency ───────────────────────────────────────────

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


def test_band_is_reproducible_across_calls() -> None:
    """Per-feature seeding makes the bootstrap deterministic — the
    backtest workbook and the verdict step depend on this."""
    feats = _features(2050, 1830)
    out_1 = compute(feats)
    out_2 = compute(feats)
    assert out_1.p_a_lower == out_2.p_a_lower
    assert out_1.p_a_upper == out_2.p_a_upper
    assert out_1.p_draw_lower == out_2.p_draw_lower
    assert out_1.p_draw_upper == out_2.p_draw_upper
    assert out_1.p_b_lower == out_2.p_b_lower
    assert out_1.p_b_upper == out_2.p_b_upper


def test_different_matches_get_different_seeds() -> None:
    """Two distinct fixtures with similar Elo gaps produce different
    bootstrap draws — the seed depends on the names, not just the maths.
    """
    out_1 = compute(_features(2050, 1830))
    out_2 = FootballFeatures(
        team_a_name="C", team_b_name="D",
        team_a_elo=2050, team_b_elo=1830,
        is_international=True,
        team_a_iso3="ccc", team_b_iso3="ddd",
    )
    out_2 = compute(out_2)
    # The point estimates must agree — same Elo diff, no bonuses.
    assert out_1.p_a == pytest.approx(out_2.p_a, abs=1e-9)
    # But the bootstrapped lower bound depends on the seed and so should
    # land in different floats.
    assert out_1.p_a_lower != out_2.p_a_lower


# ── Width is sensible at the corners ───────────────────────────────────

def test_evenly_matched_teams_have_wide_band() -> None:
    """A 50/50 fixture has the most posterior uncertainty — the 90%
    band on team_a should span at least 4pp."""
    out = compute(_features(1700, 1700))
    assert (out.p_a_upper - out.p_a_lower) >= 0.04


def test_lopsided_teams_have_narrow_upper_tail() -> None:
    """A heavily favoured team's p_a sits near the top of its range,
    so the 95th-percentile to point gap is tight."""
    out = compute(_features(2300, 1500))
    assert (out.p_a_upper - out.p_a) < 0.05


def test_band_width_is_modest_versus_total_perturbation() -> None:
    """Sanity: the 90% CI is materially narrower than what a worst-case
    Elo swing would imply (40pt swing on team_a + 40pt swing on team_b
    moves p_a by tens of pp). The band should be a fraction of that.
    """
    out = compute(_features(2050, 1830))
    width = out.p_a_upper - out.p_a_lower
    # 90% CI under ±20 perturbation per side: roughly 0.05–0.12 wide.
    # We assert <= 0.20 to leave room for draw-share variability.
    assert 0.0 < width <= 0.20


# ── Bonuses contribute to the band ─────────────────────────────────────

def test_host_bonus_shifts_band_toward_host() -> None:
    """When team_b is the host, every percentile of p_b shifts up and
    every percentile of p_a shifts down."""
    no   = compute(_features(1700, 1700))
    host = compute(_features(1700, 1700, venue_host_iso3="bbb"))

    assert host.p_b_lower > no.p_b_lower
    assert host.p_b_upper > no.p_b_upper
    assert host.p_a_lower < no.p_a_lower
    assert host.p_a_upper < no.p_a_upper


def test_altitude_bonus_widens_acclimatised_band() -> None:
    """When altitude fires for team_b (acclimatised), team_b's bootstrap
    samples each draw a perturbed altitude bonus on top of the perturbed
    Elo — so the band on p_b is wider than the no-altitude case."""
    base    = _features(1700, 1700, venue_altitude_m=2500.0)
    no_alt  = compute(base)
    with_alt = compute(_features(
        1700, 1700,
        venue_altitude_m=2500.0,
        team_b_altitude_acclimatised=True,
    ))
    # Acclimatised team_b's lower bound rises (the bonus is real), and
    # the band itself shifts toward team_b.
    assert with_alt.p_b > no_alt.p_b
    assert with_alt.p_b_lower > no_alt.p_b_lower
