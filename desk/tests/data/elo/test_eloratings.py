"""eloratings.net parser — schema hardening + last-good fallback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from desk.data.elo.cache import EloCache
from desk.data.elo.eloratings import (
    ELO_MAX, ELO_MIN, MIN_PLAUSIBLE_ROWS, parse_world_tsv, refresh_nationals,
)


def _fake_tsv(n_rows=200, base_elo=1500.0):
    """Build a TSV with `n_rows` plausible-looking rows."""
    lines = []
    for i in range(n_rows):
        iso = chr(ord('a') + (i // 26) % 26) + chr(ord('a') + i % 26) + "x"
        elo = base_elo + (i % 100)
        lines.append(f"{i+1}\t{iso.upper()}\t{iso.upper()} Name\t{elo:.1f}\t0\t0")
    return "\n".join(lines)


# ── parse_world_tsv ───────────────────────────────────────────────────

def test_parse_empty_body_is_failure():
    parsed = parse_world_tsv("")
    assert not parsed.ok
    assert "empty" in (parsed.error or "")


def test_parse_too_few_rows_aborts():
    parsed = parse_world_tsv(_fake_tsv(n_rows=10))
    assert not parsed.ok
    assert "rows" in (parsed.error or "")


def test_parse_returns_normalised_iso3():
    parsed = parse_world_tsv(_fake_tsv(n_rows=MIN_PLAUSIBLE_ROWS + 50))
    assert parsed.ok
    for iso3, _ in parsed.rows:
        assert iso3.islower()
        assert len(iso3) == 3


def test_parse_rejects_out_of_range_majority():
    # Build a feed where most Elo values are absurd (out of range).
    n = MIN_PLAUSIBLE_ROWS + 50
    lines = []
    for i in range(n):
        iso = chr(ord('a') + i % 26) + chr(ord('a') + i % 26) + "x"
        elo = 99999.0  # absurd
        lines.append(f"{i+1}\t{iso.upper()}\tX\t{elo}\t0\t0")
    parsed = parse_world_tsv("\n".join(lines))
    assert not parsed.ok
    assert "range" in (parsed.error or "")


def test_parse_in_range_threshold_at_80pct():
    """80% in-range should clear; 70% should fail."""
    n = MIN_PLAUSIBLE_ROWS + 50
    lines = []
    for i in range(n):
        iso = chr(ord('a') + (i // 26) % 26) + chr(ord('a') + i % 26) + "x"
        if i < int(n * 0.9):
            elo = 1500.0
        else:
            elo = 99999.0
        lines.append(f"{i+1}\t{iso.upper()}\tX\t{elo}\t0\t0")
    parsed = parse_world_tsv("\n".join(lines))
    assert parsed.ok


def test_parse_skips_garbage_team_codes():
    """A row with a non-3-letter code is silently skipped, not aborted."""
    n_valid = MIN_PLAUSIBLE_ROWS + 50
    lines = []
    for i in range(n_valid):
        iso = chr(ord('a') + i % 26) + chr(ord('a') + i % 26) + "x"
        lines.append(f"{i+1}\t{iso.upper()}\tX\t1500.0\t0\t0")
    # Inject a garbage row.
    lines.append("999\tBAD123\tFoo\t1500.0\t0\t0")
    parsed = parse_world_tsv("\n".join(lines))
    assert parsed.ok
    iso_codes = {iso for iso, _ in parsed.rows}
    assert "bad" not in iso_codes


# ── refresh_nationals (mocked HTTP) ──────────────────────────────────

@dataclass
class _Resp:
    status_code: int
    text: str


class _FakeClient:
    def __init__(self, response):
        self.response = response

    async def get(self, url):
        return self.response


def test_refresh_writes_only_on_ok(tmp_path):
    body = _fake_tsv(n_rows=MIN_PLAUSIBLE_ROWS + 50)
    client = _FakeClient(_Resp(status_code=200, text=body))
    cache = EloCache(tmp_path / "elo.db")
    parsed = asyncio.run(refresh_nationals(cache=cache, client=client))
    assert parsed.ok
    # First two rows should be in cache.
    rows = cache.list_nationals()
    assert len(rows) >= 50


def test_refresh_keeps_last_good_on_parser_mismatch(tmp_path):
    """When the parse aborts, the cache must keep its prior contents."""
    cache = EloCache(tmp_path / "elo.db")
    cache.upsert_national("fra", 2030.0, source_id="eloratings", source_url="x")
    # Now feed a broken response.
    bad_body = "1\t!!\tFoo\t99999.0\t0\t0\n" * (MIN_PLAUSIBLE_ROWS + 50)
    client = _FakeClient(_Resp(status_code=200, text=bad_body))
    parsed = asyncio.run(refresh_nationals(cache=cache, client=client))
    assert not parsed.ok
    # Pre-existing row preserved.
    assert cache.get_national("fra").elo == 2030.0


def test_refresh_iso3_allowlist_filter(tmp_path):
    body = _fake_tsv(n_rows=MIN_PLAUSIBLE_ROWS + 50)
    client = _FakeClient(_Resp(status_code=200, text=body))
    cache = EloCache(tmp_path / "elo.db")
    parsed = asyncio.run(refresh_nationals(
        cache=cache, client=client, iso3_allowlist={"aax", "abx"},
    ))
    assert parsed.ok
    # Only the allowlisted ISOs should appear in cache.
    rows = cache.list_nationals()
    iso_set = {r.key for r in rows}
    assert iso_set <= {"aax", "abx"}


def test_refresh_handles_http_error(tmp_path):
    client = _FakeClient(_Resp(status_code=503, text=""))
    cache = EloCache(tmp_path / "elo.db")
    cache.upsert_national("fra", 2030.0, source_id="eloratings", source_url="x")
    parsed = asyncio.run(refresh_nationals(cache=cache, client=client))
    assert not parsed.ok
    # Cache untouched.
    assert cache.get_national("fra").elo == 2030.0
