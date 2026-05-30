"""api-football /players cards path — Q1 of the squad-paragraph spec.

Covers:
  * Parse-time normalisation + league filter.
  * Card-rule lookup + at_risk derivation (including the
    already-suspended carve-out — spec §Q1 sanity gates).
  * Sanity rejection of negative / impossibly large card counts.
  * `card_data_to_rows` reconcile with the team's current suspension set.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from desk.data.api_football.cards import (
    CARD_RULES,
    WC26_LEAGUE_ID,
    CardDatum,
    card_data_to_rows,
    derive_at_risk,
    fetch_for_team,
    _parse_player_entry,
    _sane_row,
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


def _player_entry(
    *, player_id: int = 10, team_id: int = 33,
    yellows: int = 0, yellowred: int = 0, reds: int = 0,
    league_id: int = WC26_LEAGUE_ID, position: str = "Midfielder",
    name: str | None = None,
) -> dict:
    return {
        "player": {"id": player_id, "name": name or f"Player {player_id}"},
        "statistics": [
            {
                "team":   {"id": team_id, "name": "France"},
                "league": {"id": league_id, "season": 2026,
                           "name": "World Cup"},
                "games":  {"position": position},
                "cards":  {"yellow": yellows, "yellowred": yellowred,
                           "red": reds},
            }
        ],
    }


# ── _parse_player_entry ──────────────────────────────────────────────

def test_parse_picks_league_row_and_sums_yellowred():
    parsed = _parse_player_entry(
        _player_entry(player_id=7, yellows=1, yellowred=1, reds=0),
        league_id=WC26_LEAGUE_ID,
        fetched_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source_endpoint="/players?team=33&season=2026&league=1",
    )
    assert parsed is not None
    assert parsed.player_id == 7
    assert parsed.yellows == 2   # yellow + yellowred summed
    assert parsed.reds == 0
    assert parsed.position == "Midfielder"


def test_parse_skips_when_no_matching_league_row():
    entry = _player_entry(player_id=8, league_id=999)   # not WC26
    parsed = _parse_player_entry(
        entry, league_id=WC26_LEAGUE_ID,
        fetched_at=datetime.now(tz=timezone.utc),
        source_endpoint="",
    )
    assert parsed is None


def test_parse_drops_negative_or_huge_card_counts():
    entry = _player_entry(player_id=9, yellows=-1)
    parsed = _parse_player_entry(
        entry, league_id=WC26_LEAGUE_ID,
        fetched_at=datetime.now(tz=timezone.utc),
        source_endpoint="",
    )
    assert parsed is None
    entry_big = _player_entry(player_id=9, yellows=42)
    parsed_big = _parse_player_entry(
        entry_big, league_id=WC26_LEAGUE_ID,
        fetched_at=datetime.now(tz=timezone.utc),
        source_endpoint="",
    )
    assert parsed_big is None


def test_parse_handles_missing_position_gracefully():
    entry = _player_entry(player_id=10, position="")
    parsed = _parse_player_entry(
        entry, league_id=WC26_LEAGUE_ID,
        fetched_at=datetime.now(tz=timezone.utc),
        source_endpoint="",
    )
    assert parsed is not None
    assert parsed.position is None


# ── _sane_row ────────────────────────────────────────────────────────

def test_sane_row_boundaries():
    assert _sane_row(0, 0)
    assert _sane_row(20, 10)
    assert not _sane_row(-1, 0)
    assert not _sane_row(0, -1)
    assert not _sane_row(21, 0)
    assert not _sane_row(0, 11)


# ── fetch_for_team ───────────────────────────────────────────────────

def test_fetch_for_team_returns_normalised_items():
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "33", "season": "2026", "league": "1"},
        payload={"response": [
            _player_entry(player_id=11, yellows=1),
            _player_entry(player_id=12, yellows=0),
        ]},
    )
    status, items = asyncio.run(fetch_for_team(
        33, season=2026, client=client,
    ))
    assert status == "ok"
    assert len(items) == 2
    assert items[0].yellows == 1
    assert items[1].yellows == 0


def test_fetch_for_team_propagates_client_error_kind():
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "33", "season": "2026", "league": "1"},
        error=APIFootballError("quota", "rate limit"),
    )
    status, items = asyncio.run(fetch_for_team(
        33, season=2026, client=client,
    ))
    assert status == "quota"
    assert items == []


def test_fetch_for_team_warns_on_paging_total_gt_1(caplog):
    """Pagination is a v2 problem; v1 reads page 1 and warns loud."""
    client = _FakeClient()
    client.expect(
        "/players",
        {"team": "33", "season": "2026", "league": "1"},
        payload={
            "response": [_player_entry(player_id=11)],
            "paging":   {"current": 1, "total": 2},
        },
    )
    import logging
    with caplog.at_level(logging.WARNING):
        status, _ = asyncio.run(fetch_for_team(
            33, season=2026, client=client,
        ))
    assert status == "ok"
    assert any("paging.total > 1" in r.message for r in caplog.records)


# ── derive_at_risk ───────────────────────────────────────────────────

def test_at_risk_when_yellows_one_below_threshold():
    """WC26 threshold = 2, so 1 yellow = at-risk."""
    assert derive_at_risk(1, competition="wc26") is True


def test_not_at_risk_at_zero_yellows():
    assert derive_at_risk(0, competition="wc26") is False


def test_not_at_risk_at_or_above_threshold():
    # 2 yellows = already triggered the ban; not at-risk anymore (the
    # injuries cache should now flag the player as Suspended).
    assert derive_at_risk(2, competition="wc26") is False
    assert derive_at_risk(3, competition="wc26") is False


def test_at_risk_dropped_for_already_suspended_player():
    """Spec §Q1: a player both at-risk AND already suspended must NOT
    be flagged at-risk. The suspension wins (it's the confirmed absence)."""
    assert derive_at_risk(
        1, competition="wc26", already_suspended=True,
    ) is False


def test_at_risk_unknown_competition_is_false():
    """Defensive: missing card rule → silent False, never raise."""
    assert derive_at_risk(1, competition="madeup-league") is False


def test_card_rules_wc26_documented():
    """Lock the v1 rule in a test so a silent edit shows up red."""
    rule = CARD_RULES["wc26"]
    assert rule.yellow_ban_threshold == 2
    assert rule.wipe_after_stage == "quarter_final"


# ── card_data_to_rows ────────────────────────────────────────────────

def _datum(
    *, player_id: int, yellows: int = 0, reds: int = 0,
    name: str | None = None, position: str | None = "Midfielder",
) -> CardDatum:
    return CardDatum(
        team_id=33,
        player_id=player_id,
        player_name=name or f"Player {player_id}",
        position=position,
        yellows=yellows,
        reds=reds,
        fetched_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source_endpoint="/players?team=33&season=2026&league=1",
    )


def test_card_data_to_rows_flags_at_risk_player():
    rows = card_data_to_rows(
        [_datum(player_id=1, yellows=1)],
        competition="wc26",
    )
    assert len(rows) == 1
    assert rows[0].is_at_risk
    assert rows[0].yellows == 1
    assert rows[0].competition == "wc26"


def test_card_data_to_rows_skips_at_risk_for_already_suspended():
    """Reconcile: spec §Q1 sanity gate — drop at_risk for suspended ids."""
    rows = card_data_to_rows(
        [
            _datum(player_id=1, yellows=1),   # at risk
            _datum(player_id=2, yellows=1),   # also at risk… but suspended
        ],
        competition="wc26",
        suspended_player_ids={2},
    )
    assert len(rows) == 2
    by_id = {r.player_id: r for r in rows}
    assert by_id[1].is_at_risk
    assert not by_id[2].is_at_risk   # dropped — suspension wins


def test_card_data_to_rows_handles_zero_yellow_player():
    """Players with 0 yellows are returned but not flagged at-risk —
    the row still has its name + position, so the squad paragraph can
    decide to ignore them but the writer doesn't have to."""
    rows = card_data_to_rows(
        [_datum(player_id=1, yellows=0)],
        competition="wc26",
    )
    assert len(rows) == 1
    assert not rows[0].is_at_risk
