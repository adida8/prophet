"""market_sources builder — outbound venue links per fixture.

Covers the contract `MatchOutput.market_sources` list: every CTA venue
is listed, the picked flag tracks the verdict, and `priced_sides`
reflects what each venue actually quoted into the calculation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.publish.contract import Verdict, VerdictState
from desk.sport import FixtureRef
from desk.sports.football.market_links import (
    _KALSHI_WC_LANDING,
    _POLYMARKET_LANDING,
    build_market_sources,
    market_url_for_fixture,
)
from desk.verdict.compare import MarketSnapshot, VenuePrice


def _fx(**over) -> FixtureRef:
    base = dict(
        match_id="fb-wc26-fra-mex-20260612",
        sport="football",
        competition_code="wc26",
        competition_label="FIFA World Cup 2026",
        competition_stage="group_d",
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        team_a="France",
        team_b="Mexico",
        market_outcomes=("a", "draw", "b"),
        venue_city="Guadalajara",
        venue_stadium="Estadio Akron",
        venue_country="MX",
        source_venue="polymarket",
        source_event_slug="fifwc-fra-mex-2026-06-12",
    )
    base.update(over)
    return FixtureRef(**base)


def _poly_snapshot(match_id: str = "fb-wc26-fra-mex-20260612") -> MarketSnapshot:
    return MarketSnapshot(
        match_id=match_id,
        asof=datetime.now(tz=timezone.utc),
        prices=(
            VenuePrice(venue="polymarket", side="a", implied_p=0.42),
            VenuePrice(venue="polymarket", side="draw", implied_p=0.28),
            VenuePrice(venue="polymarket", side="b", implied_p=0.30),
        ),
    )


def _pick() -> Verdict:
    return Verdict(
        state=VerdictState.PICK,
        side="France",
        market_venue="polymarket",
        price="-145",
        edge_pp=4.2,
        market_url="https://polymarket.com/event/fifwc-fra-mex-2026-06-12",
        model_p=0.46,
        market_p=0.42,
    )


# ── market_url_for_fixture (moved from sport.py) ───────────────────────

def test_polymarket_deep_link_for_wc26_slug() -> None:
    url = market_url_for_fixture(_fx())
    assert url == "https://polymarket.com/event/fifwc-fra-mex-2026-06-12"


def test_polymarket_strips_more_markets_suffix() -> None:
    url = market_url_for_fixture(_fx(source_event_slug="fifwc-fra-mex-2026-06-12-more-markets"))
    assert url == "https://polymarket.com/event/fifwc-fra-mex-2026-06-12"


def test_non_fifwc_slug_uses_event_path() -> None:
    url = market_url_for_fixture(_fx(source_event_slug="epl-mun-liv-2026-08-15"))
    assert url == "https://polymarket.com/event/epl-mun-liv-2026-08-15"


def test_missing_slug_returns_none() -> None:
    assert market_url_for_fixture(_fx(source_event_slug="")) is None


# ── build_market_sources ───────────────────────────────────────────────

def test_lists_every_cta_venue() -> None:
    srcs = build_market_sources(_fx(), _poly_snapshot(), _pick())
    assert [s.venue for s in srcs] == ["polymarket", "kalshi"]
    assert [s.name for s in srcs] == ["Polymarket", "Kalshi"]


def test_pick_marks_only_the_picked_venue() -> None:
    srcs = build_market_sources(_fx(), _poly_snapshot(), _pick())
    poly, kalshi = srcs
    assert poly.picked is True
    assert kalshi.picked is False


def test_priced_sides_reflects_snapshot_per_venue() -> None:
    srcs = build_market_sources(_fx(), _poly_snapshot(), _pick())
    poly, kalshi = srcs
    # Polymarket fed all three sides; Kalshi fed nothing (stub ingest).
    assert poly.priced_sides == ["a", "draw", "b"]
    assert kalshi.priced_sides == []


def test_pass_marks_no_venue_picked() -> None:
    pass_v = Verdict(
        state=VerdictState.PASS,
        market_url="https://polymarket.com/event/fifwc-fra-mex-2026-06-12",
    )
    srcs = build_market_sources(_fx(), _poly_snapshot(), pass_v)
    assert all(s.picked is False for s in srcs)
    # priced_sides is independent of the verdict — Polymarket still priced.
    assert srcs[0].priced_sides == ["a", "draw", "b"]


def test_polymarket_falls_back_to_landing_when_no_deep_link() -> None:
    srcs = build_market_sources(_fx(source_event_slug=""), _poly_snapshot(), _pick())
    poly = srcs[0]
    assert poly.url == _POLYMARKET_LANDING


def test_kalshi_uses_wc_landing_today() -> None:
    srcs = build_market_sources(_fx(), _poly_snapshot(), _pick())
    assert srcs[1].url == _KALSHI_WC_LANDING


def test_priced_sides_ordering_is_stable_a_draw_b() -> None:
    # Feed prices out of order; the builder must normalise to a/draw/b.
    snap = MarketSnapshot(
        match_id="fb-wc26-fra-mex-20260612",
        asof=datetime.now(tz=timezone.utc),
        prices=(
            VenuePrice(venue="polymarket", side="b", implied_p=0.30),
            VenuePrice(venue="polymarket", side="a", implied_p=0.42),
            VenuePrice(venue="polymarket", side="draw", implied_p=0.28),
        ),
    )
    srcs = build_market_sources(_fx(), snap, _pick())
    assert srcs[0].priced_sides == ["a", "draw", "b"]
