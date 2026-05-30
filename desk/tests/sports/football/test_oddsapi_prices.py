"""Unit tests for desk/sports/football/oddsapi_prices.py."""

from __future__ import annotations

import math

from desk.data.oddsapi.cache import PriceRow
from desk.pricing.cost import VenueType
from desk.sports.football.oddsapi_prices import (
    enrich_polymarket_venue_prices,
    venue_prices_from_oddsapi,
)
from desk.verdict.compare import MarketSnapshot, VenuePrice


def _mun_liv_rows() -> list[PriceRow]:
    """Mirror the sample EPL event JSON."""
    return [
        # Pinnacle
        PriceRow("ev1", "pinnacle", "a",    3.10, "iso", "iso"),
        PriceRow("ev1", "pinnacle", "draw", 3.40, "iso", "iso"),
        PriceRow("ev1", "pinnacle", "b",    2.40, "iso", "iso"),
        # William Hill — slightly tighter
        PriceRow("ev1", "williamhill", "a",    3.00, "iso", "iso"),
        PriceRow("ev1", "williamhill", "draw", 3.40, "iso", "iso"),
        PriceRow("ev1", "williamhill", "b",    2.30, "iso", "iso"),
        # Betfair Exchange — best back odds, commission cuts payout
        PriceRow("ev1", "betfair_ex_uk", "a",    3.15, "iso", "iso"),
        PriceRow("ev1", "betfair_ex_uk", "draw", 3.50, "iso", "iso"),
        PriceRow("ev1", "betfair_ex_uk", "b",    2.42, "iso", "iso"),
    ]


def test_emits_one_venue_price_per_priced_side() -> None:
    rows = _mun_liv_rows()
    prices = venue_prices_from_oddsapi(rows)
    by_venue = {(p.venue, p.side) for p in prices}
    # 3 venues × 3 sides.
    assert len(prices) == 9
    assert ("pinnacle",      "a") in by_venue
    assert ("williamhill",   "b") in by_venue
    assert ("betfair_ex_uk", "draw") in by_venue


def test_sportsbook_true_price_equals_one_over_decimal() -> None:
    prices = venue_prices_from_oddsapi(_mun_liv_rows())
    pin_a = next(p for p in prices if p.venue == "pinnacle" and p.side == "a")
    assert pin_a.venue_type == VenueType.SPORTSBOOK
    assert math.isclose(pin_a.true_price, 1.0 / 3.10, rel_tol=1e-12)
    assert math.isclose(pin_a.implied_p,  1.0 / 3.10, rel_tol=1e-12)


def test_exchange_true_price_includes_commission() -> None:
    """Default 2% commission: d_eff = 1 + (3.15-1)(0.98) = 3.107 →
    e = 1/3.107 ≈ 0.3218, strictly higher than the naive 1/3.15."""
    prices = venue_prices_from_oddsapi(_mun_liv_rows())
    bf_a = next(p for p in prices if p.venue == "betfair_ex_uk" and p.side == "a")
    assert bf_a.venue_type == VenueType.EXCHANGE
    expected = 1.0 / (1.0 + (3.15 - 1.0) * 0.98)
    assert math.isclose(bf_a.true_price, expected, rel_tol=1e-12)
    assert bf_a.true_price > bf_a.implied_p   # commission costs you


def test_fair_p_per_venue_sums_to_one() -> None:
    prices = venue_prices_from_oddsapi(_mun_liv_rows())
    for venue in ("pinnacle", "williamhill", "betfair_ex_uk"):
        venue_rows = [p for p in prices if p.venue == venue]
        assert math.isclose(sum(p.fair_p for p in venue_rows), 1.0, rel_tol=1e-12), venue


def test_overround_carries_through() -> None:
    prices = venue_prices_from_oddsapi(_mun_liv_rows())
    pin_rows = [p for p in prices if p.venue == "pinnacle"]
    expected = 1.0/3.10 + 1.0/3.40 + 1.0/2.40
    for p in pin_rows:
        assert math.isclose(p.overround, expected, rel_tol=1e-12)


