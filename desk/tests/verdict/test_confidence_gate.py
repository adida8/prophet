"""Phase A.3 — verdict's lower-bound Pick gate.

When `model_p_lower` is supplied to `decide()`, a Pick fires only when
the *lower bound* of the model's probability clears the threshold
against the market — not just the point estimate.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desk.publish.contract import VerdictState
from desk.verdict.compare import MarketSnapshot, VenuePrice
from desk.verdict.decide import decide
from desk.verdict.thresholds import Thresholds

SIDES = ("a", "draw", "b")
T = Thresholds(pick_pp=3.0, pass_pp=1.0, avoid_pp=-2.0)


def _snap(prices: dict[tuple[str, str], float]) -> MarketSnapshot:
    return MarketSnapshot(
        match_id="fb-test",
        asof=datetime.now(tz=timezone.utc),
        prices=tuple(
            VenuePrice(venue=v, side=s, implied_p=p)        # type: ignore[arg-type]
            for (v, s), p in prices.items()
        ),
    )


def test_pick_fires_when_lower_bound_clears_threshold() -> None:
    """Tight band: point=0.50, lower=0.49 (only 1pp below). Market=0.45.
    Lower-bound edge = 4pp ≥ pick_pp → Pick.
    """
    model_p       = {"a": 0.50, "draw": 0.25, "b": 0.25}
    model_p_lower = {"a": 0.49, "draw": 0.23, "b": 0.23}
    market = _snap({
        ("polymarket", "a"):    0.45,
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.28,
    })
    v = decide(
        model_p=model_p, model_p_lower=model_p_lower, market=market,
        sides=SIDES, team_a="A", team_b="B", thresholds=T,
    )
    assert v.state == VerdictState.PICK.value


def test_wide_band_kills_a_borderline_pick() -> None:
    """Same point estimate, but wide band. Lower bound is 0.43.
    Market=0.45. Lower-bound edge = -2pp < pick_pp → no Pick.
    """
    model_p       = {"a": 0.50, "draw": 0.25, "b": 0.25}
    model_p_lower = {"a": 0.43, "draw": 0.20, "b": 0.20}
    market = _snap({
        ("polymarket", "a"):    0.45,
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.28,
    })
    v = decide(
        model_p=model_p, model_p_lower=model_p_lower, market=market,
        sides=SIDES, team_a="A", team_b="B", thresholds=T,
    )
    # Without the band the +5pp would have been a Pick; with the band
    # it's a Pass — the lower-bound edge is only -2pp.
    assert v.state == VerdictState.PASS.value


def test_no_band_falls_back_to_point_estimate() -> None:
    """Backwards-compatible: callers that don't supply a band see the
    same Pick logic as before."""
    model_p = {"a": 0.50, "draw": 0.25, "b": 0.25}
    market = _snap({
        ("polymarket", "a"):    0.45,
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.28,
    })
    v = decide(
        model_p=model_p, market=market,
        sides=SIDES, team_a="A", team_b="B", thresholds=T,
    )
    assert v.state == VerdictState.PICK.value
