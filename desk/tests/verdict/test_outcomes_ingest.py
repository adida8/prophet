"""Outcomes ingest — match_id parsing + api-football fixture matching.

Uses a fake APIFootballClient (same shape as the resolver / refresh
test helpers) so no live calls happen.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballError
from desk.verdict.outcomes_ingest import (
    SETTLE_BUFFER, ingest_one, parse_match_id,
)


@dataclass
class _Resp:
    payload: dict


class _FakeClient:
    def __init__(self):
        self._scripts: dict[tuple, _Resp | APIFootballError] = {}
        self.calls: list[tuple] = []

    def expect(self, path, params, payload=None, error=None):
        key = (path, tuple(sorted((params or {}).items())))
        self._scripts[key] = error or _Resp(payload=payload or {})

    async def get(self, path, *, params=None):
        params = params or {}
        key = (path, tuple(sorted(params.items())))
        self.calls.append(key)
        if key not in self._scripts:
            raise APIFootballError("permanent", f"unexpected {path} {params}")
        r = self._scripts[key]
        if isinstance(r, APIFootballError):
            raise r
        return r


@pytest.fixture
def af_cache(tmp_path):
    return APIFootballCache(tmp_path / "api_football.db")


def _ft_fixture(*, home_id, away_id, home_goals, away_goals,
                date_iso="2026-06-12T19:00:00+00:00", status="FT"):
    return {
        "fixture": {"id": 1, "date": date_iso, "status": {"short": status}},
        "teams": {
            "home": {"id": home_id}, "away": {"id": away_id},
        },
        "goals": {"home": home_goals, "away": away_goals},
    }


# ── parse_match_id ────────────────────────────────────────────────────

def test_parse_match_id_canonical():
    parsed = parse_match_id("fb-wc26-fra-mex-20260612")
    assert parsed is not None
    comp, home, away, dt = parsed
    assert comp == "wc26"
    assert home == "fra"
    assert away == "mex"
    assert dt.date().isoformat() == "2026-06-12"


def test_parse_match_id_garbage_returns_none():
    assert parse_match_id("not-a-match-id") is None
    assert parse_match_id("fb-wc26-fra-mex-XXXX0612") is None


# ── ingest_one ────────────────────────────────────────────────────────

def test_ingest_one_returns_outcome_a_when_home_wins(af_cache):
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()
    client.expect("/fixtures", {"team": "2", "date": "2026-06-12"}, payload={
        "response": [_ft_fixture(home_id=2, away_id=16,
                                 home_goals=2, away_goals=1)],
    })
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)   # > 6h after kickoff
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    assert out.status == "ok"
    assert out.outcome == "a"


def test_ingest_one_returns_outcome_b_when_away_wins(af_cache):
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()
    client.expect("/fixtures", {"team": "2", "date": "2026-06-12"}, payload={
        "response": [_ft_fixture(home_id=2, away_id=16,
                                 home_goals=0, away_goals=3)],
    })
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    assert out.outcome == "b"


def test_ingest_one_returns_outcome_draw(af_cache):
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()
    client.expect("/fixtures", {"team": "2", "date": "2026-06-12"}, payload={
        "response": [_ft_fixture(home_id=2, away_id=16,
                                 home_goals=1, away_goals=1)],
    })
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    assert out.outcome == "draw"


def test_ingest_one_skips_when_not_settled(af_cache):
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()  # no expectations — should never be hit
    now = datetime(2026, 6, 12, 19, 30, tzinfo=timezone.utc)   # 30min in
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    assert out.status == "not_settled_yet"
    assert client.calls == []


def test_ingest_one_handles_unparseable_match_id(af_cache):
    out = asyncio.run(ingest_one(
        "bogus-id", client=_FakeClient(), af_cache=af_cache,
    ))
    assert out.status == "unparseable_match_id"


def test_ingest_one_handles_missing_team_id(af_cache):
    # Only home is resolved; away is missing.
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=_FakeClient(), af_cache=af_cache, now=now,
    ))
    assert out.status == "team_id_missing"


def test_ingest_one_returns_no_fixture_found(af_cache):
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()
    # Response contains a fixture but not vs team 16.
    client.expect("/fixtures", {"team": "2", "date": "2026-06-12"}, payload={
        "response": [_ft_fixture(home_id=2, away_id=99,
                                 home_goals=1, away_goals=0)],
    })
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    assert out.status == "no_fixture_found"


def test_ingest_one_tolerates_swapped_perspective(af_cache):
    """api-football may return the same fixture as away-vs-home in some
    edge cases. The fixture matching should still resolve."""
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()
    client.expect("/fixtures", {"team": "2", "date": "2026-06-12"}, payload={
        "response": [_ft_fixture(home_id=16, away_id=2,
                                 home_goals=0, away_goals=2)],
    })
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    # Home in payload was team 16 (mex), away was team 2 (fra). We
    # asked about fra-vs-mex. From team_a (fra)'s perspective, fra
    # was the away side and scored 2 goals; mex scored 0 → fra wins → "a".
    assert out.outcome == "a"


def test_ingest_one_returns_not_settled_when_status_not_ft(af_cache):
    af_cache.upsert_team_resolution("fra", 2, source_label="t")
    af_cache.upsert_team_resolution("mex", 16, source_label="t")
    client = _FakeClient()
    client.expect("/fixtures", {"team": "2", "date": "2026-06-12"}, payload={
        "response": [_ft_fixture(home_id=2, away_id=16,
                                 home_goals=1, away_goals=0, status="NS")],
    })
    now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    out = asyncio.run(ingest_one(
        "fb-wc26-fra-mex-20260612",
        client=client, af_cache=af_cache, now=now,
    ))
    assert out.status == "not_settled_yet"