def test_region_populated_from_venue_table() -> None:
    prices = venue_prices_from_oddsapi(_mun_liv_rows())
    by_venue = {p.venue: p.region for p in prices}
    assert by_venue["pinnacle"]      == "eu"
    assert by_venue["williamhill"]   == "uk"
    assert by_venue["betfair_ex_uk"] == "uk"


def test_unknown_venue_dropped() -> None:
    rows = _mun_liv_rows() + [
        PriceRow("ev1", "wonkabet", "a", 3.50, "iso", "iso"),
    ]
    prices = venue_prices_from_oddsapi(rows)
    assert not any(p.venue == "wonkabet" for p in prices)


def test_partial_coverage_leaves_fair_p_none() -> None:
    """Only two sides priced → no de-vig possible, fair_p stays None."""
    rows = [
        PriceRow("ev1", "pinnacle", "a", 3.10, "iso", "iso"),
        PriceRow("ev1", "pinnacle", "b", 2.40, "iso", "iso"),
    ]
    prices = venue_prices_from_oddsapi(rows)
    for p in prices:
        assert p.fair_p is None
        # true_price still computable per-row.
        assert p.true_price is not None


def test_best_for_true_price_on_built_snapshot() -> None:
    """End-to-end: feed the snapshot into best_for_true_price and the
    cheapest book wins, including commission on the exchange row."""
    prices = venue_prices_from_oddsapi(_mun_liv_rows())
    snap = MarketSnapshot(
        match_id="fb-epl-mun-liv-20260815",
        asof=__import__("datetime").datetime.now(),
        prices=tuple(prices),
    )
    bv = snap.best_for_true_price("a")
    assert bv is not None
    # William Hill quoted 3.00 (e = 0.333); Pinnacle 3.10 (e = 0.322);
    # Betfair 3.15 with 2% comm (e ≈ 0.322 → 1/3.107 = 0.3218).
    # Pinnacle 1/3.10 = 0.3226 vs Betfair 1/3.107 = 0.3218.
    # So Betfair Exchange should be the cheapest place to act here.
    assert bv.venue == "betfair_ex_uk"


def test_enrich_polymarket_legacy_rows_adds_fields() -> None:
    """Pre-pivot polymarket adapter emits 3 rows without venue_type /
    true_price / fair_p; enrich() fills them in."""
    legacy = [
        VenuePrice("polymarket", "a",    0.40),
        VenuePrice("polymarket", "draw", 0.28),
        VenuePrice("polymarket", "b",    0.40),
    ]
    enriched = enrich_polymarket_venue_prices(legacy)
    by_side = {p.side: p for p in enriched if p.venue == "polymarket"}
    for s in ("a", "draw", "b"):
        assert by_side[s].venue_type == VenueType.PREDICTION_MARKET
        assert by_side[s].true_price is not None
        assert by_side[s].true_price > by_side[s].implied_p   # +fee
        assert by_side[s].fair_p is not None
    # fair_p sums to 1 after multiplicative de-vig.
    assert math.isclose(
        sum(by_side[s].fair_p for s in ("a", "draw", "b")),
        1.0, rel_tol=1e-12,
    )


def test_enrich_polymarket_preserves_non_polymarket_rows() -> None:
    """Non-Poly rows pass through enrich_polymarket_venue_prices unchanged."""
    rows = [
        VenuePrice("polymarket", "a", 0.40),
        VenuePrice("polymarket", "draw", 0.28),
        VenuePrice("polymarket", "b", 0.40),
        VenuePrice("pinnacle", "a", 1.0 / 3.10),   # legacy shape
    ]
    enriched = enrich_polymarket_venue_prices(rows)
    pin_rows = [p for p in enriched if p.venue == "pinnacle"]
    assert len(pin_rows) == 1
    # Pinnacle row left as-is (no enrichment for non-Poly here).
    assert pin_rows[0].true_price is None
