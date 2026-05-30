"""Unit tests for desk/pricing/cost.py — `e` (true price) per venue type."""

from __future__ import annotations

import math

import pytest

from desk.pricing.cost import (
    ExchangeCostInputs,
    PolymarketCostInputs,
    SportsbookCostInputs,
    VenueType,
    true_price,
    true_price_exchange,
    true_price_polymarket,
    true_price_sportsbook,
)


# ── Sportsbook (Pinnacle, William Hill, Sky Bet) ─────────────────────

def test_sportsbook_e_is_one_over_decimal() -> None:
    # William Hill at 5.50 → 1/5.50 = 18.18%
    e = true_price_sportsbook(SportsbookCostInputs(decimal_odds=5.50))
    assert math.isclose(e, 1.0 / 5.50, rel_tol=1e-12)


def test_sportsbook_rejects_non_positive_payout() -> None:
    with pytest.raises(ValueError):
        true_price_sportsbook(SportsbookCostInputs(decimal_odds=1.0))
    with pytest.raises(ValueError):
        true_price_sportsbook(SportsbookCostInputs(decimal_odds=0.5))


# ── Exchange (Betfair Exchange) ──────────────────────────────────────

def test_exchange_e_includes_commission_on_net_win() -> None:
    """back 5.00, 2% comm → d_eff = 1 + 4 * 0.98 = 4.92 → e = 1/4.92."""
    e = true_price_exchange(ExchangeCostInputs(back_odds=5.00, commission=0.02))
    assert math.isclose(e, 1.0 / 4.92, rel_tol=1e-12)


def test_exchange_zero_commission_equals_sportsbook_formula() -> None:
    """With c = 0, the exchange formula collapses to 1/b."""
    e_exch = true_price_exchange(ExchangeCostInputs(back_odds=3.00, commission=0.0))
    e_book = true_price_sportsbook(SportsbookCostInputs(decimal_odds=3.00))
    assert math.isclose(e_exch, e_book, rel_tol=1e-12)


def test_exchange_higher_commission_means_higher_e() -> None:
    """5% takes more bite than 2% → strictly higher implied price paid."""
    cheap = true_price_exchange(ExchangeCostInputs(back_odds=5.00, commission=0.02))
    pricy = true_price_exchange(ExchangeCostInputs(back_odds=5.00, commission=0.05))
    assert pricy > cheap


def test_exchange_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        true_price_exchange(ExchangeCostInputs(back_odds=1.0, commission=0.02))
    with pytest.raises(ValueError):
        true_price_exchange(ExchangeCostInputs(back_odds=5.0, commission=1.0))
    with pytest.raises(ValueError):
        true_price_exchange(ExchangeCostInputs(back_odds=5.0, commission=-0.01))


# ── Prediction market (Polymarket) ───────────────────────────────────

def test_polymarket_e_is_ask_plus_fee_plus_spread() -> None:
    """Argentina YES ask 0.18 + 0.75% fee + 0.10% half-spread → 18.85%."""
    inp = PolymarketCostInputs(ask=0.18, taker_fee=0.0075, half_spread=0.001)
    e   = true_price_polymarket(inp)
    assert math.isclose(e, 0.18 + 0.0075 + 0.001, rel_tol=1e-12)


def test_polymarket_default_fee_matches_scope_doc() -> None:
    """Default is the scope doc's 0.75% peak fee, 0 spread baseline."""
    e = true_price_polymarket(PolymarketCostInputs(ask=0.50))
    assert math.isclose(e, 0.5075, rel_tol=1e-12)


def test_polymarket_clamps_overage_at_one() -> None:
    """ask 0.99 + 0.0075 fee → naive 0.9975; never exceeds 1.0."""
    e = true_price_polymarket(PolymarketCostInputs(ask=0.99, taker_fee=0.02))
    assert e == 1.0


def test_polymarket_rejects_negative_components() -> None:
    with pytest.raises(ValueError):
        true_price_polymarket(PolymarketCostInputs(ask=-0.01))
    with pytest.raises(ValueError):
        true_price_polymarket(PolymarketCostInputs(ask=0.5, taker_fee=-0.01))
    with pytest.raises(ValueError):
        true_price_polymarket(PolymarketCostInputs(ask=0.5, half_spread=-0.01))


# ── Dispatch ─────────────────────────────────────────────────────────

def test_dispatch_helper() -> None:
    e_book = true_price(VenueType.SPORTSBOOK, SportsbookCostInputs(decimal_odds=2.0))
    e_exch = true_price(VenueType.EXCHANGE,   ExchangeCostInputs(back_odds=2.0, commission=0.02))
    e_pm   = true_price(VenueType.PREDICTION_MARKET, PolymarketCostInputs(ask=0.5, taker_fee=0.0))
    assert math.isclose(e_book, 0.5, rel_tol=1e-12)
    assert e_exch > 0.5     # commission pushes e up
    assert math.isclose(e_pm, 0.5, rel_tol=1e-12)


def test_scope_doc_argentina_worked_example() -> None:
    """Reproduce the §3 worked example numbers in the scope doc.

    These are the numbers the editorial line ('cheapest place to act
    = William Hill at e = 18.2%') is anchored on. Any drift here breaks
    that line.
    """
    # Polymarket ask 0.18, default fee 0.75%, spread 0 → 18.75% (scope says ~18.6%
    # which assumes some smaller fee + slippage; we just match the formula).
    e_poly = true_price_polymarket(PolymarketCostInputs(ask=0.18))
    assert math.isclose(e_poly, 0.18 + 0.0075, rel_tol=1e-12)

    # Pinnacle 5.40 → 1/5.40 ≈ 18.52%
    e_pin = true_price_sportsbook(SportsbookCostInputs(decimal_odds=5.40))
    assert math.isclose(e_pin, 1.0 / 5.40, rel_tol=1e-12)

    # William Hill 5.50 → 1/5.50 ≈ 18.18%
    e_wh = true_price_sportsbook(SportsbookCostInputs(decimal_odds=5.50))
    assert math.isclose(e_wh, 1.0 / 5.50, rel_tol=1e-12)

    # Betfair Exchange back 5.00, 2% comm → 1/4.92 ≈ 20.33%
    e_bf = true_price_exchange(ExchangeCostInputs(back_odds=5.00, commission=0.02))
    assert math.isclose(e_bf, 1.0 / 4.92, rel_tol=1e-12)

    # William Hill IS the cheapest place to act despite being the
    # least sharp book on the surface — the whole product story.
    assert e_wh < e_pin
    assert e_wh < e_poly
    assert e_wh < e_bf
