"""PR 3 — diff engine tests.

Mirrors `THE_DESK_OPS_DASHBOARD_SPEC.md` §5: each change type fires
exactly when the spec says, including first-run-empty and the edge
threshold boundary.
"""

from __future__ import annotations

import pytest

from desk.ops.diff import (
    DEFAULT_EDGE_DELTA_PP,
    MatchChange,
    diff_snapshots,
)
from desk.ops.report import FixtureRow

# 64-hex copy hash placeholders. Same hash → no `copy` event;
# different hashes → `copy` event fires.
_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _row(
    match_id: str,
    *,
    verdict_state: str = "pass",
    pick_side: str | None = None,
    edge_pp: float | None = None,
    venues: list[str] | None = None,
    copy_hash: str = _HASH_A,
) -> FixtureRow:
    return FixtureRow(
        match_id=match_id,
        verdict_state=verdict_state,
        pick_side=pick_side,
        edge_pp=edge_pp,
        venues=venues if venues is not None else ["polymarket"],
        copy_hash=copy_hash,
    )


# ── First-run / empty inputs ─────────────────────────────────────────

def test_first_run_returns_empty() -> None:
    """Spec §5: first run ever (no previous snapshot) → no changes."""
    assert diff_snapshots(None, [_row("fb-wc26-fra-mex-20260612")]) == []


def test_identical_snapshots_yield_no_changes() -> None:
    rows = [_row("fb-wc26-fra-mex-20260612"), _row("fb-wc26-usa-can-20260613")]
    assert diff_snapshots(rows, rows) == []


# ── new / dropped ────────────────────────────────────────────────────

def test_new_match_fires_new() -> None:
    prev = [_row("fb-wc26-fra-mex-20260612")]
    curr = [
        _row("fb-wc26-fra-mex-20260612"),
        _row("fb-wc26-usa-can-20260613"),
    ]
    out = diff_snapshots(prev, curr)
    assert out == [MatchChange(type="new", match_id="fb-wc26-usa-can-20260613")]


def test_dropped_match_fires_dropped() -> None:
    prev = [
        _row("fb-wc26-fra-mex-20260612"),
        _row("fb-wc26-usa-can-20260613"),
    ]
    curr = [_row("fb-wc26-fra-mex-20260612")]
    out = diff_snapshots(prev, curr)
    assert out == [MatchChange(type="dropped", match_id="fb-wc26-usa-can-20260613")]


# ── flip / side ──────────────────────────────────────────────────────

def test_verdict_state_change_fires_flip() -> None:
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pass")]
    curr = [_row(mid, verdict_state="pick", pick_side="France",
                 edge_pp=4.0, copy_hash=_HASH_A)]
    out = diff_snapshots(prev, curr)
    # State changed pass→pick; the same row also crossed the 1pp edge gate
    # going from None to 4.0pp, but None means we can't compute |delta|
    # so no `edge` event. Net: just the flip.
    assert any(c.type == "flip" and c.from_ == "pass" and c.to == "pick"
               for c in out)


def test_pick_side_change_fires_side_only() -> None:
    """Pick → Pick but the side flipped (e.g. model rotated to draw).
    `flip` does not fire because verdict_state is unchanged; `side` does.
    """
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=3.2)]
    curr = [_row(mid, verdict_state="pick", pick_side="draw", edge_pp=3.2)]
    out = diff_snapshots(prev, curr)
    assert [c.type for c in out] == ["side"]
    assert out[0].from_ == "France"
    assert out[0].to    == "draw"


def test_flip_and_side_are_mutually_exclusive() -> None:
    """Spec §5: when state changes, the from→to is on `flip`, not `side`."""
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=3.2)]
    curr = [_row(mid, verdict_state="pass", pick_side=None, edge_pp=None)]
    out = diff_snapshots(prev, curr)
    types = [c.type for c in out]
    assert "flip" in types
    assert "side" not in types


# ── edge threshold ────────────────────────────────────────────────────

