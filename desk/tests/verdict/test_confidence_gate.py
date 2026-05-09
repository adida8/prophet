"""Phase A.2 — verdict's calibration-aware Pick gate.

When `model_p_lower` is supplied, a Pick fires only when BOTH
  (a) raw edge        ≥ pick_pp           (default 3.0pp), and
  (b) lower-CI edge   ≥ pick_lower_pp     (default 1.0pp).

The dual gate rejects extreme-but-shaky model outputs that look like
edges on paper but vanish under Elo uncertainty.
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.publish.contract import VerdictState
from desk.verdict.compare import MarketSnapshot, VenuePrice
from desk.verdict.decide import decide
from desk.verdict.thresholds import Thresholds

SIDES = ("a", "draw", "b")
T = Thresholds(pick_pp=3.0, pick_lower_pp=1.0, pass_pp=1.0, avoid_pp=-2.0)


def _snap(prices: dict[tuple[str, str], float]) -> MarketSnapshot:
    return MarketSnapshot(
        match_id="fb-test",
        asof=datetime.now(tz=timezone.utc),
        prices=tuple(
            VenuePrice(venue=v, side=s, implied_p=p)        # type: ignore[arg-type]
            for (v, s), p in prices.items()
        ),
    )


def test_pick_fires_when_both_gates_clear() -> None:
    """Tight band: point=0.50, lower=0.49 (only 1pp below). Market=0.45.
    Raw edge = 5pp ≥ 3pp ✓; lower edge = 4pp ≥ 1pp ✓ → Pick.
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
    Market=0.45. Lower-bound edge = -2pp < 1pp → no Pick.
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
    assert v.state == VerdictState.PASS.value


def test_lower_band_just_below_one_pp_fails() -> None:
    """The 1pp lower-bound floor is exact: lower = 0.4599 → 0.99pp gap
    should fail; 0.4601 → 1.01pp should pass."""
    market = _snap({
        ("polymarket", "a"):    0.45,
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.28,
    })
    just_below = decide(
        model_p={"a": 0.50, "draw": 0.25, "b": 0.25},
        model_p_lower={"a": 0.4599, "draw": 0.20, "b": 0.20},
        market=market, sides=SIDES, team_a="A", team_b="B", thresholds=T,
    )
    just_above = decide(
        model_p={"a": 0.50, "draw": 0.25, "b": 0.25},
        model_p_lower={"a": 0.4601, "draw": 0.20, "b": 0.20},
        market=market, sides=SIDES, team_a="A", team_b="B", thresholds=T,
    )
    assert just_below.state == VerdictState.PASS.value
    assert just_above.state == VerdictState.PICK.value


def test_raw_edge_below_3pp_blocks_pick_even_with_strong_lower_band() -> None:
    """If the raw edge is only 2pp, the Pick is blocked regardless of
    how good the lower-bound looks — calibration discipline still
    requires meaningful disagreement with the market."""
    model_p       = {"a": 0.47, "draw": 0.27, "b": 0.26}
    model_p_lower = {"a": 0.46, "draw": 0.25, "b": 0.24}      # lower edge = 1pp ≥ 1pp
    market = _snap({
        ("polymarket", "a"):    0.45,
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.28,
    })
    v = decide(
        model_p=model_p, model_p_lower=model_p_lower, market=market,
        sides=SIDES, team_a="A", team_b="B", thresholds=T,
    )
    assert v.state == VerdictState.PASS.value


def test_no_band_falls_back_to_point_estimate() -> None:
    """Backwards-compatible: callers that don't supply a band see the
    raw-edge gate alone (PR 4 behaviour)."""
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
