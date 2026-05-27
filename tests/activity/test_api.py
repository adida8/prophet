"""Smoke tests for the activity router.

The DB layer is faked — these tests verify route plumbing, request/response
shapes, cookie handling, and the rate-limit branches in `post_vote`. The
Railway Postgres deploy is the integration test for real SQL execution.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from activity import db as activity_db
from activity.anon import ANON_COOKIE
from activity.router import REACTIONS, VOTE_PER_ANON_DAILY_MAX, router


# --- fake asyncpg pool ------------------------------------------------------


class _FakeConn:
    def __init__(self, store: "_FakeStore") -> None:
        self.store = store

    async def execute(self, sql: str, *args: Any) -> str:
        self.store.executes.append((sql, args))
        s = sql.lower().lstrip()
        if s.startswith("insert into match_views"):
            self.store.views.append(args)
        elif s.startswith("insert into match_reactions"):
            match_id, anon_id, reaction = args[0], args[1], args[2]
            self.store.reactions[(match_id, anon_id)] = {
                "reaction": reaction,
                "voted_at": self.store.now,
                "locked_at": None,
            }
        elif s.startswith("update match_reactions set locked_at"):
            match_id, anon_id = args
            row = self.store.reactions.get((match_id, anon_id))
            if row:
                row["locked_at"] = self.store.now
        elif s.startswith("update match_reactions"):
            match_id, anon_id, reaction = args
            row = self.store.reactions[(match_id, anon_id)]
            row["reaction"] = reaction
            row["voted_at"] = self.store.now
        return "OK"

    async def fetchval(self, sql: str, *args: Any) -> Any:
        s = sql.lower()
        if "count(*) from match_reactions" in s:
            anon_id = args[0]
            return sum(
                1 for (_, aid) in self.store.reactions if aid == anon_id
            ) + self.store.extra_daily_count
        if "now() - $1" in s:
            voted_at = args[0]
            return self.store.now - voted_at
        return None

    async def fetchrow(self, sql: str, *args: Any) -> Optional[dict]:
        s = sql.lower()
        if "from match_reactions" in s and "where match_id" in s and "anon_id" in s:
            match_id, anon_id = args
            return self.store.reactions.get((match_id, anon_id))
        if "from match_aggregates" in s:
            match_id, = args
            return self.store.aggregates.get(match_id)
        return None


class _PoolCtx:
    def __init__(self, store: "_FakeStore") -> None:
        self.store = store

    async def __aenter__(self) -> _FakeConn:
        return _FakeConn(self.store)

    async def __aexit__(self, *exc) -> None:
        return None


class _FakePool:
    def __init__(self, store: "_FakeStore") -> None:
        self.store = store

    def acquire(self) -> _PoolCtx:
        return _PoolCtx(self.store)


class _FakeStore:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.views: list[tuple] = []
        self.reactions: dict[tuple, dict] = {}
        self.aggregates: dict[str, dict] = {}
        self.executes: list[tuple] = []
        self.extra_daily_count = 0


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> _FakeStore:
    s = _FakeStore()
    monkeypatch.setattr(activity_db, "_pool", _FakePool(s))
    return s


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# --- view ------------------------------------------------------------------


def test_post_view_inserts_and_sets_cookie(client: TestClient, store: _FakeStore) -> None:
    r = client.post("/api/activity/view", json={"match_id": "fb-wc26-arg-aut-20260612"})
    assert r.status_code == 204
    assert ANON_COOKIE in r.cookies
    assert len(store.views) == 1
    inserted_match, anon_id, ip_hash = store.views[0][0], store.views[0][1], store.views[0][2]
    assert inserted_match == "fb-wc26-arg-aut-20260612"
    assert anon_id == r.cookies[ANON_COOKIE]
    assert len(ip_hash) == 32


def test_post_view_reuses_existing_cookie(client: TestClient, store: _FakeStore) -> None:
    client.cookies.set(ANON_COOKIE, "fixed-anon-uuid")
    r = client.post("/api/activity/view", json={"match_id": "fb-test-m1"})
    assert r.status_code == 204
    assert store.views[0][1] == "fixed-anon-uuid"


def test_post_view_rejects_empty_match_id(client: TestClient, store: _FakeStore) -> None:
    r = client.post("/api/activity/view", json={"match_id": ""})
    assert r.status_code == 422


# --- vote ------------------------------------------------------------------


@pytest.mark.parametrize("reaction", REACTIONS)
def test_post_vote_first_vote(reaction: str, client: TestClient, store: _FakeStore) -> None:
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": reaction})
    assert r.status_code == 200
    body = r.json()
    assert body["your_vote"] == reaction
    assert body["locked_at"] is None
    assert len(store.reactions) == 1


def test_post_vote_rejects_unknown_reaction(client: TestClient, store: _FakeStore) -> None:
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": "bullish"})
    assert r.status_code == 422


def test_post_vote_change_in_cooldown_returns_429(client: TestClient, store: _FakeStore) -> None:
    client.cookies.set(ANON_COOKIE, "anon-a")
    store.reactions[("fb-test-m1", "anon-a")] = {
        "reaction": "fair_call",
        "voted_at": store.now - timedelta(seconds=5),
        "locked_at": None,
    }
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": "sharp_call"})
    assert r.status_code == 429
    assert r.json()["detail"] == "vote_change_cooldown"


def test_post_vote_change_after_cooldown_updates(client: TestClient, store: _FakeStore) -> None:
    client.cookies.set(ANON_COOKIE, "anon-b")
    store.reactions[("fb-test-m1", "anon-b")] = {
        "reaction": "fair_call",
        "voted_at": store.now - timedelta(minutes=2),
        "locked_at": None,
    }
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": "sharp_call"})
    assert r.status_code == 200
    assert store.reactions[("fb-test-m1", "anon-b")]["reaction"] == "sharp_call"


def test_post_vote_locks_after_24h_and_rejects(client: TestClient, store: _FakeStore) -> None:
    client.cookies.set(ANON_COOKIE, "anon-c")
    store.reactions[("fb-test-m1", "anon-c")] = {
        "reaction": "sharp_call",
        "voted_at": store.now - timedelta(hours=25),
        "locked_at": None,
    }
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": "off_mark"})
    assert r.status_code == 409
    assert store.reactions[("fb-test-m1", "anon-c")]["locked_at"] is not None


def test_post_vote_rejects_already_locked(client: TestClient, store: _FakeStore) -> None:
    client.cookies.set(ANON_COOKIE, "anon-d")
    store.reactions[("fb-test-m1", "anon-d")] = {
        "reaction": "sharp_call",
        "voted_at": store.now - timedelta(hours=48),
        "locked_at": store.now - timedelta(hours=24),
    }
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": "off_mark"})
    assert r.status_code == 409
    assert r.json()["detail"] == "vote_locked"


def test_post_vote_daily_ceiling(client: TestClient, store: _FakeStore) -> None:
    store.extra_daily_count = VOTE_PER_ANON_DAILY_MAX
    r = client.post("/api/activity/vote", json={"match_id": "fb-test-m1", "reaction": "sharp_call"})
    assert r.status_code == 429
    assert r.json()["detail"] == "vote_daily_limit"


# --- get -------------------------------------------------------------------


def test_get_unknown_match_returns_zero_aggregate(client: TestClient, store: _FakeStore) -> None:
    r = client.get("/api/activity/fb-test-m1")
    assert r.status_code == 200
    body = r.json()
    assert body["match_id"] == "fb-test-m1"
    assert body["views_24h"] == 0
    assert body["votes_total"] == 0
    assert body["display_views"] is False
    assert body["display_votes"] is False
    assert body["your_vote"] is None
    assert body["by_reaction"] == {r: 0 for r in REACTIONS}


def test_get_returns_aggregate_and_caller_vote(client: TestClient, store: _FakeStore) -> None:
    client.cookies.set(ANON_COOKIE, "anon-e")
    store.aggregates["fb-test-m1"] = {
        "views_24h": 68, "votes_total": 50,
        "sharp_call": 24, "fair_call": 15, "off_mark": 8, "wait_see": 3,
        "aligned_pct": 78,
        "refreshed_at": store.now,
    }
    store.reactions[("fb-test-m1", "anon-e")] = {
        "reaction": "sharp_call",
        "voted_at": store.now,
        "locked_at": None,
    }
    r = client.get("/api/activity/fb-test-m1")
    assert r.status_code == 200
    body = r.json()
    assert body["views_24h"] == 68
    assert body["votes_total"] == 50
    assert body["by_reaction"]["sharp_call"] == 24
    assert body["aligned_pct"] == 78
    assert body["your_vote"] == "sharp_call"
    assert body["display_views"] is True
    assert body["display_votes"] is True


def test_get_thresholds_hide_below_minimums(client: TestClient, store: _FakeStore) -> None:
    store.aggregates["fb-test-m1"] = {
        "views_24h": 9, "votes_total": 4,
        "sharp_call": 2, "fair_call": 1, "off_mark": 1, "wait_see": 0,
        "aligned_pct": 75,
        "refreshed_at": store.now,
    }
    r = client.get("/api/activity/fb-test-m1")
    body = r.json()
    assert body["display_views"] is False
    assert body["display_votes"] is False
