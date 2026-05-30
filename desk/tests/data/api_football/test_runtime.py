"""APIFootballRuntime — read-only hot path over the sqlite cache."""

from __future__ import annotations

from datetime import datetime, timezone

from desk.data.api_football.cache import APIFootballCache, CardAccumulationRow
from desk.data.api_football.runtime import APIFootballRuntime


def test_runtime_returns_none_when_cache_absent(tmp_path):
    rt = APIFootballRuntime(tmp_path / "does_not_exist.db")
    assert rt.form_delta_for_iso3("fra") is None
    rt.close()


def test_runtime_returns_form_delta_when_cached(tmp_path):
    db = tmp_path / "api_football.db"
    cache = APIFootballCache(db)
    cache.upsert_form_delta("fra", form_delta=0.4, sample_size=10)
    cache.close()

    rt = APIFootballRuntime(db)
    assert rt.form_delta_for_iso3("fra") == 0.4
    assert rt.form_delta_for_iso3("xxx") is None
    rt.close()


def test_runtime_returns_none_for_empty_iso3(tmp_path):
    rt = APIFootballRuntime(tmp_path / "nodb.db")
    assert rt.form_delta_for_iso3("") is None
    rt.close()


def test_runtime_is_a_context_manager(tmp_path):
    db = tmp_path / "api_football.db"
    cache = APIFootballCache(db)
    cache.upsert_form_delta("bra", form_delta=-0.2, sample_size=5)
    cache.close()

    with APIFootballRuntime(db) as rt:
        assert rt.form_delta_for_iso3("bra") == -0.2


# ── Q2 cards_for_iso3 ────────────────────────────────────────────────

def test_cards_for_iso3_returns_rows_when_cached(tmp_path):
    db = tmp_path / "api_football.db"
    cache = APIFootballCache(db)
    cache.upsert_team_resolution("fra", 2, source_label="test")
    cache.replace_cards_for_team(2, "wc26", [
        CardAccumulationRow(
            api_football_team_id=2, player_id=1, player_name="A",
            position="Midfielder", yellows=1, reds=0, at_risk=1,
            competition="wc26",
            computed_at=datetime.now(tz=timezone.utc).isoformat(),
        ),
    ])
    cache.close()

    with APIFootballRuntime(db) as rt:
        rows = rt.cards_for_iso3("fra", competition="wc26")
    assert len(rows) == 1
    assert rows[0].player_name == "A"


def test_cards_for_iso3_empty_when_no_team_resolution(tmp_path):
    db = tmp_path / "api_football.db"
    cache = APIFootballCache(db)
    cache.close()
    with APIFootballRuntime(db) as rt:
        # Team never resolved to api-football id — silent empty list.
        assert rt.cards_for_iso3("fra", competition="wc26") == []


def test_cards_for_iso3_empty_when_cache_absent(tmp_path):
    with APIFootballRuntime(tmp_path / "no.db") as rt:
        assert rt.cards_for_iso3("fra", competition="wc26") == []


def test_cards_for_iso3_scoped_per_competition(tmp_path):
    db = tmp_path / "api_football.db"
    cache = APIFootballCache(db)
    cache.upsert_team_resolution("eng", 10, source_label="test")
    cache.replace_cards_for_team(10, "wc26", [
        CardAccumulationRow(
            api_football_team_id=10, player_id=1, player_name="A",
            position=None, yellows=1, reds=0, at_risk=1,
            competition="wc26",
            computed_at=datetime.now(tz=timezone.utc).isoformat(),
        ),
    ])
    cache.close()
    with APIFootballRuntime(db) as rt:
        assert len(rt.cards_for_iso3("eng", competition="wc26")) == 1
        assert rt.cards_for_iso3("eng", competition="ucl") == []
