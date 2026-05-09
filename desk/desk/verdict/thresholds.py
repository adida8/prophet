"""Verdict thresholds.

Read once at process start. Override at runtime via `.env`:
    DESK_PICK_PP=3.0
    DESK_PASS_PP=1.0
    DESK_AVOID_PP=-2.0

PR 4 reads them via this module so the threshold constants live in one
place. v2's admin backend will mutate them via the
`PATCH /admin/thresholds` endpoint (spec §11).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    """All values are percentage points (pp), not decimals."""
    pick_pp:  float
    pass_pp:  float
    avoid_pp: float

    @classmethod
    def from_env(cls) -> "Thresholds":
        return cls(
            pick_pp=float(os.getenv("DESK_PICK_PP",  "3.0")),
            pass_pp=float(os.getenv("DESK_PASS_PP",  "1.0")),
            avoid_pp=float(os.getenv("DESK_AVOID_PP", "-2.0")),
        )


def current() -> Thresholds:
    """Always reads env at call time so tests can monkeypatch."""
    return Thresholds.from_env()
