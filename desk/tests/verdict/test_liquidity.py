"""Liquidity filter — `is_liquid` and `LiquidityRules` behaviour."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desk.verdict.compare import MarketSnapshot, VenuePrice
from desk.verdict.liquidity import LiquidityRules, is_liquid

SIDES = ("a", "draw", "b")


def _snap(prices: dict[tuple[str, str], float]) -> MarketSnapshot:
    return MarketSnapshot(
        match_id="fb-test",
        asof=datetime.now(tz=timezone.utc),
        prices=tuple(
            VenuePrice(venue=v, side=s, implied_p=p)        # type: ignore[arg-type]
            for (v, s), p in prices.items()
        ),
    )


# ── LiquidityRules.from_env ──────────────────────────────────────────

def test_default_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DESK_LIQUIDITY_MIN_P", raising=False)
    rules = LiquidityRules.from_env()
    assert rules.min_p == 0.02
    assert rules.max_p == 0.98


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_LIQUIDITY_MIN_P", "0.05")
    rules = LiquidityRules.from_env()
    assert rules.min_p == 0.05
    assert rules.max_p == 0.95


# ── is_liquid ────────────────────────────────────────────────────────

def test_healthy_market_is_liquid() -> None:
    snap = _snap({
        ("polymarket", "a"):    0.50,
        ("polymarket", "draw"): 0.27,
        ("polymarket", "b"):    0.23,
    })
    result = is_liquid(snap, SIDES)
    assert result.is_liquid is True
    assert result.reason is None


def test_extreme_long_shot_rejected() -> None:
    """Polymarket sometimes prices a side at +9999 (~1%). That's a no-opinion quote."""
    snap = _snap({
        ("polymarket", "a"):    0.50,
        ("polymarket", "draw"): 0.01,                       # ≤ 0.02 default → reject as long-shot
        ("polymarket", "b"):    0.49,
    })
    result = is_liquid(snap, SIDES)
    assert result.is_liquid is False
    assert "long_shot" in (result.reason or "")


def test_short_favourite_rejected() -> None:
    snap = _snap({
        ("polymarket", "a"):    0.99,                        # ≥ 0.98 default → reject
        ("polymarket", "draw"): 0.005,
        ("polymarket", "b"):    0.005,
    })
    result = is_liquid(snap, SIDES)
    assert result.is_liquid is False
    assert "short_favourite" in (result.reason or "")


def test_missing_side_rejected() -> None:
    snap = _snap({
        ("polymarket", "a"):    0.50,
        ("polymarket", "b"):    0.23,
        # draw absent
    })
    result = is_liquid(snap, SIDES)
    assert result.is_liquid is False
    assert "no_quote" in (result.reason or "")


def test_threshold_override_flips_borderline() -> None:
    """Spec §3.1 acceptance: env override flips a borderline case."""
    snap = _snap({
        ("polymarket", "a"):    0.50,
        ("polymarket", "draw"): 0.04,                        # under 0.05 but above 0.02
        ("polymarket", "b"):    0.46,
    })
    # Default 0.02 → liquid.
    assert is_liquid(snap, SIDES, LiquidityRules(min_p=0.02, max_p=0.98)).is_liquid
    # Tighter 0.05 → rejected.
    assert not is_liquid(snap, SIDES, LiquidityRules(min_p=0.05, max_p=0.95)).is_liquid
