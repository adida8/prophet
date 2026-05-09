"""Threshold-from-env behaviour."""

from __future__ import annotations

import pytest

from desk.verdict.thresholds import Thresholds, current


def test_defaults_match_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DESK_PICK_PP",  raising=False)
    monkeypatch.delenv("DESK_PASS_PP",  raising=False)
    monkeypatch.delenv("DESK_AVOID_PP", raising=False)
    th = Thresholds.from_env()
    assert th.pick_pp  == 3.0
    assert th.pass_pp  == 1.0
    # Phase A.4: relaxed -2.0 → -1.5 per THE_DESK_OPTIMIZATION_SPEC §3.
    assert th.avoid_pp == -1.5


def test_env_overrides_each_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_PICK_PP",  "4.5")
    monkeypatch.setenv("DESK_PASS_PP",  "0.5")
    monkeypatch.setenv("DESK_AVOID_PP", "-3.0")
    th = current()
    assert (th.pick_pp, th.pass_pp, th.avoid_pp) == (4.5, 0.5, -3.0)
