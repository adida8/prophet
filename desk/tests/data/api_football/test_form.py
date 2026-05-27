"""form_delta math — weighted last-N PPG vs LONG_RUN_BASELINE_PPG."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from desk.data.api_football.cache import FixtureResult
from desk.data.api_football.form import (
    LONG_RUN_BASELINE_PPG, MIN_SAMPLE_SIZE, compute_form_delta,
)


def _fx(fixture_id: int, hours_ago: int, gf: int, ga: int,
        status: str = "FT") -> FixtureResult:
    return FixtureResult(
        api_football_team_id=42,
        fixture_id=fixture_id,
        played_at=datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago),
        opponent_team_id=99, team_goals=gf, opponent_goals=ga,
        status_short=status,
    )


def test_returns_none_when_too_few_fixtures():
    fixtures = [_fx(1, hours_ago=1, gf=1, ga=0)]
    assert compute_form_delta(fixtures) is None


def test_returns_none_when_all_fixtures_unfinished():
    fixtures = [
        _fx(1, hours_ago=1, gf=0, ga=0, status="POST"),
        _fx(2, hours_ago=2, gf=0, ga=0, status="POST"),
        _fx(3, hours_ago=3, gf=0, ga=0, status="POST"),
    ]
    assert compute_form_delta(fixtures) is None


def test_all_wins_yields_strongly_positive_form_delta():
    # 10 wins in a row — weighted PPG = 3.0 (every weight gets points=3),
    # so form_delta = 3.0 - LONG_RUN_BASELINE_PPG = 3.0 - 1.5 = +1.5.
    fixtures = [_fx(i, hours_ago=i, gf=2, ga=0) for i in range(1, 11)]
    result = compute_form_delta(fixtures)
    assert result is not None
    form_delta, sample = result
    assert sample == 10
    assert form_delta == pytest.approx(3.0 - LONG_RUN_BASELINE_PPG)


def test_all_losses_yields_strongly_negative_form_delta():
    fixtures = [_fx(i, hours_ago=i, gf=0, ga=2) for i in range(1, 11)]
    result = compute_form_delta(fixtures)
    assert result is not None
    form_delta, sample = result
    assert sample == 10
    assert form_delta == pytest.approx(-LONG_RUN_BASELINE_PPG)


def test_mixed_form_is_in_between():
    # Recent wins, older losses → form_delta should be > 0 because
    # the decay weights recent fixtures more.
    fixtures = [
        # freshest first
        _fx(1, hours_ago=1, gf=2, ga=0),  # win
        _fx(2, hours_ago=2, gf=2, ga=0),  # win
        _fx(3, hours_ago=3, gf=1, ga=1),  # draw
        _fx(4, hours_ago=4, gf=0, ga=2),  # loss (old)
        _fx(5, hours_ago=5, gf=0, ga=2),  # loss (old)
        _fx(6, hours_ago=6, gf=0, ga=2),  # loss (old)
    ]
    result = compute_form_delta(fixtures)
    assert result is not None
    form_delta, _ = result
    # weighted average should sit between -1.5 (all losses) and +1.5 (all wins),
    # and lean positive because the wins are more recent.
    assert form_delta > 0


def test_decay_makes_recent_fixtures_dominant():
    """Two teams with identical W/D/L totals but the win in a different
    recency slot must produce different form_deltas — the more-recent
    win yields the higher score. Uses a 3-game sample so the comparison
    is sharp: same point total, different ordering."""
    win_first = [
        _fx(1, hours_ago=1, gf=3, ga=0),  # WIN, freshest
        _fx(2, hours_ago=2, gf=0, ga=3),  # LOSS
        _fx(3, hours_ago=3, gf=1, ga=1),  # DRAW
    ]
    loss_first = [
        _fx(1, hours_ago=1, gf=0, ga=3),  # LOSS, freshest
        _fx(2, hours_ago=2, gf=3, ga=0),  # WIN
        _fx(3, hours_ago=3, gf=1, ga=1),  # DRAW
    ]
    fw = compute_form_delta(win_first)
    fl = compute_form_delta(loss_first)
    assert fw is not None and fl is not None
    # Same raw point totals (4 across 3 games), but the win-first team
    # carries its win at higher weight ⇒ higher form_delta.
    assert fw[0] > fl[0]


def test_filters_to_status_ft_only():
    # Three FT + lots of POST — only the FT should count.
    fixtures = [
        _fx(1, hours_ago=1, gf=2, ga=0),
        _fx(2, hours_ago=2, gf=0, ga=0, status="POST"),
        _fx(3, hours_ago=3, gf=1, ga=1),
        _fx(4, hours_ago=4, gf=0, ga=0, status="CANC"),
        _fx(5, hours_ago=5, gf=2, ga=1),
    ]
    result = compute_form_delta(fixtures)
    assert result is not None
    _, sample = result
    assert sample == 3  # only the three FT


def test_min_sample_size_threshold_is_inclusive():
    # Exactly MIN_SAMPLE_SIZE FT fixtures → returns a value, not None.
    fixtures = [_fx(i, hours_ago=i, gf=1, ga=1) for i in range(1, MIN_SAMPLE_SIZE + 1)]
    result = compute_form_delta(fixtures)
    assert result is not None
