"""End-to-end runtime merge tests — cached odds-api prices + a
Polymarket-only snapshot → enriched multi-venue snapshot."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from desk.data.oddsapi.cache import OddsAPICache, PriceRow
from desk.sports.football.oddsapi_prices import merge_oddsapi_into_snapshot
from desk.verdict.compare import MarketSnapshot, VenuePrice


@pytest.fixture()
def cache(tmp_path) -> OddsAPICache:
    return OddsAPICache(tmp_path / "oddsapi.db")


def _legacy_poly_snapshot() -> MarketSnapshot:
    """The pre-pivot snapshot shape — Polymarket only, no enrichment."""
    return MarketSnapshot(
        match_id="fb-epl-mun-liv-20260815",
        asof=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        prices=(
            VenuePrice("polymarket", "a",    0.40),
            VenuePrice("polymarket", "draw", 0.28),
            VenuePrice("polymarket", "b",    0.40),
        ),
    )


def _seed_cache_with_mun_liv(cache: OddsAPICache) -> None:
    """Mirror what `desk fetch-odds` would write for the Man-U vs
    Liverpool sample event."""
    kickoff = datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)
    cache.upsert_event(
        event_id="ev1",
        sport_key="soccer_epl",
        commence_time=kickoff,
        home_team="Manchester United",
        away_team="Liverpool",
    )
    cache.set_event_resolution("ev1", "fb-epl-mun-liv-20260815")
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="pinnacle",
        rows=[
            PriceRow("ev1", "pinnacle", "a",    3.10, "iso", "iso"),
            PriceRow("ev1", "pinnacle", "draw", 3.40, "iso", "iso"),
            PriceRow("ev1", "pinnacle", "b",    2.40, "iso", "iso"),
        ],
    )
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="williamhill",
        rows=[
            PriceRow("ev1", "williamhill", "a",    3.00, "iso", "iso"),
            PriceRow("ev1", "williamhill", "draw", 3.40, "iso", "iso"),
            PriceRow("ev1", "williamhill", "b",    2.30, "iso", "iso"),
        ],
    )


def test_merge_adds_oddsapi_venues_to_snapshot(cache) -> None:
    _seed_cache_with_mun_liv(cache)
    merged = merge_oddsapi_into_snapshot(_legacy_poly_snapshot(), cache=cache)

    venues = {p.venue for p in merged.prices}
    assert venues == {"polymarket", "pinnacle", "williamhill"}


def test_merge_enriches_polymarket_rows(cache) -> None:
    """Polymarket rows go in naive (no venue_type / true_price /
    fair_p) and come out enriched so they're directly rankable
    against the books."""
    _seed_cache_with_mun_liv(cache)
    merged = merge_oddsapi_into_snapshot(_legacy_poly_snapshot(), cache=cache)

    poly_rows = [p for p in merged.prices if p.venue == "polymarket"]
    assert len(poly_rows) == 3
    for p in poly_rows:
        assert p.venue_type is not None
        assert p.true_price is not None
        assert p.fair_p is not None
        # True price = ask + default 0.75% fee
        assert math.isclose(p.true_price, p.implied_p + 0.0075, rel_tol=1e-12)


def test_merge_noop_when_cache_empty(cache) -> None:
    """No events for this match_id → snapshot returned unchanged."""
    snap = _legacy_poly_snapshot()
    merged = merge_oddsapi_into_snapshot(snap, cache=cache)
    assert merged is snap


def test_merge_preserves_match_id_and_asof(cache) -> None:
    _seed_cache_with_mun_liv(cache)
    snap = _legacy_poly_snapshot()
    merged = merge_oddsapi_into_snapshot(snap, cache=cache)
    assert merged.match_id == snap.match_id
    assert merged.asof == snap.asof


def test_merged_best_for_true_price_ranks_across_all_venues(cache) -> None:
    """After merge, best_for_true_price ranks Polymarket vs William
    Hill vs Pinnacle on a single comparable cost surface."""
    _seed_cache_with_mun_liv(cache)
    merged = merge_oddsapi_into_snapshot(_legacy_poly_snapshot(), cache=cache)
    bv_a = merged.best_for_true_price("a")
    assert bv_a is not None
    # Pinnacle 1/3.10 = 0.3226; William Hill 1/3.00 = 0.3333;
    # Polymarket 0.40 + 0.0075 = 0.4075.
    # Pinnacle is the cheapest place to act on home.
    assert bv_a.venue == "pinnacle"


def test_merge_dropped_unknown_venues_quietly(cache) -> None:
    """A row from a venue outside the launch set survives in the
    cache but never makes it into the snapshot."""
    _seed_cache_with_mun_liv(cache)
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="some-future-venue",
        rows=[PriceRow("ev1", "some-future-venue", "a", 3.20, "iso", "iso")],
    )
    merged = merge_oddsapi_into_snapshot(_legacy_poly_snapshot(), cache=cache)
    venues = {p.venue for p in merged.prices}
    assert "some-future-venue" not in venues


def test_merge_safe_when_match_id_unresolved(cache) -> None:
    """Cached event exists but its match_id was never resolved →
    `events_for_match_id` returns [] → snapshot unchanged."""
    cache.upsert_event(
        event_id="ev1", sport_key="soccer_epl",
        commence_time=datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc),
        home_team="Manchester United", away_team="Liverpool",
    )
    # NOTE: deliberately skip set_event_resolution.
    cache.replace_prices_for_event_venue(
        event_id="ev1", venue_id="pinnacle",
        rows=[PriceRow("ev1", "pinnacle", "a", 3.10, "iso", "iso")],
    )
    snap = _legacy_poly_snapshot()
    merged = merge_oddsapi_into_snapshot(snap, cache=cache)
    assert merged is snap


def test_resolve_event_match_ids_helper(cache) -> None:
    """`refresh_all` runs `_resolve_event_match_ids` so cached events
    get their match_id stamped immediately after the fetch."""
    from desk.data.oddsapi.events import parse_event_payload
    from desk.data.oddsapi.refresh import _resolve_event_match_ids
    import json
    from pathlib import Path

    sample_path = (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "oddsapi" / "sample_epl_event.json"
    )
    parsed = parse_event_payload(json.loads(sample_path.read_text()))
    # Seed the event row(s) so set_event_resolution has something to
    # stamp.
    for ev in parsed:
        cache.upsert_event(
            event_id=ev["event_id"], sport_key=ev["sport_key"],
            commence_time=ev["commence_time"],
            home_team=ev["home_team"], away_team=ev["away_team"],
        )
    n = _resolve_event_match_ids(parsed, cache)
    assert n == 1
    stored = cache.event_for("abc123-event-id-mun-liv")
    assert stored is not None
    assert stored.resolved_match_id == "fb-epl-mun-liv-20260815"
