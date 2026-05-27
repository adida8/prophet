"""ISO3 → api-football team_id resolution.

Mocks the httpx layer via a fake APIFootballClient that the resolver
can call exactly as if it were live. No network calls. Tests are sync
with `asyncio.run` so they don't need the pytest-asyncio plugin.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballError
from desk.data.api_football.teams import resolve_team_id


@dataclass
class _FakeResp:
    payload: dict


class _FakeClient:
    """Records every GET call and replays a queued list of responses."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.responses: list[_FakeResp | APIFootballError] = []

    def queue(self, payload):
        self.responses.append(_FakeResp(payload=payload))

    def queue_error(self, err: APIFootballError):
        self.responses.append(err)

    async def get(self, path, *, params=None):
        self.calls.append((path, params or {}))
        if not self.responses:
            raise APIFootballError("permanent", "no queued response")
        resp = self.responses.pop(0)
        if isinstance(resp, APIFootballError):
            raise resp
        return resp


@pytest.fixture
def cache(tmp_path):
    return APIFootballCache(tmp_path / "api_football.db")


def _resolve(iso3, client, cache, force=False):
    return asyncio.run(resolve_team_id(iso3, client=client, cache=cache, force=force))


def test_resolution_hits_api_and_persists(cache):
    client = _FakeClient()
    client.queue({
        "response": [{
            "team": {"id": 2, "name": "France", "national": True},
        }],
    })
    outcome = _resolve("fra", client, cache)
    assert outcome.status == "resolved"
    assert outcome.team_id == 2
    assert cache.team_id_for_iso3("fra") == 2
    assert len(client.calls) == 1


def test_cached_resolution_skips_api(cache):
    cache.upsert_team_resolution("bra", 6, source_label="test")
    client = _FakeClient()
    outcome = _resolve("bra", client, cache)
    assert outcome.status == "cached"
    assert outcome.team_id == 6
    assert client.calls == []


def test_force_reresolution_hits_api(cache):
    cache.upsert_team_resolution("bra", 6, source_label="test")
    client = _FakeClient()
    client.queue({
        "response": [{
            "team": {"id": 7, "name": "Brazil", "national": True},
        }],
    })
    outcome = _resolve("bra", client, cache, force=True)
    assert outcome.status == "resolved"
    assert outcome.team_id == 7
    assert cache.team_id_for_iso3("bra") == 7


def test_filters_to_national_team_only(cache):
    """The /teams?search= response can include club teams whose name
    happens to match. We must take the first `national == True` hit."""
    client = _FakeClient()
    client.queue({
        "response": [
            {"team": {"id": 100, "name": "England U21", "national": False}},
            {"team": {"id": 10,  "name": "England",     "national": True}},
            {"team": {"id": 999, "name": "England XI",  "national": False}},
        ],
    })
    outcome = _resolve("eng", client, cache)
    assert outcome.team_id == 10


def test_no_national_match_returns_no_match(cache):
    client = _FakeClient()
    client.queue({"response": [
        {"team": {"id": 1, "name": "Club X", "national": False}},
    ]})
    outcome = _resolve("fra", client, cache)
    assert outcome.status == "no_match"
    assert outcome.team_id is None
    assert cache.team_id_for_iso3("fra") is None


def test_unknown_iso3_does_not_hit_api(cache):
    client = _FakeClient()
    outcome = _resolve("xxx", client, cache)
    assert outcome.status == "unknown_iso3"
    assert client.calls == []


def test_api_error_surfaces_as_error_outcome(cache):
    client = _FakeClient()
    client.queue_error(APIFootballError("transient", "timeout"))
    outcome = _resolve("fra", client, cache)
    assert outcome.status == "error"
    assert "timeout" in (outcome.error or "")
