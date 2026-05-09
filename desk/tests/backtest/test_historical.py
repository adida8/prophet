"""Tests for the historical loaders.

The Elo snapshot loader and market CSV loader are read-only — they
exercise the bundled data files committed under
`desk/data/backtest/`. Network-free.
"""

from __future__ import annotations

from datetime import date

import pytest

from desk.backtest.historical.elo import LookaheadError, get_elo, load_intl_elo_snapshot
from desk.backtest.historical.markets import load_tournament_matches
from desk.backtest.historical.results import winner_from_score
from desk.backtest.tournaments import TOURNAMENTS


# ── ELO ──────────────────────────────────────────────────────────────

def test_loads_pre_wc_2022_elo_snapshot() -> None:
    """The bundled 2022-11-20 snapshot returns Elo for known WC participants."""
    snap = load_intl_elo_snapshot(date(2022, 11, 20))
    assert get_elo(snap, "arg") > 2000           # Argentina pre-WC, top tier
    assert get_elo(snap, "ksa") < 1700           # Saudi Arabia, lowest seed
    assert get_elo(snap, "qat") > 1500           # host nation present


def test_lookahead_error_when_asof_predates_every_snapshot() -> None:
    with pytest.raises(LookaheadError):
        load_intl_elo_snapshot(date(2000, 1, 1))


def test_uses_latest_snapshot_at_or_before_asof() -> None:
    """Asking for a later date returns the most recent snapshot we have."""
    snap = load_intl_elo_snapshot(date(2099, 1, 1))
    assert "arg" in snap


def test_get_elo_default_for_unknown_team() -> None:
    snap = load_intl_elo_snapshot(date(2022, 11, 20))
    assert get_elo(snap, "xxx") == 1500.0
    assert get_elo(snap, "xxx", default=1234.0) == 1234.0


# ── MARKETS ──────────────────────────────────────────────────────────

def test_loads_all_64_wc_2022_matches_from_manual_csv() -> None:
    matches = load_tournament_matches(TOURNAMENTS["wc-2022"])
    assert len(matches) == 64

    arg_v_sau = next(m for m in matches if m.match_id == "wc22-c-arg-sau-20221122")
    assert arg_v_sau.team_a == "Argentina"
    assert arg_v_sau.team_b == "Saudi Arabia"
    assert arg_v_sau.winner_90min == "b"
    assert arg_v_sau.close_a < 1.5      # Argentina was a heavy favourite
    assert arg_v_sau.close_b > 10       # Saudi long-shot in closing odds


def test_market_implied_probabilities_devig_to_one() -> None:
    matches = load_tournament_matches(TOURNAMENTS["wc-2022"])
    final = next(m for m in matches if m.match_id == "wc22-fin-arg-fra-20221218")
    s = final.market_p_a + final.market_p_draw + final.market_p_b
    assert abs(s - 1.0) < 1e-9


# ── RESULTS ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b,expected", [
    (3, 1, "a"),
    (0, 2, "b"),
    (1, 1, "draw"),
    (3, 3, "draw"),     # AFC playoff style — draws on penalties NOT counted as wins
])
def test_winner_from_score(a: int, b: int, expected: str) -> None:
    assert winner_from_score(a, b) == expected
