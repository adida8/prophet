"""api-football /injuries — parse + per-team fetch + source audit."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from desk.data.api_football.client import APIFootballError
from desk.data.api_football.injuries import (
    _parse_injury_entry, fetch_for_team, run_source_audit,
)


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


def _entry(player_id=10, team_id=2, position="Defender",
           type_="Missing Fixture", reason="Knock"):
    return {
        "player": {"id": player_id, "name": f"Player {player_id}",
                   "position": position},
        "team":   {"id": team_id, "name": "X"},
        "type":   type_, "reason": reason,
    }


# ── _parse_injury_entry ───────────────────────────────────────────────

def test_parse_injury_entry_happy_path():
    e = _entry()
    parsed = _parse_injury_entry(
        e, fetched_at=datetime(2026, 5, 28, tzinfo=timezone.utc),
    )
    assert parsed is not None
    assert parsed.team_id == 2
    assert parsed.player_id == 10
    assert parsed.position == "Defender"
    assert parsed.type == "Missing Fixture"


def test_parse_injury_entry_malformed_returns_none():
    parsed = _parse_injury_entry(
        {"player": None, "team": None},
        fetched_at=datetime.now(tz=timezone.utc),
    )
    assert parsed is None


# ── fetch_for_team ────────────────────────────────────────────────────

def test_fetch_for_team_returns_normalised_items():
    client = _FakeClient()
    client.expect("/injuries", {"team": "2", "season": "2026"}, payload={
        "response": [_entry(), _entry(player_id=11)],
    })
    status, items = asyncio.run(fetch_for_team(
        2, season=2026, client=client,
    ))
    assert status == "ok"
    assert len(items) == 2


def test_fetch_for_team_handles_api_error():
    client = _FakeClient()
    client.expect("/injuries", {"team": "2", "season": "2026"},
                  error=APIFootballError("transient", "timeout"))
    status, items = asyncio.run(fetch_for_team(
        2, season=2026, client=client,
    ))
    assert status == "transient"
    assert items == []


def test_fetch_for_team_skips_malformed_rows():
    client = _FakeClient()
    client.expect("/injuries", {"team": "2", "season": "2026"}, payload={
        "response": [
            _entry(),
            {"player": "garbage", "team": "garbage"},   # malformed
            _entry(player_id=11),
        ],
    })
    status, items = asyncio.run(fetch_for_team(2, season=2026, client=client))
    assert status == "ok"
    assert len(items) == 2  # malformed row skipped


# ── source audit ──────────────────────────────────────────────────────

def test_source_audit_clears_on_clean_data():
    client = _FakeClient()
    for tid in [2, 6, 16]:
        client.expect("/injuries", {"team": str(tid), "season": "2026"},
                      payload={
            "response": [
                _entry(team_id=tid, player_id=100),
                _entry(team_id=tid, player_id=101),
            ],
        })
    audit = asyncio.run(run_source_audit([2, 6, 16],
                                          season=2026, client=client))
    assert audit.coverage_rate == pytest.approx(1.0)
    assert audit.has_position_rate == pytest.approx(1.0)
    assert audit.has_type_rate == pytest.approx(1.0)
    assert audit.passes


def test_source_audit_fails_when_position_missing():
    client = _FakeClient()
    for tid in [2, 6, 16]:
        client.expect("/injuries", {"team": str(tid), "season": "2026"},
                      payload={
            "response": [
                _entry(team_id=tid, player_id=100, position=None),
            ],
        })
    audit = asyncio.run(run_source_audit([2, 6, 16],
                                          season=2026, client=client))
    assert audit.has_position_rate == pytest.approx(0.0)
    assert not audit.passes


def test_source_audit_coverage_below_floor():
    """Most teams returning no rows fails the coverage floor."""
    client = _FakeClient()
    client.expect("/injuries", {"team": "2", "season": "2026"},
                  payload={"response": []})
    client.expect("/injuries", {"team": "6", "season": "2026"},
                  payload={"response": []})
    client.expect("/injuries", {"team": "16", "season": "2026"},
                  payload={"response": [_entry(team_id=16, player_id=100)]})
    audit = asyncio.run(run_source_audit([2, 6, 16],
                                          season=2026, client=client))
    assert audit.coverage_rate == pytest.approx(1/3)
    assert not audit.passes
