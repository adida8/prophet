"""api.clubelo.com CSV parser + refresh orchestrator (mocked HTTP)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from desk.data.elo.cache import EloCache
from desk.data.elo.clubelo import (
    CLUB_ID_TO_CLUBELO_NAME, ClubEloFetch, _parse_csv, _Unparseable,
    clubelo_name_for, fetch_one, refresh_clubs,
)


_VALID_CSV = """Rank,Club,Country,Level,Elo,From,To
None,ManCity,ENG,1,1810.2,2024-08-05,2024-08-10
None,ManCity,ENG,1,1820.5,2024-08-11,2024-08-15
None,ManCity,ENG,1,1825.0,2024-08-16,2024-08-25
"""


def test_parse_csv_returns_rows_in_order():
    rows = _parse_csv(_VALID_CSV)
    assert rows == [
        ("2024-08-10", 1810.2),
        ("2024-08-15", 1820.5),
        ("2024-08-25", 1825.0),
    ]


def test_parse_csv_rejects_renamed_header():
    bad = "Rank,Club,Country,Level,Strength,From,To\nNone,X,ENG,1,1800,a,b\n"
    with pytest.raises(_Unparseable):
        _parse_csv(bad)


def test_parse_csv_rejects_empty_response():
    with pytest.raises(_Unparseable):
        _parse_csv("")


def test_parse_csv_skips_individual_bad_rows():
    """One malformed row shouldn't take down the whole parse."""
    body = ("Rank,Club,Country,Level,Elo,From,To\n"
            "None,X,ENG,1,1800.0,a,2024-08-10\n"
            "None,X,ENG,1,BAD,a,2024-08-11\n"
            "None,X,ENG,1,1820.0,a,2024-08-12\n")
    rows = _parse_csv(body)
    assert len(rows) == 2


# ── client wiring (mocked httpx) ──────────────────────────────────────

@dataclass
class _Resp:
    status_code: int
    text: str


class _FakeClient:
    def __init__(self, response=None, raise_error=None):
        self.response = response
        self.raise_error = raise_error
        self.calls: list[str] = []

    async def get(self, url):
        self.calls.append(url)
        if self.raise_error:
            raise self.raise_error
        return self.response


def test_clubelo_name_for_handles_unknown():
    assert clubelo_name_for("epl-mci") == "ManCity"
    assert clubelo_name_for("not-a-club") is None


def test_fetch_one_no_mapping_returns_no_history():
    out = asyncio.run(fetch_one("not-a-club", client=_FakeClient()))
    assert out.status == "no_history"


def test_fetch_one_happy_path():
    client = _FakeClient(response=_Resp(status_code=200, text=_VALID_CSV))
    out = asyncio.run(fetch_one("epl-mci", client=client))
    assert out.status == "ok"
    assert out.elo == 1825.0
    assert out.rows_parsed == 3
    assert client.calls == ["https://api.clubelo.com/ManCity"]


def test_fetch_one_handles_http_error():
    client = _FakeClient(response=_Resp(status_code=503, text="upstream down"))
    out = asyncio.run(fetch_one("epl-mci", client=client))
    assert out.status == "http_error"


def test_fetch_one_handles_parser_mismatch():
    bad = "DifferentSchema,Foo,Bar\n1,2,3\n"
    client = _FakeClient(response=_Resp(status_code=200, text=bad))
    out = asyncio.run(fetch_one("epl-mci", client=client))
    assert out.status == "parser_mismatch"


def test_refresh_clubs_writes_to_cache_on_ok(tmp_path):
    client = _FakeClient(response=_Resp(status_code=200, text=_VALID_CSV))
    cache = EloCache(tmp_path / "elo.db")
    outcomes = asyncio.run(refresh_clubs(["epl-mci"], cache=cache, client=client))
    assert outcomes[0].status == "ok"
    row = cache.get_club("epl-mci")
    assert row is not None
    assert row.elo == 1825.0
    assert row.source_id == "clubelo"


def test_refresh_clubs_skips_write_on_parser_mismatch(tmp_path):
    """When the parser fails, the cache must keep its last-good value
    (per spec: 'fall back to last-good cached values on mismatch')."""
    cache = EloCache(tmp_path / "elo.db")
    # Seed a last-good value.
    cache.upsert_club("epl-mci", 1700.0, source_id="clubelo", source_url="x")
    # Now refresh with a broken response.
    bad = "DifferentSchema,Foo,Bar\n1,2,3\n"
    client = _FakeClient(response=_Resp(status_code=200, text=bad))
    outcomes = asyncio.run(refresh_clubs(["epl-mci"], cache=cache, client=client))
    assert outcomes[0].status == "parser_mismatch"
    # Cache untouched.
    assert cache.get_club("epl-mci").elo == 1700.0
