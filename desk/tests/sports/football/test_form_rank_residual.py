"""Phase B.1 — form / FIFA-rank residual on the Elo prior.

The hook ships in Shadow: extensions to `FootballFeatures` are
optional, the env flag `DESK_FORM_RANK_RESIDUAL` is off by default, and
even with the flag on, an all-None feature row contributes nothing. The
spec (`THE_DESK_OPTIMIZATION_SPEC.md` §4.B.1) lets the hook PR land
ahead of its paired data PR; the coupled unit isn't *done* until
data-layer Phase 2 wires real values into the feature builder and
forward-validation clears.
"""

from __future__ import annotations

import pytest

from desk import config
from desk.sports.football.model import (
    FORM_WEIGHT,
    RANK_WEIGHT,
    RESIDUAL_DRIVER_THRESHOLD_ELO,
    FootballFeatures,
    compute,
)


@pytest.fixture
def residual_enabled(monkeypatch):
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", True)


@pytest.fixture
def residual_disabled(monkeypatch):
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", False)


def _features(**overrides) -> FootballFeatures:
    base = dict(
        team_a_name="A", team_b_name="B",
        team_a_elo=1700.0, team_b_elo=1700.0,
        is_international=False,
    )
    base.update(overrides)
    return FootballFeatures(**base)


# ── Flag off — no contribution even when fields are populated ────────

def test_flag_off_means_residual_does_not_apply(residual_disabled) -> None:
    f = _features(
        team_a_form_delta=2.0,
        team_b_form_delta=-1.0,
        team_a_rank_residual=3.0,
        team_b_rank_residual=-2.0,
    )
    out = compute(f)
    # With the flag off the residual must not reach Elo — adjusted Elo
    # equals the base prior (no venue bonuses fire here either).
    assert out.elo_a_adj == pytest.approx(1700.0)
    assert out.elo_b_adj == pytest.approx(1700.0)
    assert out.drivers == ()


# ── Flag on, all None — same byte-identical no-op ────────────────────

def test_flag_on_but_no_features_is_a_no_op(residual_enabled) -> None:
    f = _features()
    out = compute(f)
    assert out.elo_a_adj == pytest.approx(1700.0)
    assert out.elo_b_adj == pytest.approx(1700.0)
    assert out.drivers == ()


# ── Flag on — form contribution lands per spec ───────────────────────

def test_form_delta_applies_per_team_and_fires_driver_when_meaningful(
    residual_enabled,
) -> None:
    # form_delta of +1.0 → 20 Elo contribution → clears the 15 Elo
    # driver-attribution threshold. Team B's −0.5 contributes −10 Elo
    # which is below threshold so its driver must NOT fire.
    f = _features(
        team_a_name="Brazil", team_b_name="Croatia",
        team_a_form_delta=1.0,
        team_b_form_delta=-0.5,
    )
    out = compute(f)
    assert out.elo_a_adj == pytest.approx(1700.0 + FORM_WEIGHT * 1.0)
    assert out.elo_b_adj == pytest.approx(1700.0 + FORM_WEIGHT * -0.5)

    labels = {d.label: d for d in out.drivers}
    assert "Brazil form" in labels
    assert "Croatia form" not in labels
    assert labels["Brazil form"].pp_impact == pytest.approx(20.0)
    assert labels["Brazil form"].side == "a"


# ── Flag on — rank residual contribution + driver ────────────────────

def test_rank_residual_fires_when_above_threshold(residual_enabled) -> None:
    # rank_residual of +2.0 → 20 Elo contribution, above the 15 Elo
    # threshold. Drivers fire with rank_residual_a but not _b at +1.0
    # → 10 Elo below threshold.
    f = _features(
        team_a_name="A", team_b_name="B",
        team_a_rank_residual=2.0,
        team_b_rank_residual=1.0,
    )
    out = compute(f)
    assert out.elo_a_adj == pytest.approx(1700.0 + RANK_WEIGHT * 2.0)
    assert out.elo_b_adj == pytest.approx(1700.0 + RANK_WEIGHT * 1.0)

    labels = {d.label for d in out.drivers}
    assert "A rank residual" in labels
    assert "B rank residual" not in labels


