"""Snapshot diff — typed change events between two run snapshots.

Spec: `THE_DESK_OPS_DASHBOARD_SPEC.md` §5. The runner calls `diff_snapshots()`
at the tail of each pass with (previous_run.snapshot, this_run.snapshot)
and persists the resulting list under `RunReport.changes`.

Pure function; no I/O. The recorder is what loads the previous snapshot
off disk and feeds it in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Literal

from desk.ops.report import FixtureRow

DEFAULT_EDGE_DELTA_PP = 1.0

ChangeType = Literal["new", "dropped", "flip", "side", "edge", "venue", "copy"]


def _edge_threshold() -> float:
    """Minimum |edge_pp delta| that fires an `edge` change.

    Env-overridable to tune dashboard noise without a code change.
    Falls back to spec default on a bad value (operator typo shouldn't
    silently break the diff).
    """
    try:
        v = float(os.getenv("DESK_OPS_EDGE_DELTA_PP", str(DEFAULT_EDGE_DELTA_PP)))
    except ValueError:
        return DEFAULT_EDGE_DELTA_PP
    return max(0.0, v)


@dataclass(frozen=True)
class MatchChange:
    """One typed change between two consecutive runs.

    Carrier fields are sparse on purpose: `new`/`dropped`/`copy` have no
    extra payload, `flip`/`side` carry from/to, `edge`/`venue` use
    `detail` for a human-readable string. The dashboard renders this
    structure directly.
    """
    type:     ChangeType
    match_id: str
    from_:    str | None = None      # serialised as `from` via to_dict()
    to:       str | None = None
    detail:   str | None = None

    def to_dict(self) -> dict:
        out: dict = {"type": self.type, "match_id": self.match_id}
        if self.from_ is not None: out["from"]   = self.from_
        if self.to    is not None: out["to"]     = self.to
        if self.detail is not None: out["detail"] = self.detail
        return out


def _format_edge_detail(prev: float, now: float) -> str:
    """`+2.1pp (3.4 → 5.5)` — sign-led delta + the values either side."""
    delta = now - prev
    sign  = "+" if delta >= 0 else "−"
    return f"{sign}{abs(delta):.1f}pp ({prev:.1f} → {now:.1f})"


def _format_venue_detail(prev: set[str], now: set[str]) -> str:
    """Comma-separated `+ kalshi · − polymarket`-style description."""
    added   = sorted(now - prev)
    removed = sorted(prev - now)
    parts: list[str] = []
    parts.extend(f"+ {v}" for v in added)
    parts.extend(f"− {v}" for v in removed)
    return " · ".join(parts)


def diff_snapshots(
    previous: Iterable[FixtureRow] | None,
    current:  Iterable[FixtureRow],
    *,
    edge_threshold_pp: float | None = None,
) -> list[MatchChange]:
    """Return typed changes between two snapshots.

    First run ever (`previous is None`) returns `[]` per spec §5.

    Per-fixture rules (in order — only the *first* matching state-level
    rule fires, but `edge`/`venue`/`copy` are additive on top of state):

    - `new`     ── match in current, absent in previous
    - `dropped` ── present in previous, absent in current
    - `flip`    ── verdict_state changed
    - `side`    ── still a Pick, but pick_side changed
    - `edge`    ── |edge_pp delta| ≥ threshold (additive — can pair with copy/venue)
    - `venue`   ── venues set membership changed (additive)
    - `copy`    ── copy_hash changed (additive)
    """
    out: list[MatchChange] = []
    if previous is None:
        return out

    threshold = edge_threshold_pp if edge_threshold_pp is not None else _edge_threshold()

    prev_by_id = {r.match_id: r for r in previous}
    curr_by_id = {r.match_id: r for r in current}

    prev_ids = set(prev_by_id)
    curr_ids = set(curr_by_id)

    for mid in sorted(curr_ids - prev_ids):
        out.append(MatchChange(type="new", match_id=mid))

    for mid in sorted(prev_ids - curr_ids):
        out.append(MatchChange(type="dropped", match_id=mid))

    for mid in sorted(prev_ids & curr_ids):
        prev = prev_by_id[mid]
        now  = curr_by_id[mid]

        # ── State-level: flip OR side (mutually exclusive) ─────
        if prev.verdict_state != now.verdict_state:
            out.append(MatchChange(
                type="flip", match_id=mid,
                from_=prev.verdict_state, to=now.verdict_state,
            ))
        elif (prev.verdict_state == "pick"
              and prev.pick_side != now.pick_side):
            out.append(MatchChange(
                type="side", match_id=mid,
                from_=prev.pick_side, to=now.pick_side,
            ))

        # ── Additive: edge, venue, copy ─────────────────────────
        if (prev.edge_pp is not None and now.edge_pp is not None
                and abs(now.edge_pp - prev.edge_pp) >= threshold):
            out.append(MatchChange(
                type="edge", match_id=mid,
                detail=_format_edge_detail(prev.edge_pp, now.edge_pp),
            ))

        prev_venues = set(prev.venues)
        curr_venues = set(now.venues)
        if prev_venues != curr_venues:
            out.append(MatchChange(
                type="venue", match_id=mid,
                detail=_format_venue_detail(prev_venues, curr_venues),
            ))

        if prev.copy_hash != now.copy_hash:
            out.append(MatchChange(type="copy", match_id=mid))

    return out
