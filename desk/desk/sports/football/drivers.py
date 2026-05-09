"""Football drivers — ranked attribution of what moved the model.

Drivers are how the explainer tells the user *why* the model called
what it did. PR 5 turns these into prose; PR 3 just produces them.

A driver is a tuple of (label, signed_pp_impact, side). `side` is "a",
"b", or "draw" — whichever outcome's probability the driver pushed
toward. The explainer presents drivers ordered by absolute pp impact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Driver:
    label: str
    pp_impact: float    # signed percentage-point shift on the favoured side
    side:  Literal["a", "b", "draw"]
