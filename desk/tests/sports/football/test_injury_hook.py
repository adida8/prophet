"""Phase B.3 injury Elo penalty hook in _adjusted_elos."""

from __future__ import annotations

import pytest

from desk import config
from desk.sports.football.model import (
    INJURY_DRIVER_THRESHOLD_ELO, FootballFeatures, compute,
)


def _f(**overrides):
    base = dict(
        team_a_name="A", team_b_name="B",
        team_a_elo=1700.0, team_b_elo=1700.0,
        is_international=False,
    )
    base.update(overrides)
    return FootballFeatures(**base)


def test_flag_off_no_penalty_applied(monkeypatch):
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", False)
    f = _f(team_a_injury_elo_penalty=40.0)
    out = compute(f)
    assert out.elo_a_adj == 1700.0


def test_flag_on_with_penalty_subtracts_from_elo(monkeypatch):
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", True)
    f = _f(team_a_injury_elo_penalty=40.0)
    out = compute(f)
    assert out.elo_a_adj == pytest.approx(1700.0 - 40.0)


def test_flag_on_absent_field_is_no_op(monkeypatch):
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", True)
    f = _f()  # no injury penalty fields
    out = compute(f)
    assert out.elo_a_adj == 1700.0
    assert out.elo_b_adj == 1700.0


def test_driver_fires_above_threshold(monkeypatch):
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", True)
    f = _f(team_a_name="France",
           team_a_injury_elo_penalty=INJURY_DRIVER_THRESHOLD_ELO + 5.0)
    out = compute(f)
    labels = {d.label for d in out.drivers}
    assert "France injuries" in labels


def test_driver_does_not_fire_below_threshold(monkeypatch):
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", True)
    f = _f(team_a_injury_elo_penalty=5.0)
    out = compute(f)
    labels = {d.label for d in out.drivers}
    assert "A injuries" not in labels


def test_force_injury_penalty_override(monkeypatch):
    """The dual-prediction Shadow path uses force_injury_penalty=True
    to compute "with-injury" alongside the published path."""
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", False)
    f = _f(team_a_injury_elo_penalty=40.0)
    # Flag off + override on → penalty IS applied for this call.
    out = compute(f, force_injury_penalty=True)
    assert out.elo_a_adj == pytest.approx(1700.0 - 40.0)


def test_force_residual_and_injury_combined(monkeypatch):
    """Both overrides can fire together for the all-flags-on shadow."""
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", False)
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", False)
    from desk.sports.football.model import FORM_WEIGHT
    f = _f(team_a_form_delta=1.0, team_a_injury_elo_penalty=20.0)
    out = compute(f, force_residual=True, force_injury_penalty=True)
    expected = 1700.0 + FORM_WEIGHT * 1.0 - 20.0
    assert out.elo_a_adj == pytest.approx(expected)


def test_overrides_restore_module_flag(monkeypatch):
    """try/finally must reset config flag even after exception path."""
    monkeypatch.setattr(config, "INJURY_PENALTY_ENABLED", False)
    f = _f(team_a_injury_elo_penalty=20.0)
    compute(f, force_injury_penalty=True)
    assert config.INJURY_PENALTY_ENABLED is False
