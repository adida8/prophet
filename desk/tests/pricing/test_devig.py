"""Unit tests for desk/pricing/devig.py."""

from __future__ import annotations

import math

import pytest

from desk.pricing.devig import DevigMethod, devig, devig_multiplicative


def test_multiplicative_sums_to_one_3way() -> None:
    """Standard 1X2 with ~107% overround → fair sums to exactly 1.0."""
    # Pinnacle-ish 1X2 quote: 1/2.10 + 1/3.40 + 1/3.80 ≈ 1.060
    implied = [1.0 / 2.10, 1.0 / 3.40, 1.0 / 3.80]
    fair = devig_multiplicative(implied)
    assert math.isclose(sum(fair), 1.0, rel_tol=1e-12)
    # Ordering preserved
    assert fair[0] > fair[1]
    assert fair[1] > fair[2]


def test_multiplicative_normalizes_inflated_book() -> None:
    """A 135% overround outright book de-vigs cleanly."""
    implied = [0.20, 0.50, 0.65]   # sums to 1.35
    fair = devig_multiplicative(implied)
    assert math.isclose(sum(fair), 1.0, rel_tol=1e-12)
    # Multiplicative scales each implied by 1 / 1.35 ≈ 0.741
    assert math.isclose(fair[0], 0.20 / 1.35, rel_tol=1e-12)
    assert math.isclose(fair[1], 0.50 / 1.35, rel_tol=1e-12)
    assert math.isclose(fair[2], 0.65 / 1.35, rel_tol=1e-12)


def test_favourite_longshot_ordering_preserved() -> None:
    """Multiplicative never reorders sides — favourite stays favourite."""
    implied = [0.55, 0.30, 0.21]   # 106%
    fair = devig_multiplicative(implied)
    assert fair[0] == max(fair)
    assert fair[2] == min(fair)


def test_dispatch_routes_multiplicative() -> None:
    fair = devig([0.50, 0.25, 0.30], method=DevigMethod.MULTIPLICATIVE)
    assert math.isclose(sum(fair), 1.0, rel_tol=1e-12)


def test_dispatch_unimplemented_methods_raise() -> None:
    """Asking for Shin / power must fail loud — silently falling back to
    multiplicative would defeat the purpose of asking."""
    with pytest.raises(NotImplementedError, match="shin"):
        devig([0.30, 0.40, 0.40], method=DevigMethod.SHIN)
    with pytest.raises(NotImplementedError, match="power"):
        devig([0.30, 0.40, 0.40], method=DevigMethod.POWER)


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        devig_multiplicative([])


def test_out_of_range_implied_raises() -> None:
    with pytest.raises(ValueError, match="\\[0, 1\\]"):
        devig_multiplicative([0.5, 1.2, 0.4])


def test_total_zero_raises() -> None:
    """A 0/0/0 market means nothing's priced — can't strip margin."""
    with pytest.raises(ValueError, match="cannot strip margin"):
        devig_multiplicative([0.0, 0.0, 0.0])
