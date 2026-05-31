"""MarketSnapshot — best-of-venues behaviour and staleness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from desk.verdict.compare import MarketSnapshot, VenuePrice


def _ms(*prices: VenuePrice, asof: datetime | None = None) -> MarketSnapshot:
    return MarketSnapshot(
        match_id="fb-wc26-fra-mex-20260612",
        asof=asof or datetime.now(tz=timezone.utc),
        prices=tuple(prices),
    )


def test_best_for_returns_lowest_implied_p_across_venues() -> None:
    snap = _ms(
        VenuePrice("polymarket", "a", 0.50),
        VenuePrice("kalshi",     "a", 0.48),
    )
    bv = snap.best_for("a")
    assert bv is not None
    assert bv.venue == "kalshi"
    assert bv.implied_p == 0.48


def test_best_for_returns_none_when_side_missing() -> None:
    snap = _ms(VenuePrice("polymarket", "a", 0.50))
    assert snap.best_for("draw") is None
    assert snap.best_for("b") is None


def test_has_full_coverage() -> None:
    snap = _ms(
        VenuePrice("polymarket", "a",    0.46),
        VenuePrice("polymarket", "draw", 0.27),
        VenuePrice("polymarket", "b",    0.27),
    )
    assert snap.has_full_coverage(("a", "draw", "b"))
    assert not _ms().has_full_coverage(("a", "draw", "b"))


def test_stale_after_5_minutes() -> None:
    now = datetime.now(tz=timezone.utc)
    fresh = _ms(asof=now - timedelta(minutes=2))
    old   = _ms(asof=now - timedelta(minutes=10))
    assert not fresh.stale(now=now)
    assert old.stale(now=now)


# ── Cross-venue true-price ranking (non-US pivot) ─────────────────────

def test_best_for_true_price_uses_e_not_implied() -> None:
    """The scope-doc Argentina case — William Hill holds the LOWEST
    fair opinion (most bearish on Argentina) yet offers the LOWEST
    `true_price` (cheapest place to act). naive `best_for` ranks by
    raw implied; the new `best_for_true_price` ranks by `e`."""
    from desk.pricing.cost import VenueType

    snap = _ms(
        VenuePrice(
            venue="pinnacle", side="a", implied_p=1.0 / 5.40,
            venue_type=VenueType.SPORTSBOOK, true_price=1.0 / 5.40,
            fair_p=0.168,
        ),
        VenuePrice(
            venue="williamhill", side="a", implied_p=1.0 / 5.50,
            venue_type=VenueType.SPORTSBOOK, true_price=1.0 / 5.50,
            fair_p=0.146,   # most bearish opinion
        ),
        VenuePrice(
            venue="polymarket", side="a", implied_p=0.18,
            venue_type=VenueType.PREDICTION_MARKET, true_price=0.18 + 0.0075,
            fair_p=0.169,
        ),
    )
    # William Hill has lowest e despite its lowest fair_p.
    bv = snap.best_for_true_price("a")
    assert bv is not None
    assert bv.venue == "williamhill"


def test_best_for_true_price_falls_back_when_data_missing() -> None:
    """If any candidate row has no true_price, fall back to naive
    best_for — refuses to silently mix apples (e) with oranges (implied)."""
    from desk.pricing.cost import VenueType

    snap = _ms(
        VenuePrice("a-venue", "a", 0.50, venue_type=VenueType.SPORTSBOOK,
                   true_price=0.50),
        VenuePrice("b-venue", "a", 0.48),    # no true_price
    )
    bv = snap.best_for_true_price("a")
    assert bv is not None
    # Falls back to the naive comparison — b-venue at 0.48 wins.
    assert bv.venue == "b-venue"


def test_venue_price_legacy_constructor_unchanged() -> None:
    """Pre-pivot callers pass three positional args. None of the new
    fields are required; the dataclass tolerates the old shape."""
    p = VenuePrice("polymarket", "a", 0.50)
    assert p.venue == "polymarket"
    assert p.side == "a"
    assert p.implied_p == 0.50
    assert p.venue_type is None
    assert p.true_price is None
    assert p.fair_p is None
    assert p.region is None
