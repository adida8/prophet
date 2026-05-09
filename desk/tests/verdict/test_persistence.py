"""Phase A.3 — multi-window Pick persistence tests."""

from __future__ import annotations

from desk.verdict.persistence import WindowVerdict, apply_persistence_rule


def _pick(side: str) -> WindowVerdict:
    return WindowVerdict(state="pick", side=side)


PASS_VERDICT  = WindowVerdict(state="pass")
AVOID_VERDICT = WindowVerdict(state="avoid")


# ── No-op cases ────────────────────────────────────────────────────────

def test_pass_passes_through_unchanged() -> None:
    """Pass verdicts aren't subject to the persistence rule."""
    res = apply_persistence_rule(PASS_VERDICT, prior_verdicts={})
    assert res.persistent is True
    assert res.reason == "not_a_pick"


def test_avoid_passes_through_unchanged() -> None:
    res = apply_persistence_rule(AVOID_VERDICT, prior_verdicts={})
    assert res.persistent is True
    assert res.reason == "not_a_pick"


# ── Persistent picks ───────────────────────────────────────────────────

def test_three_window_picks_on_same_side_persist() -> None:
    res = apply_persistence_rule(
        _pick("France"),
        prior_verdicts={"T-5": _pick("France"), "T-1h": _pick("France")},
    )
    assert res.persistent is True
    assert res.reason == "ok"


def test_two_window_picks_persist_when_t5_missing() -> None:
    """Spec: 'or at least the latest two if T−5 wasn't computed'."""
    res = apply_persistence_rule(
        _pick("Brazil"),
        prior_verdicts={"T-1h": _pick("Brazil")},
    )
    assert res.persistent is True


# ── Non-persistent picks → downgrade to Pass ──────────────────────────

def test_pick_at_ko_only_is_rejected() -> None:
    """No prior window agreed → not persistent → Pass."""
    res = apply_persistence_rule(_pick("France"), prior_verdicts={})
    assert res.persistent is False
    assert res.reason == "not_persistent"


def test_pick_with_t1h_pass_is_rejected() -> None:
    """T-1h was Pass; the Pick first appeared at KO → not persistent."""
    res = apply_persistence_rule(
        _pick("France"),
        prior_verdicts={"T-5": _pick("France"), "T-1h": PASS_VERDICT},
    )
    assert res.persistent is False
    assert res.reason == "not_persistent"


def test_pick_with_disagreeing_side_is_rejected() -> None:
    """T-1h Picked the other side → the engine flipped → not persistent."""
    res = apply_persistence_rule(
        _pick("France"),
        prior_verdicts={"T-5": _pick("France"), "T-1h": _pick("Mexico")},
    )
    assert res.persistent is False


def test_t5_disagreement_with_t1h_and_ko_is_rejected() -> None:
    """T-1h and KO Pick France, but T-5 Picked Mexico — 'all three'
    rule says this is not persistent."""
    res = apply_persistence_rule(
        _pick("France"),
        prior_verdicts={"T-5": _pick("Mexico"), "T-1h": _pick("France")},
    )
    assert res.persistent is False


def test_pick_with_only_t5_match_is_rejected() -> None:
    """T-5 Picked France, T-1h not computed; the latest-two rule needs
    T-1h agreement, not just T-5."""
    res = apply_persistence_rule(
        _pick("France"),
        prior_verdicts={"T-5": _pick("France")},
    )
    assert res.persistent is False
