"""Injury Elo penalty math — bounded + counted types only."""

from __future__ import annotations

import pytest

from desk.data.api_football.cache import InjuryRow
from desk.data.api_football.injury_penalty import (
    DEFAULT_MINUTES_SHARE, INJURY_BASE_PENALTY, INJURY_MAX_TOTAL_ELO_PER_TEAM,
    compute_injury_penalty,
)


def _row(player_id=1, type_="Missing Fixture", position="Defender"):
    return InjuryRow(
        api_football_team_id=2, player_id=player_id,
        player_name=f"P{player_id}",
        type=type_, reason="Knock",
        position=position, fetched_at="2026-05-28T00:00:00Z",
    )


def test_empty_list_zero_penalty():
    penalty, n = compute_injury_penalty([])
    assert penalty == 0.0
    assert n == 0


def test_single_defender_penalty():
    rows = [_row(position="Defender")]
    penalty, n = compute_injury_penalty(rows)
    # Defender weight 1.0 × DEFAULT_MINUTES_SHARE × INJURY_BASE_PENALTY = 30.0
    assert penalty == pytest.approx(
        INJURY_BASE_PENALTY * 1.0 * DEFAULT_MINUTES_SHARE
    )
    assert n == 1


def test_goalkeeper_weighted_higher_than_defender():
    gk = compute_injury_penalty([_row(position="Goalkeeper")])
    df = compute_injury_penalty([_row(position="Defender")])
    assert gk[0] > df[0]
    # GK weight 1.5 vs Defender 1.0 → GK penalty is 1.5x.
    assert gk[0] == pytest.approx(1.5 * df[0])


def test_capped_at_max_total():
    """Many high-importance injuries should saturate at the per-team cap."""
    rows = [
        _row(player_id=i, position="Goalkeeper") for i in range(20)
    ]
    penalty, n = compute_injury_penalty(rows)
    assert penalty <= INJURY_MAX_TOTAL_ELO_PER_TEAM
    # n_counted reflects every counted player, even though penalty saturated.
    assert n == 20


def test_questionable_type_excluded():
    """Only Missing Fixture / Suspended count; Questionable doesn't."""
    rows = [
        _row(player_id=1, type_="Questionable"),
        _row(player_id=2, type_="Missing Fixture"),
    ]
    penalty, n = compute_injury_penalty(rows)
    # Only the Missing Fixture entry contributes.
    assert n == 1


def test_suspended_counts_same_as_missing_fixture():
    a = compute_injury_penalty([_row(player_id=1, type_="Missing Fixture")])
    b = compute_injury_penalty([_row(player_id=1, type_="Suspended")])
    assert a[0] == b[0]


def test_unknown_position_uses_default_weight():
    rows = [_row(position="UnknownRole")]
    penalty, n = compute_injury_penalty(rows)
    # DEFAULT_POSITION_WEIGHT = 0.8.
    assert penalty == pytest.approx(
        INJURY_BASE_PENALTY * 0.8 * DEFAULT_MINUTES_SHARE
    )
    assert n == 1


def test_position_none_falls_back_to_default():
    rows = [_row(position=None)]
    penalty, n = compute_injury_penalty(rows)
    assert n == 1
    assert penalty > 0
