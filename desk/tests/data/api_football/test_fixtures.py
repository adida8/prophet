"""api-football /fixtures payload normalisation.

Mirror the shape of a real response (truncated) and check that we
correctly compute `team_goals` vs `opponent_goals` regardless of which
side the queried team is on.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from desk.data.api_football.client import APIFootballError
from desk.data.api_football.fixtures import fetch_recent_fixtures


@dataclass
class _Resp:
    payload: dict


class _FakeClient:
    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error
        self.calls = []

    async def get(self, path, *, params=None):
        self.calls.append((path, params or {}))
        if self._error:
            raise self._error
        return _Resp(payload=self._payload or {"response": []})


def _entry(fixture_id, home_id, away_id, home_goals, away_goals,
           status="FT", date_iso="2026-05-20T18:00:00+00:00"):
    return {
        "fixture": {
            "id": fixture_id,
            "date": date_iso,
            "status": {"short": status},
        },
        "teams": {
            "home": {"id": home_id, "name": f"H{home_id}"},
            "away": {"id": away_id, "name": f"A{away_id}"},
        },
        "goals": {"home": home_goals, "away": away_goals},
    }


def _fetch(team_id, payload):
    client = _FakeClient(payload=payload)
    return asyncio.run(fetch_recent_fixtures(team_id, client=client, n=10))


def test_normalises_team_as_home_side():
    payload = {"response": [_entry(100, home_id=7, away_id=99, home_goals=2, away_goals=1)]}
    rows = _fetch(7, payload)
    assert len(rows) == 1
    r = rows[0]
    assert r.fixture_id == 100
    assert r.team_goals == 2
    assert r.opponent_goals == 1
    assert r.opponent_team_id == 99
    assert r.status_short == "FT"


def test_normalises_team_as_away_side():
    payload = {"response": [_entry(101, home_id=99, away_id=7, home_goals=1, away_goals=3)]}
    rows = _fetch(7, payload)
    assert len(rows) == 1
    r = rows[0]
    # Even though team 7 was the away side, team_goals reflects 7's goals (3).
    assert r.team_goals == 3
    assert r.opponent_goals == 1
    assert r.opponent_team_id == 99


def test_skips_malformed_entries_without_raising():
    payload = {"response": [
        _entry(101, home_id=99, away_id=7, home_goals=1, away_goals=2),
        # Wrong-team malformed: team 7 not present anywhere.
        {"fixture": {"id": 102, "date": "2026-05-20T18:00:00+00:00",
                     "status": {"short": "FT"}},
         "teams": {"home": {"id": 1}, "away": {"id": 2}},
         "goals": {"home": 1, "away": 0}},
        _entry(103, home_id=7, away_id=99, home_goals=0, away_goals=0),
    ]}
    rows = _fetch(7, payload)
    # Two valid entries; the malformed one is skipped.
    assert {r.fixture_id for r in rows} == {101, 103}


def test_empty_response_yields_empty_list():
    rows = _fetch(7, {"response": []})
    assert rows == []


def test_propagates_api_football_error():
    client = _FakeClient(error=APIFootballError("transient", "boom"))
    with pytest.raises(APIFootballError):
        asyncio.run(fetch_recent_fixtures(7, client=client, n=10))
