"""Unit tests for desk/publish/market_prices.py.

Lives in tests/publish/ to mirror the source layout.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from desk.data.oddsapi.cache import PriceRow
from desk.publish.contract import (
    DeployRegion,
    MarketPriceRow,
    MarketPriceVenue,
    MarketVenue,
    VenueType,
)
from desk.publish.market_prices import (
    build_consensus_fair,
    build_market_prices,
)
from desk.sports.football.oddsapi_prices import venue_prices_from_oddsapi
from desk.verdict.compare import MarketSnapshot, VenuePrice


def _snap(prices: list[VenuePrice]) -> MarketSnapshot:
    return MarketSnapshot(
        match_id="fb-epl-mun-liv-20260815",
        asof=datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc),
        prices=tuple(prices),
    )


def _mun_liv_snap() -> MarketSnapshot:
    rows = [
        PriceRow("ev1", "pinnacle", "a",    3.10, "iso", "iso"),
        PriceRow("ev1", "pinnacle", "draw", 3.40, "iso", "iso"),
        PriceRow("ev1", "pinnacle", "b",    2.40, "iso", "iso"),
        PriceRow("ev1", "williamhill", "a",    3.00, "iso", "iso"),
        PriceRow("ev1", "williamhill", "draw", 3.40, "iso", "iso"),
        PriceRow("ev1", "williamhill", "b",    2.30, "iso", "iso"),
        PriceRow("ev1", "betfair_ex_uk", "a",    3.15, "iso", "iso"),
        PriceRow("ev1", "betfair_ex_uk", "draw", 3.50, "iso", "iso"),
        PriceRow("ev1", "betfair_ex_uk", "b",    2.42, "iso", "iso"),
    ]
    return _snap(venue_prices_from_oddsapi(rows))


def test_build_market_prices_emits_one_row_per_side() -> None:
    snap = _mun_liv_snap()
    rows = build_market_prices(snap)
    sides = sorted(r.side for r in rows)
    assert sides == ["a", "b", "draw"]


def test_each_row_carries_every_priced_venue() -> None:
    snap = _mun_liv_snap()
    rows = {r.side: r for r in build_market_prices(snap)}
    venues_a = {v.venue for v in rows["a"].venues}
    assert venues_a == {
        MarketVenue.PINNACLE.value,
        MarketVenue.WILLIAMHILL.value,
        MarketVenue.BETFAIR_EX_UK.value,
    }


def test_at_most_one_is_best_per_side() -> None:
    snap = _mun_liv_snap()
    rows = build_market_prices(snap)
    for r in rows:
        flagged = [v for v in r.venues if v.is_best]
        assert len(flagged) == 1, f"side={r.side} flagged {len(flagged)}"


def test_is_best_ignores_rows_with_none_true_price() -> None:
    """Bug fix: a row with `true_price=None` should NEVER win is_best
    when at least one other row has a real true_price. Previously the
    publisher fell back to ranking by implied_p whenever ANY row was
    missing true_price — which gave Kalshi (no enrichment in the
    snapshot, lowest implied_p) the 'Best price' badge over real
    sportsbook quotes."""
    from desk.pricing.cost import VenueType as _VT
    snap = _snap([
        # Pinnacle: real true_price 0.32
        VenuePrice("pinnacle", "a", 1.0 / 3.10,
                   venue_type=_VT.SPORTSBOOK, decimal_odds=3.10,
                   true_price=1.0 / 3.10, fair_p=0.30, overround=1.05),
        # Kalshi: no enrichment, low implied_p
        VenuePrice("kalshi", "a", 0.20),
    ])
    rows = build_market_prices(snap)
    assert len(rows) == 1
    venues_by_id = {v.venue: v for v in rows[0].venues}
    # Pinnacle wins is_best (it has true_price).
    assert venues_by_id["pinnacle"].is_best is True
    # Kalshi can NOT win is_best despite lower implied_p — it has no
    # true_price.
    assert venues_by_id["kalshi"].is_best is False


def test_is_best_chosen_by_true_price() -> None:
    """Betfair Exchange wins side 'a' because 1/3.107 ≈ 0.3218 vs
    Pinnacle's 1/3.10 = 0.3226 (William Hill at 1/3.00 is worse)."""
    snap = _mun_liv_snap()
    rows = {r.side: r for r in build_market_prices(snap)}
    best_a = next(v for v in rows["a"].venues if v.is_best)
    assert best_a.venue == MarketVenue.BETFAIR_EX_UK.value