def test_edge_event_fires_at_or_above_threshold() -> None:
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=3.4)]
    curr = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=5.5)]
    out = diff_snapshots(prev, curr)
    edge_evt = next((c for c in out if c.type == "edge"), None)
    assert edge_evt is not None
    assert edge_evt.detail == "+2.1pp (3.4 → 5.5)"


def test_edge_event_skips_when_below_threshold() -> None:
    """0.9pp delta with default 1.0pp threshold → no edge event."""
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=3.4)]
    curr = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=4.3)]
    out = diff_snapshots(prev, curr)
    assert not any(c.type == "edge" for c in out)


def test_edge_event_threshold_boundary_inclusive() -> None:
    """At exactly the threshold the event fires (≥ per spec §5)."""
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=3.0)]
    curr = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=4.0)]
    out = diff_snapshots(prev, curr,
                         edge_threshold_pp=DEFAULT_EDGE_DELTA_PP)
    assert any(c.type == "edge" for c in out)


def test_edge_event_uses_negative_unicode_minus_for_drop() -> None:
    """Sign of the delta is rendered with a Unicode minus for visual parity
    with the funnel notes — keeps the dashboard consistent."""
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=5.5)]
    curr = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=3.4)]
    out = diff_snapshots(prev, curr)
    edge_evt = next(c for c in out if c.type == "edge")
    assert edge_evt.detail == "−2.1pp (5.5 → 3.4)"


# ── venue ─────────────────────────────────────────────────────────────

def test_venue_added_fires_venue_event() -> None:
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, venues=["polymarket"])]
    curr = [_row(mid, venues=["kalshi", "polymarket"])]
    out = diff_snapshots(prev, curr)
    v = next(c for c in out if c.type == "venue")
    assert v.detail == "+ kalshi"


def test_venue_removed_fires_venue_event() -> None:
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, venues=["kalshi", "polymarket"])]
    curr = [_row(mid, venues=["polymarket"])]
    out = diff_snapshots(prev, curr)
    v = next(c for c in out if c.type == "venue")
    assert v.detail == "− kalshi"


# ── copy ──────────────────────────────────────────────────────────────

def test_copy_hash_change_fires_copy() -> None:
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, copy_hash=_HASH_A)]
    curr = [_row(mid, copy_hash=_HASH_B)]
    out = diff_snapshots(prev, curr)
    assert any(c.type == "copy" for c in out)


# ── env override of edge threshold ───────────────────────────────────

def test_env_override_widens_edge_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_OPS_EDGE_DELTA_PP", "5.0")
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=1.0)]
    curr = [_row(mid, verdict_state="pick", pick_side="France", edge_pp=5.0)]
    # 4.0pp delta — under the new threshold of 5.0 → no edge event.
    out = diff_snapshots(prev, curr)
    assert not any(c.type == "edge" for c in out)


# ── Additive layering: a single fixture can carry many events ───────

def test_one_fixture_can_emit_multiple_events_per_run() -> None:
    """state change + venue change + copy change → all three fire."""
    mid = "fb-wc26-fra-mex-20260612"
    prev = [_row(mid, verdict_state="pass", venues=["polymarket"],
                 copy_hash=_HASH_A)]
    curr = [_row(mid, verdict_state="pick", pick_side="France",
                 edge_pp=3.2, venues=["kalshi", "polymarket"],
                 copy_hash=_HASH_B)]
    types = {c.type for c in diff_snapshots(prev, curr)}
    assert {"flip", "venue", "copy"}.issubset(types)


# ── Serialisation (the runner stores changes as dicts in RunReport) ─

def test_match_change_to_dict_uses_from_key() -> None:
    """The dataclass field is `from_` (Python keyword); the JSON key is
    `from` — verified so the dashboard contract matches the spec table."""
    c = MatchChange(type="flip", match_id="m", from_="pass", to="pick")
    d = c.to_dict()
    assert d == {"type": "flip", "match_id": "m", "from": "pass", "to": "pick"}
    assert "from_" not in d
