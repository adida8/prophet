"""End-to-end parse of a Kalshi event's markets payload into a
fixture-keyed `MarketSnapshot`."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from desk.ingest.kalshi_prices import (
    snapshots_from_event,
    _midpoint,
    _parse_dollar,
    _side_for_suffix,
)
from desk.verdict.compare import MarketSnapshot, VenuePrice

FIXTURES = Path(__file__).parent.parent / "fixtures" / "kalshi"


@pytest.fixture
def mexrsa_markets() -> list[dict]:
    raw = json.loads(
        (FIXTURES / "markets_KXWCGAME-26JUN11MEXRSA.json").read_text()
    )
    return raw["markets"]


@pytest.fixture
def asof() -> datetime:
    return datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


class TestSnapshotFromEvent:
    def test_builds_three_venueprices(
        self, mexrsa_markets: list[dict], asof: datetime
    ) -> None:
        result = snapshots_from_event(
            event_ticker="KXWCGAME-26JUN11MEXRSA",
            markets=mexrsa_markets,
            asof=asof,
        )
        assert result is not None
        key, snap = result
        assert key == (date(2026, 6, 11), frozenset({"mex", "rsa"}))
        assert isinstance(snap, MarketSnapshot)
        assert len(snap.prices) == 3
        assert all(p.venue == "kalshi" for p in snap.prices)
        assert {p.side for p in snap.prices} == {"a", "b", "draw"}

    def test_midpoint_implied_p(
        self, mexrsa_markets: list[dict], asof: datetime
    ) -> None:
        """Mexico side: yes_bid=0.64, yes_ask=0.65 → midpoint 0.645."""
        _key, snap = snapshots_from_event(
            event_ticker="KXWCGAME-26JUN11MEXRSA",
            markets=mexrsa_markets,
            asof=asof,
        )
        # Mexico is team_a in this ticker (MEX precedes RSA), so side="a".
        side_a = next(p for p in snap.prices if p.side == "a")
        assert side_a.implied_p == pytest.approx(0.645, rel=1e-6)

        # Tie midpoint: 0.21/0.22 → 0.215
        draw = next(p for p in snap.prices if p.side == "draw")
        assert draw.implied_p == pytest.approx(0.215, rel=1e-6)

        # South Africa: 0.12/0.15 → 0.135
        side_b = next(p for p in snap.prices if p.side == "b")
        assert side_b.implied_p == pytest.approx(0.135, rel=1e-6)

    def test_inactive_markets_skipped(
        self, mexrsa_markets: list[dict], asof: datetime
    ) -> None:
        # Knock the MEX market out of "active"
        muted = [
            dict(m, status="closed") if m["ticker"].endswith("-MEX") else m
            for m in mexrsa_markets
        ]
        _key, snap = snapshots_from_event(
            event_ticker="KXWCGAME-26JUN11MEXRSA",
            markets=muted,
            asof=asof,
        )
        sides = {p.side for p in snap.prices}
        assert sides == {"b", "draw"}

    def test_unparseable_event_ticker_returns_none(
        self, mexrsa_markets: list[dict], asof: datetime
    ) -> None:
        assert (
            snapshots_from_event(
                event_ticker="garbage",
                markets=mexrsa_markets,
                asof=asof,
            )
            is None
        )

    def test_missing_prices_skip_silently(self, asof: datetime) -> None:
        markets = [
            {
                "ticker": "KXWCGAME-26JUN11MEXRSA-MEX",
                "yes_sub_title": "Mexico",
                "yes_bid_dollars": None,
                "yes_ask_dollars": None,
                "status": "active",
            },
            {
                "ticker": "KXWCGAME-26JUN11MEXRSA-TIE",
                "yes_sub_title": "Tie",
                "yes_bid_dollars": "0.20",
                "yes_ask_dollars": "0.22",
                "status": "active",
            },
        ]
        _key, snap = snapshots_from_event(
            event_ticker="KXWCGAME-26JUN11MEXRSA",
            markets=markets,
            asof=asof,
        )
        # Only the draw market makes it through.
        assert {p.side for p in snap.prices} == {"draw"}


class TestHelpers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0.6400", 0.64),
            ("0.0000", 0.0),
            ("1.0000", 1.0),
            ("", None),
            (None, None),
            ("garbage", None),
            ("-0.10", None),    # negative implied_p
            ("1.50", None),     # > 1
        ],
    )
    def test_parse_dollar(self, raw, expected) -> None:
        assert _parse_dollar(raw) == expected

    def test_midpoint(self) -> None:
        assert _midpoint("0.40", "0.60") == pytest.approx(0.50)

    def test_midpoint_one_side_missing(self) -> None:
        assert _midpoint("0.40", None) == pytest.approx(0.40)
        assert _midpoint(None, "0.60") == pytest.approx(0.60)
        assert _midpoint(None, None) is None

    @pytest.mark.parametrize(
        "suffix,team_a,team_b,expected",
        [
            ("mex", "mex", "rsa", "a"),
            ("rsa", "mex", "rsa", "b"),
            ("tie", "mex", "rsa", "draw"),
            ("usa", "mex", "rsa", None),     # not on this fixture
        ],
    )
    def test_side_for_suffix(self, suffix, team_a, team_b, expected) -> None:
        assert _side_for_suffix(suffix, team_a_code=team_a, team_b_code=team_b) == expected
