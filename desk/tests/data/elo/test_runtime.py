"""EloRuntime — live-then-seed fallback semantics."""

from __future__ import annotations

from desk.data.elo.cache import EloCache
from desk.data.elo.runtime import EloRuntime


def test_returns_seed_when_cache_absent(tmp_path):
    rt = EloRuntime(tmp_path / "nope.db")
    # France seed value from elo_seed.NATIONAL_ELO is 2030.0.
    assert rt.national_elo("fra") == 2030.0
    # Source label flows from seed → "wiki" for known, "stub" for unknown.
    assert rt.national_elo_source("fra") == "wiki"
    assert rt.national_elo_source("zzz") == "stub"
    rt.close()


def test_live_value_wins_when_cached(tmp_path):
    db = tmp_path / "elo.db"
    with EloCache(db) as cache:
        cache.upsert_national(
            "fra", 2099.0,
            source_id="eloratings", source_url="x",
        )
    rt = EloRuntime(db)
    assert rt.national_elo("fra") == 2099.0
    assert rt.national_elo_source("fra") == "eloratings"
    rt.close()


def test_live_value_falls_back_for_uncached_iso3(tmp_path):
    db = tmp_path / "elo.db"
    with EloCache(db) as cache:
        cache.upsert_national("fra", 2099.0,
                              source_id="eloratings", source_url="x")
    rt = EloRuntime(db)
    # Brazil isn't in the cache → fall back to seed (1970.0 per
    # elo_seed.NATIONAL_ELO).
    assert rt.national_elo("bra") == 1970.0
    assert rt.national_elo_source("bra") == "wiki"
    rt.close()


def test_club_path_mirrors_national(tmp_path):
    db = tmp_path / "elo.db"
    with EloCache(db) as cache:
        cache.upsert_club("epl-mci", 1850.0,
                          source_id="clubelo", source_url="x")
    rt = EloRuntime(db)
    assert rt.club_elo("epl-mci") == 1850.0
    assert rt.club_elo_source("epl-mci") == "clubelo"
    # Unknown club_id → stub.
    assert rt.club_elo_source("epl-xyz") == "stub"
    rt.close()


def test_context_manager(tmp_path):
    with EloRuntime(tmp_path / "nope.db") as rt:
        assert rt.national_elo("fra") == 2030.0
