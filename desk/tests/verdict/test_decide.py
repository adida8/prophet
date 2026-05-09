"""decide() — branch-by-branch tests + threshold env-override end-to-end."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desk.publish.contract import MarketVenue, Verdict, VerdictState
from desk.verdict.compare import MarketSnapshot, VenuePrice
from desk.verdict.decide import decide
from desk.verdict.thresholds import Thresholds, current

SIDES = ("a", "draw", "b")
T_DEFAULT = Thresholds(pick_pp=3.0, pass_pp=1.0, avoid_pp=-2.0)


def _snap(prices: dict[tuple[str, str], float]) -> MarketSnapshot:
    return MarketSnapshot(
        match_id="fb-wc26-fra-mex-20260612",
        asof=datetime.now(tz=timezone.utc),
        prices=tuple(
            VenuePrice(venue=v, side=s, implied_p=p)        # type: ignore[arg-type]
            for (v, s), p in prices.items()
        ),
    )


# ── Pick ──────────────────────────────────────────────────────────────

def test_pick_fires_when_one_side_clears_pick_threshold() -> None:
    """Model says France 50%; market best is 45% on Kalshi → 5pp edge."""
    model_p = {"a": 0.50, "draw": 0.25, "b": 0.25}
    market = _snap({
        ("polymarket", "a"):    0.47,
        ("kalshi",     "a"):    0.45,           # best (lowest)
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.27,
    })
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico", thresholds=T_DEFAULT,
    )
    assert v.state == VerdictState.PICK.value
    assert v.side == "France"
    assert v.market_venue == MarketVenue.KALSHI.value     # the lowest-implied venue
    assert v.edge_pp == pytest.approx(5.0, abs=0.01)
    assert v.price.startswith("+") or v.price.startswith("-")


def test_pick_picks_largest_edge_when_multiple_sides_qualify() -> None:
    """If multiple sides clear pick threshold, the biggest edge wins."""
    model_p = {"a": 0.50, "draw": 0.30, "b": 0.20}
    market = _snap({
        ("polymarket", "a"):    0.46,           # +4pp on France
        ("polymarket", "draw"): 0.21,           # +9pp on draw
        ("polymarket", "b"):    0.33,           # −13pp on Mexico
    })
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico", thresholds=T_DEFAULT,
    )
    assert v.state == VerdictState.PICK.value
    assert v.side == "draw"


# ── Pass ──────────────────────────────────────────────────────────────

def test_pass_when_every_side_within_pass_band() -> None:
    """Model agrees with market within ±1pp on every side."""
    model_p = {"a": 0.46, "draw": 0.27, "b": 0.27}
    market = _snap({
        ("polymarket", "a"):    0.465,
        ("polymarket", "draw"): 0.275,
        ("polymarket", "b"):    0.265,
    })
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico", thresholds=T_DEFAULT,
    )
    assert v.state == VerdictState.PASS.value
    assert v.side is None
    assert v.market_venue is None
    assert v.price is None


def test_pass_when_in_neither_pick_nor_avoid_band() -> None:
    """Edges between the bands → default Pass."""
    model_p = {"a": 0.48, "draw": 0.27, "b": 0.25}
    market = _snap({
        ("polymarket", "a"):    0.46,           # +2pp (below pick=3)
        ("polymarket", "draw"): 0.28,           # −1pp
        ("polymarket", "b"):    0.26,           # −1pp
    })
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico", thresholds=T_DEFAULT,
    )
    assert v.state == VerdictState.PASS.value


# ── Avoid ─────────────────────────────────────────────────────────────

def test_avoid_when_every_side_below_avoid_band() -> None:
    """Both venues priced inside our number across the board."""
    model_p = {"a": 0.30, "draw": 0.30, "b": 0.30}
    market = _snap({
        ("polymarket", "a"):    0.35,           # −5pp
        ("polymarket", "draw"): 0.34,           # −4pp
        ("polymarket", "b"):    0.36,           # −6pp
    })
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico", thresholds=T_DEFAULT,
    )
    assert v.state == VerdictState.AVOID.value
    assert v.side is None
    assert v.market_venue is None
    assert v.price is None


# ── Missing data ──────────────────────────────────────────────────────

def test_missing_side_falls_back_to_pass() -> None:
    """Spec §9: if any side is missing, default to Pass."""
    model_p = {"a": 0.50, "draw": 0.25, "b": 0.25}
    market = _snap({
        ("polymarket", "a"): 0.45,
        # draw and b absent
    })
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico", thresholds=T_DEFAULT,
    )
    assert v.state == VerdictState.PASS.value


# ── Threshold env-override flips state without code change ────────────

def test_env_override_changes_pick_into_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 4pp edge is a Pick at the default threshold but a Pass when
    DESK_PICK_PP is set higher than 4. Spec §4 PR 4 acceptance.
    """
    model_p = {"a": 0.50, "draw": 0.25, "b": 0.25}
    market = _snap({
        ("polymarket", "a"):    0.46,           # +4pp
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.27,
    })

    # Default → Pick
    monkeypatch.delenv("DESK_PICK_PP", raising=False)
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico",
        thresholds=current(),
    )
    assert v.state == VerdictState.PICK.value

    # Tighter pick threshold → Pass
    monkeypatch.setenv("DESK_PICK_PP", "5.0")
    v2 = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="France", team_b="Mexico",
        thresholds=current(),
    )
    assert v2.state == VerdictState.PASS.value


def test_env_override_changes_avoid_into_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    model_p = {"a": 0.30, "draw": 0.30, "b": 0.30}
    market = _snap({
        ("polymarket", "a"):    0.32,           # −2pp
        ("polymarket", "draw"): 0.32,           # −2pp
        ("polymarket", "b"):    0.32,           # −2pp
    })

    # Default avoid_pp = −2.0 → all sides are exactly at threshold → Avoid.
    monkeypatch.delenv("DESK_AVOID_PP", raising=False)
    v = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="A", team_b="B",
        thresholds=current(),
    )
    assert v.state == VerdictState.AVOID.value

    # Loosen avoid threshold to −3 → no longer in Avoid → Pass.
    monkeypatch.setenv("DESK_AVOID_PP", "-3.0")
    v2 = decide(
        model_p=model_p, market=market, sides=SIDES,
        team_a="A", team_b="B",
        thresholds=current(),
    )
    assert v2.state == VerdictState.PASS.value
