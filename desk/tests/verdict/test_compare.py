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
