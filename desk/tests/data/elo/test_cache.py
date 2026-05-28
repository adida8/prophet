"""EloCache schema + idempotent upserts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desk.data.elo.cache import EloCache


@pytest.fixture
def cache(tmp_path):
    return EloCache(tmp_path / "elo.db")


def test_national_upsert_then_read(cache):
    cache.upsert_national(
        "fra", 2030.0,
        source_id="eloratings", source_url="https://eloratings.net/World.tsv",
    )
    row = cache.get_national("fra")
    assert row is not None
    assert row.elo == 2030.0
    assert row.source_id == "eloratings"


def test_national_iso3_case_insensitive(cache):
    cache.upsert_national(
        "FRA", 2030.0,
        source_id="eloratings", source_url="x",
    )
    assert cache.get_national("fra").elo == 2030.0
    assert cache.get_national("FRA").elo == 2030.0


def test_national_upsert_overwrites(cache):
    cache.upsert_national("fra", 2030.0,
                          source_id="eloratings", source_url="x")
    cache.upsert_national("fra", 2050.0,
                          source_id="eloratings", source_url="x")
    assert cache.get_national("fra").elo == 2050.0


def test_national_missing_returns_none(cache):
    assert cache.get_national("xxx") is None


def test_club_upsert_then_read(cache):
    cache.upsert_club(
        "epl-mci", 1825.5,
        source_id="clubelo", source_url="https://api.clubelo.com/ManCity",
    )
    row = cache.get_club("epl-mci")
    assert row is not None
    assert row.elo == pytest.approx(1825.5)
    assert row.source_id == "clubelo"


def test_list_methods_return_sorted(cache):
    cache.upsert_national("bra", 1970.0, source_id="e", source_url="x")
    cache.upsert_national("arg", 2140.0, source_id="e", source_url="x")
    rows = cache.list_nationals()
    assert [r.key for r in rows] == ["arg", "bra"]


def test_mark_fetch_round_trips(cache):
    cache.mark_fetch("eloratings", "ok")
    last = cache.last_fetch("eloratings")
    assert last is not None
    ts, status = last
    assert status == "ok"
    assert ts.tzinfo is not None


def test_provenance_fields_persisted(cache):
    ts = datetime(2026, 5, 28, 12, tzinfo=timezone.utc)
    cache.upsert_national(
        "fra", 2030.0,
        source_id="eloratings",
        source_url="https://www.eloratings.net/World.tsv",
        fetched_at=ts,
    )
    row = cache.get_national("fra")
    assert row.source_url == "https://www.eloratings.net/World.tsv"
    assert row.fetched_at == ts.isoformat()
    assert row.parser_version == "v1"
