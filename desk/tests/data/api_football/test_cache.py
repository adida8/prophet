"""APIFootballCache — schema + idempotent upserts.

Sqlite cache for api-football responses. Tests cover team resolution,
fixture-results upsert, recent_fixtures filter on status FT, and
form_delta read/write.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from desk.data.api_football.cache import (
    APIFootballCache, CardAccumulationRow, FixtureResult,
)


@pytest.fixture
def cache(tmp_path):
    return APIFootballCache(tmp_path / "api_football.db")


def _fx(team_id: int, fixture_id: int, hours_ago: int,
        goals_for: int, goals_against: int, status: str = "FT") -> FixtureResult:
    return FixtureResult(
        api_football_team_id=team_id,
        fixture_id=fixture_id,
        played_at=datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago),
        opponent_team_id=999,
        team_goals=goals_for,
        opponent_goals=goals_against,
        status_short=status,
    )


def test_team_resolution_upsert_then_lookup(cache):
    cache.upsert_team_resolution("fra", 2, source_label="test")
    assert cache.team_id_for_iso3("fra") == 2

    # Idempotent — second upsert overwrites.
    cache.upsert_team_resolution("fra", 3, source_label="test-2")
    assert cache.team_id_for_iso3("fra") == 3


def test_team_resolution_iso3_case_insensitive(cache):
    cache.upsert_team_resolution("FRA", 2, source_label="test")
    assert cache.team_id_for_iso3("fra") == 2
    assert cache.team_id_for_iso3("FRA") == 2


def test_team_resolution_missing_returns_none(cache):
    assert cache.team_id_for_iso3("xyz") is None


def test_recent_fixtures_filters_to_ft_and_orders_desc(cache):
    cache.upsert_fixture_results([
        _fx(7, 100, hours_ago=72, goals_for=1, goals_against=2),  # loss, oldest
        _fx(7, 101, hours_ago=48, goals_for=2, goals_against=2),  # draw
        _fx(7, 102, hours_ago=24, goals_for=3, goals_against=0),  # win, newest
        _fx(7, 103, hours_ago=12, goals_for=0, goals_against=0, status="POST"),  # postponed
    ])
    rows = cache.recent_fixtures(7, limit=10)
    # POST excluded; FT ordered desc by played_at.
    assert [r.fixture_id for r in rows] == [102, 101, 100]


def test_fixture_results_upsert_is_idempotent(cache):
    f = _fx(7, 100, hours_ago=24, goals_for=2, goals_against=1)
    cache.upsert_fixture_results([f, f])
    assert len(cache.recent_fixtures(7)) == 1


def test_form_delta_read_write(cache):
    cache.upsert_form_delta("bra", form_delta=0.7, sample_size=10)
    fd = cache.form_delta_for_iso3("bra")
    assert fd is not None
    assert fd.iso3 == "bra"
    assert fd.form_delta == pytest.approx(0.7)
    assert fd.sample_size == 10


def test_form_delta_missing_returns_none(cache):
    assert cache.form_delta_for_iso3("zzz") is None


def test_form_delta_upsert_overwrites(cache):
    cache.upsert_form_delta("bra", form_delta=0.7, sample_size=10)
    cache.upsert_form_delta("bra", form_delta=-0.3, sample_size=8)
    fd = cache.form_delta_for_iso3("bra")
    assert fd.form_delta == pytest.approx(-0.3)
    assert fd.sample_size == 8


def test_form_delta_carries_citation_provenance(cache):
    """Per data-layer spec §3.5: every externally-derived datum carries
    Citation (source_id, endpoint, fetched_at) + transform name."""
    ts = datetime(2026, 5, 28, 12, tzinfo=timezone.utc)
    cache.upsert_form_delta(
        "fra", form_delta=0.4, sample_size=10,
        source_endpoint="/fixtures?team=2&last=10",
        source_fetched_at=ts,
    )
    fd = cache.form_delta_for_iso3("fra")
    assert fd is not None
    assert fd.source_id == "api_football"
    assert fd.source_endpoint == "/fixtures?team=2&last=10"
    assert fd.source_fetched_at == ts.isoformat()
    assert fd.transform == "compute_form_delta"


def test_form_delta_default_citation_fields_when_not_passed(cache):
    """Old callers that don't pass citation kwargs still see populated
    defaults — no migration needed."""
    cache.upsert_form_delta("bra", form_delta=0.2, sample_size=5)
    fd = cache.form_delta_for_iso3("bra")
    assert fd.source_id == "api_football"
    assert fd.transform == "compute_form_delta"
    assert fd.source_endpoint == ""


def test_points_property_on_fixture_result(cache):
    win = _fx(7, 1, hours_ago=1, goals_for=3, goals_against=0)
    draw = _fx(7, 2, hours_ago=1, goals_for=1, goals_against=1)
    loss = _fx(7, 3, hours_ago=1, goals_for=0, goals_against=2)
    nogoals = _fx(7, 4, hours_ago=1, goals_for=0, goals_against=0, status="POST")
    # status POST is unrelated to points calculation — those are
    # filtered elsewhere; here we just check the points math.
    assert win.points == 3
    assert draw.points == 1
    assert loss.points == 0
    # Missing goals (None) = no points credited.
    blank = FixtureResult(
        api_football_team_id=7, fixture_id=99,
        played_at=datetime.now(tz=timezone.utc),
        opponent_team_id=None, team_goals=None, opponent_goals=None,
        status_short="FT",
    )
    assert blank.points == 0


# ── Q1 card_accumulation ──────────────────────────────────────────────

def _card(*, player_id: int, yellows: int, at_risk: int = 0,
          team_id: int = 33, name: str | None = None) -> CardAccumulationRow:
    return CardAccumulationRow(
        api_football_team_id=team_id,
        player_id=player_id,
        player_name=name or f"Player {player_id}",
        position="Midfielder",
        yellows=yellows, reds=0,
        at_risk=at_risk,
        competition="wc26",
        computed_at=datetime.now(tz=timezone.utc).isoformat(),
        source_endpoint="/players?team=33&season=2026&league=1",
    )


def test_card_accumulation_replace_then_read(cache):
    cache.replace_cards_for_team(33, "wc26", [
        _card(player_id=1, yellows=1, at_risk=1),
        _card(player_id=2, yellows=0),
    ])
    rows = cache.cards_for_team(api_football_team_id=33, competition="wc26")
    assert len(rows) == 2
    by_id = {r.player_id: r for r in rows}
    assert by_id[1].is_at_risk
    assert not by_id[2].is_at_risk


def test_card_accumulation_replace_overwrites_per_team_per_competition(cache):
    cache.replace_cards_for_team(33, "wc26", [
        _card(player_id=1, yellows=1, at_risk=1),
    ])
    # A subsequent refresh with a different player set wipes the first.
    cache.replace_cards_for_team(33, "wc26", [
        _card(player_id=2, yellows=0),
    ])
    rows = cache.cards_for_team(api_football_team_id=33, competition="wc26")
    assert [r.player_id for r in rows] == [2]


def test_card_accumulation_scoped_per_team_and_competition(cache):
    """Cards for different competitions / teams coexist independently."""
    cache.replace_cards_for_team(33, "wc26", [_card(player_id=1, yellows=1)])
    cache.replace_cards_for_team(33, "ucl",  [_card(player_id=9, yellows=2)])
    cache.replace_cards_for_team(44, "wc26", [_card(player_id=5, yellows=0, team_id=44)])

    rows_wc = cache.cards_for_team(api_football_team_id=33, competition="wc26")
    rows_uc = cache.cards_for_team(api_football_team_id=33, competition="ucl")
    rows_44 = cache.cards_for_team(api_football_team_id=44, competition="wc26")
    assert [r.player_id for r in rows_wc] == [1]
    assert [r.player_id for r in rows_uc] == [9]
    assert [r.player_id for r in rows_44] == [5]


def test_cards_for_team_empty_returns_empty_list(cache):
    rows = cache.cards_for_team(api_football_team_id=999, competition="wc26")
    assert rows == []
