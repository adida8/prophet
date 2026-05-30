"""Tests for the Slice B lineup fetcher (api-football /fixtures/lineups).

Async functions are driven via `asyncio.run` rather than pytest-asyncio
so the test suite stays portable across environments that don't have
the marker plugin installed.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from desk.data.api_football.cache import APIFootballCache, LineupRow
from desk.data.api_football.client import APIFootballResponse
from desk.data.api_football.lineups import (
    _parse_lineup_entry,
    fetch_lineups_for_fixture,
    refresh_lineup_for_match,
    resolve_fixture_id,
)


# ── fakes ─────────────────────────────────────────────────────────────

class FakeClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def get(self, path: str, *, params: dict | None = None) -> APIFootballResponse:
        self.calls.append((path, params or {}))
        payload = self.responses.get(path)
        if payload is None:
            raise AssertionError(f"unscripted call to {path}")
        return APIFootballResponse(payload=payload, rate_limit=None)


def _cache() -> APIFootballCache:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    f.close()
    return APIFootballCache(Path(f.name))


def _run(coro):
    return asyncio.run(coro)


# ── _parse_lineup_entry ───────────────────────────────────────────────

def test_parse_lineup_entry_full_xi_is_confirmed() -> None:
    entry = {
        "team": {"id": 33, "name": "France"},
        "coach": {"id": 1, "name": "Didier Deschamps"},
        "formation": "4-3-3",
        "startXI": [
            {"player": {"id": i, "name": f"Player{i}"}} for i in range(1, 12)
        ],
        "substitutes": [
            {"player": {"id": 100, "name": "Sub1"}},
        ],
    }
    row = _parse_lineup_entry(
        entry, fixture_id=999, fetched_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert row is not None
    assert row.fixture_id == 999
    assert row.api_football_team_id == 33
    assert row.state == "confirmed"
    assert row.formation == "4-3-3"
    assert row.coach_name == "Didier Deschamps"
    assert len(row.starters) == 11
    assert row.starters[0] == "Player1"
    assert row.substitutes == ("Sub1",)


def test_parse_lineup_entry_partial_xi_is_predicted() -> None:
    entry = {
        "team": {"id": 33, "name": "France"},
        "startXI": [{"player": {"id": 1, "name": "OnlyOne"}}],
    }
    row = _parse_lineup_entry(
        entry, fixture_id=1, fetched_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert row is not None
    assert row.state == "predicted"
    assert len(row.starters) == 1


def test_parse_lineup_entry_drops_malformed() -> None:
    entry = {"team": {}, "startXI": []}
    row = _parse_lineup_entry(
        entry, fixture_id=1, fetched_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    assert row is None


# ── fetch_lineups_for_fixture ────────────────────────────────────────

def test_fetch_lineups_for_fixture_ok() -> None:
    client = FakeClient(responses={
        "/fixtures/lineups": {
            "response": [
                {
                    "team": {"id": 33, "name": "France"},
                    "formation": "4-3-3",
                    "startXI": [
                        {"player": {"id": i, "name": f"FRA{i}"}} for i in range(11)
                    ],
                    "substitutes": [],
                },
                {
                    "team": {"id": 16, "name": "Mexico"},
                    "formation": "4-2-3-1",
                    "startXI": [
                        {"player": {"id": 100 + i, "name": f"MEX{i}"}} for i in range(11)
                    ],
                    "substitutes": [],
                },
            ],
        },
    })
    status, rows = _run(fetch_lineups_for_fixture(fixture_id=42, client=client))
    assert status == "ok"
    assert len(rows) == 2
    assert {r.api_football_team_id for r in rows} == {33, 16}
    assert all(r.state == "confirmed" for r in rows)


def test_fetch_lineups_for_fixture_no_response() -> None:
    client = FakeClient(responses={"/fixtures/lineups": {"response": []}})
    status, rows = _run(fetch_lineups_for_fixture(fixture_id=42, client=client))
    assert status == "no_lineups"
    assert rows == []


# ── resolve_fixture_id ────────────────────────────────────────────────

def test_resolve_fixture_id_cache_hit_skips_call() -> None:
    cache = _cache()
    cache.upsert_fixture_resolution(
        match_id="fb-wc26-fra-mex-20260612",
        api_football_fixture_id=999,
        home_team_id=33, away_team_id=16,
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
    )
    client = FakeClient(responses={})
    out = _run(resolve_fixture_id(
        match_id="fb-wc26-fra-mex-20260612",
        home_team_id=33, away_team_id=16,
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        season=2026, client=client, cache=cache,
    ))
    assert out == 999
    assert client.calls == []


def test_resolve_fixture_id_cache_miss_fetches_and_writes() -> None:
    cache = _cache()
    target_ko = datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc)
    client = FakeClient(responses={
        "/fixtures": {
            "response": [
                {
                    "fixture": {"id": 12345, "date": "2026-06-12T19:00:00+00:00"},
                    "teams": {
                        "home": {"id": 33},
                        "away": {"id": 16},
                    },
                },
                {
                    "fixture": {"id": 99999, "date": "2026-06-12T19:00:00+00:00"},
                    "teams": {
                        "home": {"id": 33},
                        "away": {"id": 99},
                    },
                },
            ],
        },
    })
    out = _run(resolve_fixture_id(
        match_id="fb-wc26-fra-mex-20260612",
        home_team_id=33, away_team_id=16,
        kickoff_utc=target_ko,
        season=2026, client=client, cache=cache,
    ))
    assert out == 12345
    cached = cache.fixture_resolution_for("fb-wc26-fra-mex-20260612")
    assert cached is not None
    assert cached.api_football_fixture_id == 12345


def test_resolve_fixture_id_returns_none_on_no_match() -> None:
    cache = _cache()
    client = FakeClient(responses={
        "/fixtures": {"response": [
            {
                "fixture": {"id": 1, "date": "2026-06-12T19:00:00+00:00"},
                "teams": {"home": {"id": 33}, "away": {"id": 99}},
            },
        ]},
    })
    out = _run(resolve_fixture_id(
        match_id="x", home_team_id=33, away_team_id=16,
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        season=2026, client=client, cache=cache,
    ))
    assert out is None


# ── refresh_lineup_for_match (top-level) ─────────────────────────────

def test_refresh_lineup_writes_to_cache() -> None:
    cache = _cache()
    cache.upsert_team_resolution("fra", 33, source_label="test")
    cache.upsert_team_resolution("mex", 16, source_label="test")
    cache.upsert_fixture_resolution(
        match_id="fb-wc26-fra-mex-20260612",
        api_football_fixture_id=999,
        home_team_id=33, away_team_id=16,
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
    )
    client = FakeClient(responses={
        "/fixtures/lineups": {
            "response": [
                {
                    "team": {"id": 33, "name": "France"},
                    "formation": "4-3-3",
                    "startXI": [
                        {"player": {"id": i, "name": f"FRA{i}"}} for i in range(11)
                    ],
                    "substitutes": [],
                },
                {
                    "team": {"id": 16, "name": "Mexico"},
                    "formation": "4-4-2",
                    "startXI": [
                        {"player": {"id": 100 + i, "name": f"MEX{i}"}} for i in range(11)
                    ],
                    "substitutes": [],
                },
            ],
        },
    })
    out = _run(refresh_lineup_for_match(
        match_id="fb-wc26-fra-mex-20260612",
        home_iso3="fra", away_iso3="mex",
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        season=2026, client=client, cache=cache,
    ))
    assert out.status == "ok"
    assert out.home_lineup is not None
    assert out.away_lineup is not None
    home = cache.lineup_for(fixture_id=999, api_football_team_id=33)
    assert home is not None
    assert home.state == "confirmed"
    assert len(home.starters) == 11


def test_refresh_lineup_skips_when_team_resolution_missing() -> None:
    cache = _cache()
    cache.upsert_team_resolution("fra", 33, source_label="test")
    client = FakeClient(responses={})
    out = _run(refresh_lineup_for_match(
        match_id="x", home_iso3="fra", away_iso3="mex",
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        season=2026, client=client, cache=cache,
    ))
    assert out.status == "no_team_id"
    assert client.calls == []
