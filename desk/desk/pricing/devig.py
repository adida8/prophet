"""De-vig — strip a bookmaker's margin off a quoted outcome set.

A sportsbook's quoted implied probabilities sum to more than 1 — the
excess is the overround / margin / vig. De-vig turns that into a
margin-stripped probability that sums to 1, the venue's honest opinion.

v1 implements the multiplicative method: `fair_i = implied_i / Σ`.
Cheap, stable, fine for low-overround 3-way (104-107%). The seam for
Shin / power-method is intentionally explicit because outrights need
it later (135%+ overrounds over-shade favourites under multiplicative).

The output is for the consensus narrative ONLY — `fair_p` never drives
the verdict's edge. See `desk/pricing/cost.py` for the price the
verdict actually uses (`e` = true price).
"""

from __future__ import annotations

from enum import Enum
from typing import Sequence


class DevigMethod(str, Enum):
    """Strategy enum. v1 only ships MULTIPLICATIVE; the others are
    placeholders kept here so the call sites name the method explicitly
    — easier to grep for when Shin lands."""
    MULTIPLICATIVE = "multiplicative"
    SHIN           = "shin"             # not implemented yet
    POWER          = "power"            # not implemented yet


def devig_multiplicative(implied: Sequence[float]) -> list[float]:
    """`fair_i = implied_i / Σ implied`. Sums to exactly 1.0.

    Caller passes the full outcome set for a market (e.g. all three of
    home / draw / away). Mixing sides from different markets is a bug —
    the sum needs to be a single overround.
    """
    if not implied:
        raise ValueError("devig: implied is empty; pass the full outcome set.")
    for p in implied:
        if not (0.0 <= p <= 1.0):
            raise ValueError(
                f"devig: implied probabilities must be in [0, 1] (got {p})."
            )
    total = sum(implied)
    if total <= 0.0:
        raise ValueError(
            f"devig: sum of implied probabilities is {total}; "
            "cannot strip margin from an unpriced market."
        )
    return [p / total for p in implied]


def devig(implied: Sequence[float], *, method: DevigMethod = DevigMethod.MULTIPLICATIVE) -> list[float]:
    """Strategy dispatch. Default = multiplicative.

    Raises `NotImplementedError` for methods that aren't wired yet —
    we want call sites that ask for Shin to fail loud, not silently
    fall back to multiplicative (the whole point of asking for Shin is
    you don't want multiplicative).
    """
    if method == DevigMethod.MULTIPLICATIVE:
        return devig_multiplicative(implied)
    raise NotImplementedError(
        f"de-vig method {method.value!r} not implemented; "
        "v1 ships multiplicative only — Shin / power are outrights-only seams."
    )
