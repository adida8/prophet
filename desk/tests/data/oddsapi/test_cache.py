"""Unit tests for desk/desk/data/oddsapi/cache.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desk.data.oddsapi.cache import OddsAPICache, PriceRow


@pytest.fixture()
def cache(tmp_path) -> OddsAPICache:
    return OddsAPICache(tmp_path / "oddsapi.db")


def test_event_round_trip(cache: OddsAPICache) -> None:
    kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)
    cache.upsert_event(
        event_id="ev1",
        sport_key="soccer_epl",
        commence_time=kickoff,
        home_team="Manchester United",
        away_team="Liverpool",
    )
    ev = cache.event_for("ev1")
    assert ev is not None
    assert ev.home_team == "Manchester United"
    assert ev.away_team == "Liverpool"
    assert ev.commence_time == kickoff
    assert ev.resolved_match_id == ""


def test_set_event_resolution(cache: OddsAPICache) -> None:
    cache.upsert_event(
        event_id="ev1", sport_key="soccer_epl",
        commence_time=datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc),
        home_team="Manchester United", away_team="Liverpool",
    )
    cache.set_event_resolution("ev1", "fb-epl-mun-liv-20260815")
    ev = cache.event_for("ev1")
    assert ev is not None
    assert ev.resolved_match_id == "fb-epl-mun-liv-20260815"
    # Reverse lookup also works.
    events = cache.events_for_match_id("fb-epl-mun-liv-20260815")
    assert len(events) == 1
    assert events[0].event_id == "ev1"


def test_replace_prices_deletes_stale(cache: OddsAPICache) -> None:
    # First fetch: three sides priced.
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="pinnacle",
        rows=[
            PriceRow("ev1", "pinnacle", "a",    3.10, "iso1", "iso1"),
            PriceRow("ev1", "pinnacle", "draw", 3.40, "iso1", "iso1"),
            PriceRow("ev1", "pinnacle", "b",    2.40, "iso1", "iso1"),
        ],
    )
    assert len(cache.prices_for_event("ev1")) == 3

    # Second fetch: venue stopped quoting the draw. Replacement must
    # WIPE the old draw row, not leave it.
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="pinnacle",
        rows=[
            PriceRow("ev1", "pinnacle", "a", 3.20, "iso2", "iso2"),
            PriceRow("ev1", "pinnacle", "b", 2.35, "iso2", "iso2"),
        ],
    )
    rows = cache.prices_for_event("ev1")
    assert len(rows) == 2
    assert {r.side for r in rows} == {"a", "b"}
    # And the prices reflect the second fetch.
    assert {r.decimal_odds for r in rows} == {3.20, 2.35}


def test_prices_isolated_per_venue(cache: OddsAPICache) -> None:
    """Rewriting Pinnacle must not touch William Hill's rows."""
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="pinnacle",
        rows=[PriceRow("ev1", "pinnacle", "a", 3.10, "iso1", "iso1")],
    )
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="williamhill",
        rows=[PriceRow("ev1", "williamhill", "a", 3.00, "iso1", "iso1")],
    )
    # Now rewrite Pinnacle only.
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="pinnacle",
        rows=[PriceRow("ev1", "pinnacle", "a", 3.05, "iso2", "iso2")],
    )
    rows = cache.prices_for_event("ev1")
    by_venue = {(r.venue_id, r.side): r.decimal_odds for r in rows}
    assert by_venue[("pinnacle",    "a")] == 3.05
    assert by_venue[("williamhill", "a")] == 3.00


def test_fetch_log_round_trip(cache: OddsAPICache) -> None:
    cache.mark_fetch("soccer_epl/h2h", "ok", credits=1)
    log = cache.last_fetch("soccer_epl/h2h")
    assert log is not None
    when, status, credits = log
    assert isinstance(when, datetime)
    assert status == "ok"
    assert credits == 1


def test_default_cache_path_honours_env(monkeypatch, tmp_path) -> None:
    from desk.data.oddsapi.cache import default_cache_path
    override = tmp_path / "mounted" / "oddsapi.db"
    monkeypatch.setenv("DESK_ODDS_API_DB_PATH", str(override))
    assert default_cache_path() == override
