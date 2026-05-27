"""Unit tests for pure-function helpers in activity.jobs.

The async job bodies (aggregate / seed / prune) hit Postgres and are
covered by the staging deploy. These tests target the deterministic
math + dispatch in the helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from activity.jobs import (
    _HARD_CAP_VIEWS_DAY,
    _HARD_CAP_VOTES_LIFETIME,
    _REACTION_DISTRIBUTION,
    _read_priced_fixtures,
    _stage_for,
    _time_of_day_weight,
    _weighted_reaction,
)


# --- stage classification --------------------------------------------------


@pytest.mark.parametrize("days,expected_views", [
    (30, (12, 30)),          # > 14d away
    (14.5, (12, 30)),        # right at the long edge
    (10, (25, 60)),          # 14d → 5d
    (5, (25, 60)),           # 5d → 14d band (lower-inclusive at 5? — no, 5 is in 5..14 band)
    (3, (50, 130)),          # 5d → 1d
    (0.5, (100, 260)),       # match day
    (0, (100, 260)),         # match day (kickoff today)
])
def test_stage_for_returns_expected_view_range(days, expected_views) -> None:
    stage = _stage_for(days)
    assert stage is not None
    assert stage[0] == expected_views


def test_stage_for_post_kickoff_returns_none() -> None:
    # Anything more than a day past kickoff (days_to_ko < -1) is out of band.
    assert _stage_for(-2) is None
    assert _stage_for(-100) is None


# --- time-of-day weight ----------------------------------------------------


@pytest.mark.parametrize("utc_hour,expected_local_hour", [
    (17, 19),  # 17:00 UTC = 19:00 Madrid (summer DST)
])
def test_time_of_day_weight_peak(utc_hour, expected_local_hour) -> None:
    # In June (DST active in Madrid: UTC+2), 17:00 UTC = 19:00 local → peak.
    t = datetime(2026, 6, 15, utc_hour, 0, 0, tzinfo=timezone.utc)
    assert _time_of_day_weight(t) == 1.6


def test_time_of_day_weight_quiet() -> None:
    # 03:00 UTC in June → 05:00 Madrid → quiet band.
    t = datetime(2026, 6, 15, 3, 0, 0, tzinfo=timezone.utc)
    assert _time_of_day_weight(t) == 0.2


# --- reaction distribution -------------------------------------------------


def test_reaction_distributions_sum_to_one() -> None:
    for state, dist in _REACTION_DISTRIBUTION.items():
        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-9, f"{state} distribution sums to {total}"


def test_weighted_reaction_returns_known_value() -> None:
    # A pick-state distribution sampled enough times should hit all four
    # outcomes. This is a smoke check on the chooser, not on the weights.
    seen = set()
    for _ in range(500):
        seen.add(_weighted_reaction(_REACTION_DISTRIBUTION["pick"]))
    assert seen == {"sharp_call", "fair_call", "off_mark", "wait_see"}


# --- hard caps -------------------------------------------------------------


def test_hard_caps_are_within_spec() -> None:
    assert _HARD_CAP_VIEWS_DAY == 450
    assert _HARD_CAP_VOTES_LIFETIME == 70


# --- read priced fixtures --------------------------------------------------


def test_read_priced_fixtures_skips_missing_per_match_file(tmp_path) -> None:
    # Index claims two matches; only one per-match file exists.
    (tmp_path / "index.json").write_text(json.dumps({
        "matches": [
            {"match_id": "fb-test-a-b-20260612"},
            {"match_id": "fb-test-c-d-20260613"},
        ],
    }))
    (tmp_path / "fb-test-a-b-20260612.json").write_text(json.dumps({
        "kickoff_utc": "2026-06-12T19:00:00Z",
        "team_a": "Argentina",
        "team_b": "Austria",
        "verdict": {"state": "pick"},
    }))
    fixtures = _read_priced_fixtures(tmp_path)
    assert len(fixtures) == 1
    assert fixtures[0]["match_id"] == "fb-test-a-b-20260612"
    assert fixtures[0]["team_a"] == "Argentina"
    assert fixtures[0]["verdict_state"] == "pick"


def test_read_priced_fixtures_no_index_returns_empty(tmp_path) -> None:
    assert _read_priced_fixtures(tmp_path) == []


def test_read_priced_fixtures_defaults_verdict_to_pass(tmp_path) -> None:
    (tmp_path / "index.json").write_text(json.dumps({
        "matches": [{"match_id": "fb-test-x-y-20260612"}],
    }))
    (tmp_path / "fb-test-x-y-20260612.json").write_text(json.dumps({
        "kickoff_utc": "2026-06-12T19:00:00Z",
        "team_a": "Brazil",
        "team_b": "France",
        # no verdict block
    }))
    fixtures = _read_priced_fixtures(tmp_path)
    assert fixtures[0]["verdict_state"] == "pass"