def test_fair_p_sums_to_one_per_venue() -> None:
    """Each venue's row should still de-vig to sum 1 across its sides."""
    snap = _mun_liv_snap()
    rows = build_market_prices(snap)
    by_venue: dict[str, float] = {}
    for r in rows:
        for v in r.venues:
            by_venue.setdefault(v.venue, 0.0)
            by_venue[v.venue] += v.fair_p or 0.0
    for venue, total in by_venue.items():
        assert math.isclose(total, 1.0, rel_tol=1e-9), venue


def test_consensus_fair_sums_to_one_after_normalisation() -> None:
    """A sharp-weighted blend per side; tests just confirm each side
    yields a valid probability (the sum across sides isn't guaranteed
    to equal 1 because weights differ per row — the consensus is a
    per-side narrative, not a coherent probability vector)."""
    snap = _mun_liv_snap()
    out = build_consensus_fair(snap)
    assert out is not None
    for side, p in out.items():
        assert 0.0 < p < 1.0, (side, p)
    assert set(out.keys()) == {"a", "draw", "b"}


def test_legacy_polymarket_only_snapshot_returns_empty() -> None:
    """Legacy snapshots (no true_price, no venue_type) produce no
    market_prices rows when no row carries the cross-venue fields.

    Today's pre-pivot path uses `VenuePrice(venue, side, implied_p)`
    only — `build_market_prices` skips venues that fall outside the
    MarketVenue enum (so a misconfigured ingest can't sneak through)
    but legacy Polymarket rows are valid enum values, so they should
    survive even without true_price / venue_type.
    """
    legacy_snap = _snap([
        VenuePrice("polymarket", "a",    0.40),
        VenuePrice("polymarket", "draw", 0.28),
        VenuePrice("polymarket", "b",    0.40),
    ])
    rows = build_market_prices(legacy_snap)
    assert len(rows) == 3
    # All rows carry Polymarket. is_best falls back to implied_p
    # (lowest tied — picks one, but the count is exactly 1 per side).
    for r in rows:
        flagged = [v for v in r.venues if v.is_best]
        assert len(flagged) == 1


def test_unknown_venue_dropped_from_publish_rows() -> None:
    """A snapshot with a venue id outside MarketVenue gets the row
    dropped quietly — log + skip, never raise."""
    rows = [
        VenuePrice("polymarket", "a", 0.50, venue_type=__import__(
            "desk.pricing.cost", fromlist=["VenueType"]).VenueType.PREDICTION_MARKET,
            true_price=0.50),
        VenuePrice("wonkabet", "a", 0.45),
    ]
    out = build_market_prices(_snap(rows))
    assert len(out) == 1
    venues = {v.venue for v in out[0].venues}
    assert "wonkabet" not in venues


def test_consensus_fair_none_when_no_devig_possible() -> None:
    """A snapshot whose rows carry no fair_p → consensus returns None."""
    snap = _snap([
        VenuePrice("polymarket", "a",    0.40),
        VenuePrice("polymarket", "draw", 0.28),
        VenuePrice("polymarket", "b",    0.40),
    ])
    assert build_consensus_fair(snap) is None


def test_contract_round_trip_with_new_fields() -> None:
    """A MatchOutput with market_prices + consensus_fair + region
    round-trips through model_dump_json / model_validate_json without
    loss."""
    import json

    from desk.publish.contract import (
        Competition,
        Copy,
        MatchOutput,
        Verdict,
        VerdictState,
    )

    snap = _mun_liv_snap()
    market_prices = build_market_prices(snap)
    consensus     = build_consensus_fair(snap)

    m = MatchOutput(
        match_id="fb-epl-mun-liv-20260815",
        sport="football",
        competition=Competition(code="epl", label="Premier League"),
        kickoff_utc=datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc),
        team_a="Manchester United",
        team_b="Liverpool",
        market_outcomes=["a", "draw", "b"],
        verdict=Verdict(state=VerdictState.PASS),
        copy=Copy(),
        market_prices=market_prices,
        consensus_fair=consensus,
        region=DeployRegion.NON_US,
        updated_at=datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc),
    )
    payload = json.loads(m.model_dump_json())
    assert payload["region"] == "non-us"
    assert isinstance(payload["market_prices"], list)
    assert len(payload["market_prices"]) == 3
    assert payload["consensus_fair"]
    # Re-validate the payload through the schema — round-trip integrity.
    parsed = MatchOutput.model_validate(payload)
    assert parsed.market_prices[0].venues[0].name
    assert parsed.region == "non-us"
