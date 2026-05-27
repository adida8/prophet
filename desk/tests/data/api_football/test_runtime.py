"""APIFootballRuntime — read-only hot path over the sqlite cache."""

from __future__ import annotations

from desk.data.api_football.cache import APIFootballCache
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
