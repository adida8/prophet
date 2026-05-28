"""Sanity gates — fixture validity + form_delta range checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from desk.data.api_football.cache import FixtureResult
from desk.data.api_football.sanity import (
    REASON_ENTITY_MISMATCH,
    REASON_FAILED_SANITY,
    REASON_OK,
    REASON_OUTSIDE_WINDOW,
    check_entity_match,
    check_fixture,
    check_form_delta_range,
)


def _fx(team_id=7, fixture_id=100, hours_ago=24,
        gf=2, ga=1, status="FT") -> FixtureResult:
    return FixtureResult(
        api_football_team_id=team_id, fixture_id=fixture_id,
        played_at=datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago),
        opponent_team_id=99, team_goals=gf, opponent_goals=ga,
        status_short=status,
    )


# ── check_fixture ────────────────────────────────────────────────────

def test_recent_fixture_passes():
    assert check_fixture(_fx(hours_ago=24)) == REASON_OK


def test_future_fixture_outside_window():
    f = FixtureResult(
        api_football_team_id=7, fixture_id=1,
        played_at=datetime.now(tz=timezone.utc) + timedelta(days=2),
        opponent_team_id=99, team_goals=None, opponent_goals=None,
        status_short="NS",
    )
    assert check_fixture(f) == REASON_OUTSIDE_WINDOW


def test_clock_skew_tolerance_1h():
    """Up to 1h in the future is tolerated (clock skew across machines)."""
    f = FixtureResult(
        api_football_team_id=7, fixture_id=1,
        played_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
        opponent_team_id=99, team_goals=None, opponent_goals=None,
        status_short="NS",
    )
    assert check_fixture(f) == REASON_OK


def test_too_old_fixture_outside_window():
    f = FixtureResult(
        api_football_team_id=7, fixture_id=1,
        played_at=datetime.now(tz=timezone.utc) - timedelta(days=10 * 365),
        opponent_team_id=99, team_goals=1, opponent_goals=0,
        status_short="FT",
    )
    assert check_fixture(f) == REASON_OUTSIDE_WINDOW


def test_negative_goals_fail_sanity():
    f = _fx(gf=-1, ga=0)
    assert check_fixture(f) == REASON_FAILED_SANITY


# ── check_entity_match ────────────────────────────────────────────────

def test_entity_match_ok():
    assert check_entity_match(_fx(team_id=7), requested_team_id=7) == REASON_OK


def test_entity_mismatch():
    assert check_entity_match(_fx(team_id=7), requested_team_id=99) == REASON_ENTITY_MISMATCH


# ── check_form_delta_range ────────────────────────────────────────────

def test_form_delta_in_range_passes():
    assert check_form_delta_range(0.5) == REASON_OK
    assert check_form_delta_range(-1.0) == REASON_OK
    assert check_form_delta_range(2.0) == REASON_OK


def test_form_delta_out_of_range_fails():
    assert check_form_delta_range(3.0) == REASON_FAILED_SANITY
    assert check_form_delta_range(-3.0) == REASON_FAILED_SANITY
