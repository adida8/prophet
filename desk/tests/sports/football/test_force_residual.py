"""`compute(features, force_residual=True/False/None)` override.

The runner uses `force_residual=True` to produce the Shadow prediction
even when `config.FORM_RANK_RESIDUAL_ENABLED` is `False` (the default
in prod). This test set proves:
  * force_residual=None → reads the config flag (current behaviour)
  * force_residual=True → applies the residual regardless of flag
  * force_residual=False → ignores the residual regardless of flag
  * the override is restored after the call (no global state leak)
"""

from __future__ import annotations

from desk import config
from desk.sports.football.model import (
    FORM_WEIGHT, FootballFeatures, compute,
)


def _feat(form_a=None, form_b=None):
    return FootballFeatures(
        team_a_name="A", team_b_name="B",
        team_a_elo=1700.0, team_b_elo=1700.0,
        is_international=False,
        team_a_form_delta=form_a,
        team_b_form_delta=form_b,
    )


def test_default_reads_config_flag_off(monkeypatch):
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", False)
    out = compute(_feat(form_a=1.0))
    # Flag off → residual NOT applied → elo_a_adj equals base 1700.
    assert out.elo_a_adj == 1700.0


def test_default_reads_config_flag_on(monkeypatch):
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", True)
    out = compute(_feat(form_a=1.0))
    # Flag on → residual applied → elo_a_adj == 1700 + FORM_WEIGHT * 1.0.
    assert out.elo_a_adj == 1700.0 + FORM_WEIGHT


def test_force_residual_true_applies_even_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", False)
    out = compute(_feat(form_a=1.0), force_residual=True)
    assert out.elo_a_adj == 1700.0 + FORM_WEIGHT


def test_force_residual_false_disables_even_when_flag_on(monkeypatch):
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", True)
    out = compute(_feat(form_a=1.0), force_residual=False)
    assert out.elo_a_adj == 1700.0


def test_override_does_not_leak_after_call(monkeypatch):
    """The temporary swap inside compute() must restore the original
    flag value via the try/finally."""
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", False)
    compute(_feat(form_a=1.0), force_residual=True)
    assert config.FORM_RANK_RESIDUAL_ENABLED is False
    compute(_feat(form_a=1.0), force_residual=False)
    assert config.FORM_RANK_RESIDUAL_ENABLED is False


def test_dual_compute_pattern(monkeypatch):
    """The runner's actual usage pattern: published prediction + shadow."""
    monkeypatch.setattr(config, "FORM_RANK_RESIDUAL_ENABLED", False)
    features = _feat(form_a=1.0, form_b=-0.5)
    published = compute(features)                       # flag-off path
    shadow    = compute(features, force_residual=True)  # shadow path
    # Published: residual NOT applied, both teams at base 1700.
    assert published.elo_a_adj == 1700.0
    # Shadow: residual applied — team A up, team B down.
    assert shadow.elo_a_adj == 1700.0 + FORM_WEIGHT * 1.0
    assert shadow.elo_b_adj == 1700.0 + FORM_WEIGHT * -0.5
