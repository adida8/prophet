"""refresh_one + refresh_all — end-to-end orchestrator with fake client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballError
from desk.data.api_football.refresh import refresh_all, refresh_one


@dataclass
class _Resp:
    payload: dict


class _FakeClient:
    """Programmable scripted responder. Keyed on (path, sorted_param_tuple).
    On a miss, raises a clear error so the test fails loudly."""

    def __init__(self):
        self._responses: dict[tuple, _Resp | APIFootballError] = {}
        self.calls: list[tuple[str, dict]] = []

    def expect(self, path, params, payload=None, error=None):
        key = (path, tuple(sorted((params or {}).items())))
        self._responses[key] = error or _Resp(payload=payload or {})

    async def get(self, path, *, params=None):
        params = params or {}
        self.calls.append((path, params))
        key = (path, tuple(sorted(params.items())))
        if key not in self._responses:
            raise APIFootballError("permanent", f"unexpected call {path} {params}")
        resp = self._responses[key]
        if isinstance(resp, APIFootballError):
            raise resp
        return resp


def _ft_entry(fixture_id, team_id, gf, ga, hours_ago):
    """`team_id` is the FETCHED team. Half the time they're home, half away —
    use hours_ago parity to keep the test deterministic."""
    home = team_id if hours_ago % 2 == 0 else 999
    away = team_id if hours_ago % 2 == 1 else 999
    return {
        "fixture": {
            "id": fixture_id,
            "date": f"2026-05-{(hours_ago % 28) + 1:02d}T18:00:00+00:00",
            "status": {"short": "FT"},
        },
        "teams": {
            "home": {"id": home}, "away": {"id": away},
        },
        "goals": {
            "home": gf if home == team_id else ga,
            "away": gf if away == team_id else ga,
        },
    }


@pytest.fixture
def cache(tmp_path):
    return APIFootballCache(tmp_path / "api_football.db")


def test_refresh_one_full_path(cache):
    client = _FakeClient()
    client.expect("/teams", {"search": "France"}, payload={
        "response": [{"team": {"id": 2, "name": "France", "national": True}}],
    })
    client.expect("/fixtures", {"team": "2", "last": "10"}, payload={
        "response": [_ft_entry(i, team_id=2, gf=2, ga=1, hours_ago=i)
                     for i in range(10)],
    })

    outcome = asyncio.run(refresh_one("fra", client=client, cache=cache))
    assert outcome.status == "resolved_then_ok"
    assert outcome.team_id == 2
    assert outcome.sample_size == 10
    # 10 wins (gf=2 > ga=1) → form_delta = 3.0 - LONG_RUN_BASELINE_PPG (1.5) = +1.5.
    assert outcome.form_delta == pytest.approx(1.5)

    # Cache reflects the work.
    assert cache.team_id_for_iso3("fra") == 2
    cached_fd = cache.form_delta_for_iso3("fra")
    assert cached_fd is not None
    assert cached_fd.form_delta == pytest.approx(1.5)


def test_refresh_one_uses_cached_team_id(cache):
    cache.upsert_team_resolution("bra", 6, source_label="test")
    client = _FakeClient()
    # No /teams call should fire — only /fixtures.
    client.expect("/fixtures", {"team": "6", "last": "10"}, payload={
        "response": [_ft_entry(i, team_id=6, gf=1, ga=1, hours_ago=i)
                     for i in range(5)],
    })
    outcome = asyncio.run(refresh_one("bra", client=client, cache=cache))
    assert outcome.status == "ok"  # not "resolved_then_ok" — id was cached
    assert outcome.team_id == 6
    paths = [p for p, _ in client.calls]
    assert paths == ["/fixtures"]


def test_refresh_one_skips_unknown_iso3(cache):
    client = _FakeClient()
    outcome = asyncio.run(refresh_one("xyz", client=client, cache=cache))
    assert outcome.status == "no_team_id"
    assert client.calls == []


def test_refresh_one_handles_fetch_failure(cache):
    cache.upsert_team_resolution("fra", 2, source_label="test")
    client = _FakeClient()
    client.expect("/fixtures", {"team": "2", "last": "10"},
                  error=APIFootballError("transient", "boom"))
    outcome = asyncio.run(refresh_one("fra", client=client, cache=cache))
    assert outcome.status == "fetch_failed"
    assert outcome.team_id == 2
    assert "boom" in (outcome.error or "")


def test_refresh_all_aborts_on_auth_failure(cache):
    """An auth failure on the *first* call must abort the loop — there's
    no point burning the daily quota probing a dead key. Other teams
    in the queue should NOT be attempted."""
    client = _FakeClient()
    # Whatever the first call is, return auth error.
    client.expect("/teams", {"search": "France"},
                  error=APIFootballError("auth", "401"))

    outcomes = asyncio.run(refresh_all(
        client=client, cache=cache, iso3s=["fra", "bra"],
    ))
    # First call fired, second never did.
    paths = [p for p, _ in client.calls]
    assert paths == ["/teams"]
    # We surface one error outcome and stop.
    assert len(outcomes) == 1
    assert outcomes[0].error.startswith("auth")


def test_refresh_all_continues_past_transient_errors(cache):
    """A transient on team A must not block team B."""
    client = _FakeClient()
    # FRA: /teams returns transient.
    client.expect("/teams", {"search": "France"},
                  error=APIFootballError("transient", "timeout"))
    # BRA: full happy path.
    client.expect("/teams", {"search": "Brazil"}, payload={
        "response": [{"team": {"id": 6, "name": "Brazil", "national": True}}],
    })
    client.expect("/fixtures", {"team": "6", "last": "10"}, payload={
        "response": [_ft_entry(i, team_id=6, gf=2, ga=0, hours_ago=i)
                     for i in range(10)],
    })

    outcomes = asyncio.run(refresh_all(
        client=client, cache=cache, iso3s=["fra", "bra"],
    ))
    assert len(outcomes) == 2
    statuses = {o.iso3: o.status for o in outcomes}
    assert statuses["fra"] == "no_team_id"   # transient surfaces via resolve_team_id
    assert statuses["bra"] == "resolved_then_ok"
