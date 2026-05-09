"""Multi-window Pick persistence (Phase A.3).

Per THE_DESK_OPTIMIZATION_SPEC §3 Phase A.3, a Pick verdict only ships
when the same Pick side persisted across the prior verdict windows:

    T-5  → T-1h → KO   all Pick the same side, or
           T-1h → KO   both Pick the same side  (when T-5 wasn't computed)

A single-window edge is noise; an edge that survives the market gaining
new information (line moves, lineup news, weather updates) between T-5
and KO is signal. The rule is the spec's strongest selection-discipline
filter — most over-confident model outputs flicker between Pick and
Pass across windows, and persistence rejects them.

This module ships the pure function. The backtest applies it as a
post-processing pass over a match's per-window snapshots; the live
engine will apply it in PR 6 (scheduler) once it has window awareness
and a per-match verdict cache.

Inputs are lightweight `WindowVerdict` records — just (state, side) —
so callers can synthesise them from snapshot rows without paying the
Pydantic `Verdict` model's full-output validation cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Optional

# Windows in time order; KO is the published window.
PersistenceWindow = Literal["T-5", "T-1h", "KO"]
PERSISTENCE_WINDOWS: tuple[PersistenceWindow, ...] = ("T-5", "T-1h", "KO")


@dataclass(frozen=True)
class WindowVerdict:
    """Minimal verdict shape the persistence rule needs."""
    state: str                          # "pick" / "pass" / "avoid"
    side:  Optional[str] = None         # only relevant when state == "pick"


@dataclass(frozen=True)
class PersistenceResult:
    persistent: bool
    reason: str          # "ok" | "not_persistent" | "not_a_pick"


def _is_pick(v: Optional[WindowVerdict]) -> bool:
    return v is not None and v.state == "pick"


def apply_persistence_rule(
    current: WindowVerdict,
    *,
    prior_verdicts: Mapping[str, WindowVerdict],
) -> PersistenceResult:
    """Gate a Pick on multi-window agreement.

    `current` is the verdict at the published window (KO).
    `prior_verdicts` maps prior window labels to their `WindowVerdict`;
    the function reads "T-5" and "T-1h" — anything else is ignored.
    Missing keys are treated as "not computed".

    Returns:
      - persistent=True,  reason="not_a_pick"     — current isn't a Pick.
      - persistent=True,  reason="ok"             — Pick survived the rule.
      - persistent=False, reason="not_persistent" — Pick rejected.
    """
    if not _is_pick(current):
        return PersistenceResult(persistent=True, reason="not_a_pick")

    pick_side = current.side

    t5  = prior_verdicts.get("T-5")
    t1h = prior_verdicts.get("T-1h")

    def matches(v: Optional[WindowVerdict]) -> bool:
        return _is_pick(v) and v is not None and v.side == pick_side

    # The "latest two" — T-1h must Pick the same side as KO.
    if not matches(t1h):
        return PersistenceResult(persistent=False, reason="not_persistent")

    # If T-5 was computed it must agree too. ("All three" rule.)
    if t5 is not None and not matches(t5):
        return PersistenceResult(persistent=False, reason="not_persistent")

    return PersistenceResult(persistent=True, reason="ok")
