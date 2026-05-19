"""Polymarket + Kalshi merge logic for priced fixtures."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from desk.sport import FixtureRef
from desk.sports.football.priced import _fixture_key, _merge_kalshi
from desk.verdict.compare import MarketSnapshot, VenuePrice

UTC = timezone.utc


def _fx(
    *,
    match_id: str = "fb-wc26-mex-rsa-20260611",
    team_a: str = "Mexico",
    team_b: str = "South Africa",
    kickoff: datetime = datetime(2026, 6, 11, 19, 0, tzinfo=UTC),
) -> FixtureRef:
    return FixtureRef(
        match_id=match_id,
        sport="football",
        competition_code="wc26",
        competition_label="FIFA World Cup 2026",
        competition_stage=None,
        team_a=team_a,
        team_b=team_b,
        kickoff_utc=kickoff,
        market_outcomes=("a", "draw", "b"),
        venue_city=None,
        venue_stadium=None,
        venue_country=None,
    )


class TestFixtureKey:
    def test_wc26_match_id(self) -> None:
        assert _fixture_key("fb-wc26-mex-rsa-20260611") == (
            date(2026, 6, 11), frozenset({"mex", "rsa"}),
        )

    def test_club_match_id(self) -> None:
        # Club ids are `fb-{league}-{teamA}-{teamB}-{date}` — same shape.
        assert _fixture_key("fb-epl-mun-liv-20260815") == (
            date(2026, 8, 15), frozenset({"mun", "liv"}),
        )

    def test_team_pair_is_order_independent(self) -> None:
        assert _fixture_key("fb-wc26-mex-rsa-20260611") == _fixture_key(
            "fb-wc26-rsa-mex-20260611"
        )

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "fb-wc26-mex",
            "fb-wc26-mex-rsa-bad",
            "fb-wc26-mex-rsa-20269999",   # bogus date
        ],
    )
    def test_malformed_returns_none(self, bad: str) -> None:
        assert _fixture_key(bad) is None


class TestMergeKalshi:
    def test_kalshi_prices_appended(self) -> None:
        pm_snap = MarketSnapshot(
            match_id="fb-wc26-mex-rsa-20260611",
            asof=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            prices=(
                VenuePrice(venue="polymarket", side="a",    implied_p=0.60),
                VenuePrice(venue="polymarket", side="b",    implied_p=0.18),
                VenuePrice(venue="polymarket", side="draw", implied_p=0.22),
            ),
        )
        kalshi_snap = MarketSnapshot(
            match_id="",
            asof=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            prices=(
                VenuePrice(venue="kalshi", side="a",    implied_p=0.645),
                VenuePrice(venue="kalshi", side="b",    implied_p=0.135),
                VenuePrice(venue="kalshi", side="draw", implied_p=0.215),
            ),
        )
        merged = _merge_kalshi(pm_snap, kalshi_snap)
        assert merged.match_id == "fb-wc26-mex-rsa-20260611"
        assert len(merged.prices) == 6
        venues = {p.venue for p in merged.prices}
        assert venues == {"polymarket", "kalshi"}

    def test_best_for_picks_lower_implied_p(self) -> None:
        """For the bettor: lower implied_p = higher payout. `best_for`
        picks the lowest across venues."""
        pm_snap = MarketSnapshot(
            match_id="fb-wc26-mex-rsa-20260611",
            asof=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            prices=(VenuePrice(venue="polymarket", side="a", implied_p=0.60),),
        )
        kalshi_snap = MarketSnapshot(
            match_id="",
            asof=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            prices=(VenuePrice(venue="kalshi", side="a", implied_p=0.645),),
        )
        merged = _merge_kalshi(pm_snap, kalshi_snap)
        # Polymarket is the better price for side "a" here.
        best = merged.best_for("a")
        assert best is not None and best.venue == "polymarket"

        # Flip the prices — Kalshi wins.
        pm_snap2 = MarketSnapshot(
            match_id="fb-wc26-mex-rsa-20260611",
            asof=pm_snap.asof,
            prices=(VenuePrice(venue="polymarket", side="a", implied_p=0.70),),
        )
        merged2 = _merge_kalshi(pm_snap2, kalshi_snap)
        best2 = merged2.best_for("a")
        assert best2 is not None and best2.venue == "kalshi"

    def test_no_kalshi_snapshot_returns_polymarket(self) -> None:
        pm_snap = MarketSnapshot(
            match_id="fb-wc26-mex-rsa-20260611",
            asof=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            prices=(VenuePrice(venue="polymarket", side="a", implied_p=0.60),),
        )
        merged = _merge_kalshi(pm_snap, None)
        assert merged is pm_snap

    def test_empty_kalshi_returns_polymarket(self) -> None:
        pm_snap = MarketSnapshot(
            match_id="fb-wc26-mex-rsa-20260611",
            asof=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
            prices=(VenuePrice(venue="polymarket", side="a", implied_p=0.60),),
        )
        empty_kalshi = MarketSnapshot(
            match_id="",
            asof=pm_snap.asof,
            prices=(),
        )
        merged = _merge_kalshi(pm_snap, empty_kalshi)
        assert merged is pm_snap