def test_driver_threshold_is_signed_and_symmetric(residual_enabled) -> None:
    # form_delta of −1.0 → −20 Elo, |contribution| ≥ 15 → driver fires
    # with negative pp_impact. The threshold is on |x|, not on x.
    f = _features(team_a_form_delta=-1.0)
    out = compute(f)
    drivers = {d.label: d for d in out.drivers}
    assert "A form" in drivers
    assert drivers["A form"].pp_impact == pytest.approx(-20.0)


# ── Combined form + rank → both drivers + summed Elo contribution ────

def test_form_and_rank_combine_additively(residual_enabled) -> None:
    f = _features(
        team_a_form_delta=1.0,        # +20 Elo
        team_a_rank_residual=2.0,     # +20 Elo
    )
    out = compute(f)
    assert out.elo_a_adj == pytest.approx(
        1700.0 + FORM_WEIGHT * 1.0 + RANK_WEIGHT * 2.0
    )
    labels = {d.label for d in out.drivers}
    assert "A form" in labels
    assert "A rank residual" in labels


# ── Threshold gate — exactly 15 Elo fires ───────────────────────────

def test_driver_threshold_inclusive(residual_enabled) -> None:
    # form_delta of +0.75 → 15.0 Elo, exactly at the threshold — fires.
    on_threshold = RESIDUAL_DRIVER_THRESHOLD_ELO / FORM_WEIGHT  # 0.75
    f = _features(team_a_form_delta=on_threshold)
    out = compute(f)
    labels = {d.label for d in out.drivers}
    assert "A form" in labels

    # Just under threshold — does not fire.
    f2 = _features(team_a_form_delta=on_threshold - 0.01)
    out2 = compute(f2)
    labels2 = {d.label for d in out2.drivers}
    assert "A form" not in labels2


# ── Residual stacks under host bonus, not in place of it ─────────────

def test_residual_stacks_with_host_bonus(residual_enabled) -> None:
    # Mexico playing in Mexico picks up the host bonus on top of its
    # form residual — they're additive, not exclusive.
    f = FootballFeatures(
        team_a_name="France", team_b_name="Mexico",
        team_a_elo=2050.0, team_b_elo=1830.0,
        is_international=True,
        team_a_iso3="fra", team_b_iso3="mex",
        venue_host_iso3="mex",
        team_b_form_delta=1.0,                  # +20 Elo
    )
    out = compute(f)
    # Mexico: 1830 + 20 (form) + 75 (host bonus) = 1925
    assert out.elo_b_adj == pytest.approx(1830.0 + FORM_WEIGHT * 1.0 + 75.0)
    labels = {d.label for d in out.drivers}
    assert "Mexico form" in labels
    assert "host nation" in labels


# ── Bootstrap includes the residual in the confidence band ───────────

def test_confidence_band_reflects_residual(residual_enabled) -> None:
    # The confidence band is built from samples of `_adjusted_elos`, so
    # turning the residual on must shift the band's central tendency.
    # We just check the bounds aren't pathological — same fixture with
    # a large positive A-side residual should not produce a lower p_a
    # band than a neutral fixture.
    neutral = _features()
    boosted = _features(team_a_form_delta=2.0)   # +40 Elo to A

    out_n = compute(neutral)
    out_b = compute(boosted)

    assert out_b.p_a > out_n.p_a
    assert out_b.p_a_lower >= out_n.p_a_lower  # band shifted upward


# ── Bootstrap seed is unchanged when residuals are absent ────────────

def test_seed_unchanged_when_residuals_absent(residual_disabled) -> None:
    """With every residual field None, the confidence-band seed must
    match the pre-B.1 seed exactly — this is the byte-identical
    regression gate for the WC 2022 backtest."""
    f = _features(team_a_elo=1850.0, team_b_elo=1700.0)
    out = compute(f)
    # Frozen baseline produced by running the pre-B.1 code on this
    # fixture (1850 vs 1700, club, no venue). If this test starts to
    # fail, the seed has drifted — likely an unintentional change to
    # `_seed_for_features` that touches every existing fixture's band.
    assert out.p_a_lower == pytest.approx(0.4708, abs=0.0005)
    assert out.p_a_upper == pytest.approx(0.6308, abs=0.0005)
