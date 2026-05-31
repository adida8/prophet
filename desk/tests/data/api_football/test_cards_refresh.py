"""Q5 — `desk fetch-cards` orchestrator (cards_refresh.py).

Verifies the refresh path: resolve team_id (cached), pull /players,
read suspended player_ids from the injuries cache, write rows back.
Auth-abort short-circuits the loop (mirror of injuries_refresh).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from desk.data.api_football.cache import APIFootballCache, InjuryRow
from desk.data.api_football.cards_refresh import (
    CardRefreshOutcome,
    refresh_cards_all,
    refresh_cards_one,
)
from desk.data.api_football.client import APIFootballError


@dataclass
class _Resp:
    payload: dict


class _FakeClient:
    def __init__(self):
        self._by_key: dict[tuple, _Resp | APIFootballError] = {}
        self.calls: list[tuple] = []

    def expect(self, path, params, payload=None, error=None):
        key = (path, tuple(sorted((params or {}).items())))
        self._by_key[key] = error or _Resp(payload=payload or {})

    async def get(self, path, *, params=None):
        params = params or {}
        key = (path, tuple(sorted(params.items())))
        self.calls.append(key)
        if key not in self._by_key:
            raise APIFootballError("permanent", f"unexpected {path} {params}")
        r = self._by_key[key]
        if isinstance(r, APIFootballError):
            raise r
        return r


def _players_entry(*, player_id, team_id, yellows=0, league_id=1):
    return {
        "player": {"id": player_id, "name": f"Player {player_id}"},
        "statistics": [{
            "team":   {"id": team_id, "name": "France"},
            "league": {"id": league_id, "season": 2026,
                       "name": "World Cup"},
            "games":  {"position": "Midfielder"},
            "cards":  {"yellow": yellows, "yellowred": 0, "red": 0},
        }],
    }


@pytest.fixture
def cache(tmp_path):
    return APIFootballCache(tmp_path / "api_football.db")


def test_refresh_cards_one_writes_rows_and_flags_at_risk(cache):
    """Happy path: team_id is cached, /players returns two players,
    one with 1 yellow (at-risk for WC26 threshold=2)."""
    cache.upsert_team_resolution("fra", 2, source_label="test")
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "2", "season": "2026", "league": "1"},
        payload={"response": [
            _players_entry(player_id=10, team_id=2, yellows=1),
            _players_entry(player_id=11, team_id=2, yellows=0),
        ]},
    )
    outcome = asyncio.run(refresh_cards_one(
        "fra", season=2026, competition="wc26", league_id=1,
        client=client, cache=cache,
    ))
    assert outcome.status == "ok"
    assert outcome.team_id == 2
    assert outcome.n_rows == 2
    assert outcome.n_at_risk == 1

    rows = cache.cards_for_team(api_football_team_id=2, competition="wc26")
    by_id = {r.player_id: r for r in rows}
    assert by_id[10].is_at_risk
    assert not by_id[11].is_at_risk


def test_refresh_cards_one_reconciles_against_suspended_players(cache):
    """Suspended players from injuries cache are dropped from at-risk."""
    cache.upsert_team_resolution("eng", 10, source_label="test")
    cache.replace_injuries_for_team(10, [
        InjuryRow(
            api_football_team_id=10, player_id=99,
            player_name="Bellingham",
            type="Suspended", reason="Yellow accumulation",
            position="Midfielder",
            fetched_at=datetime.now(tz=timezone.utc).isoformat(),
        ),
    ])
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "10", "season": "2026", "league": "1"},
        payload={"response": [
            _players_entry(player_id=99, team_id=10, yellows=1),
            _players_entry(player_id=1,  team_id=10, yellows=1),
        ]},
    )
    asyncio.run(refresh_cards_one(
        "eng", season=2026, competition="wc26", league_id=1,
        client=client, cache=cache,
    ))
    rows = cache.cards_for_team(api_football_team_id=10, competition="wc26")
    by_id = {r.player_id: r for r in rows}
    assert not by_id[99].is_at_risk   # dropped — suspended
    assert by_id[1].is_at_risk        # genuine at-risk


def test_refresh_cards_one_handles_fetch_failure(cache):
    cache.upsert_team_resolution("bra", 6, source_label="test")
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "6", "season": "2026", "league": "1"},
        error=APIFootballError("quota", "rate limit"),
    )
    outcome = asyncio.run(refresh_cards_one(
        "bra", season=2026, competition="wc26", league_id=1,
        client=client, cache=cache,
    ))
    assert outcome.status == "fetch_failed"
    assert outcome.error == "quota"
    # No rows written to the cache on failure.
    assert cache.cards_for_team(
        api_football_team_id=6, competition="wc26",
    ) == []


def test_refresh_cards_all_aborts_on_auth_error(cache):
    """A single auth error short-circuits the whole loop."""
    cache.upsert_team_resolution("arg", 1, source_label="test")
    cache.upsert_team_resolution("fra", 2, source_label="test")
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "1", "season": "2026", "league": "1"},
        error=APIFootballError("auth", "bad key"),
    )
    # France would succeed if we got there.
    client.expect(
        "/players",
        {"team": "2", "season": "2026", "league": "1"},
        payload={"response": []},
    )
    outcomes = asyncio.run(refresh_cards_all(
        season=2026, client=client, cache=cache,
        iso3s=["arg", "fra"],
    ))
    # Stopped after the first auth error — France never queried.
    assert len(outcomes) == 1
    assert outcomes[0].iso3 == "arg"
    assert outcomes[0].status == "fetch_failed"
