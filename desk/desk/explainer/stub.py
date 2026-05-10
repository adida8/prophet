"""Templated explainer — deterministic prose for every verdict state.

Replaces empty `copy.{title, summary, blurb}` strings with real
editorial copy that already passes the voice-rule post-check. PR 5
swaps these templates for three Haiku prompts that produce richer
prose; until then, the engine's output carries something a reader can
actually read.

Templates are short by design. The voice rules in
`desk/explainer/voice.py` reject any text that contains banned phrases,
exclamation marks, or emoji.
"""

from __future__ import annotations

from typing import TypedDict

from desk.explainer.voice import assert_voice_clean
from desk.publish.contract import Copy, VerdictState


class Inputs(TypedDict, total=False):
    state:           str    # "pick" / "pass" / "avoid"
    side:            str | None
    edge_pp:         float | None
    market_venue:    str | None
    price:           str | None
    team_a:          str
    team_b:          str
    competition:     str    # human label, e.g. "FIFA World Cup 2026"
    model_p_a:       float
    model_p_draw:    float
    model_p_b:       float
    market_p_a:      float
    market_p_draw:   float
    market_p_b:      float


def _pct(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p * 100:.0f}%"


def _name_for_side(side: str, *, team_a: str, team_b: str) -> str:
    if side == "draw":
        return "the draw"
    if side == team_a:
        return team_a
    if side == team_b:
        return team_b
    return side


def _verb_for_side(side: str, team_a: str, team_b: str) -> str:
    """Probabilistic verb — never assertive."""
    if side == "draw":
        return "to share the points"
    return "to win"


# ── Templates per state ───────────────────────────────────────────────

def _pick_copy(i: Inputs) -> Copy:
    side  = i["side"] or ""
    edge  = i["edge_pp"] or 0.0
    a, b  = i["team_a"], i["team_b"]
    side_name = _name_for_side(side, team_a=a, team_b=b)
    venue_label = (i.get("market_venue") or "the market").title()

    # Map side to the model + market probability we should reference.
    side_to_p = {a: ("a", "model_p_a", "market_p_a"),
                 b: ("b", "model_p_b", "market_p_b"),
                 "draw": ("draw", "model_p_draw", "market_p_draw")}
    _, m_key, mk_key = side_to_p.get(side, ("a", "model_p_a", "market_p_a"))
    model_p   = i.get(m_key, 0.0)        # type: ignore[arg-type]
    market_p  = i.get(mk_key, 0.0)       # type: ignore[arg-type]

    title = f"{a} v {b} · the model leans {side_name}"
    summary = (
        f"The model rates {side_name} at {_pct(model_p)}; "
        f"the market prices that side at {_pct(market_p)}. "
        f"The {edge:+.1f}pp gap is the basis for the Pick."
    )
    blurb = (
        f"{i.get('competition', 'This match')} pits {a} against {b}. "
        f"Our Elo prior, after host and altitude adjustments where they apply, "
        f"rates {side_name} {_verb_for_side(side, a, b)} at {_pct(model_p)}. "
        f"{venue_label} prices the same outcome at "
        f"{_pct(market_p)} — implying a model-versus-market gap of {edge:+.1f} percentage points. "
        f"That clears our 3pp threshold, so the verdict reads Pick. "
        f"Calibration history sits with the closing market across recent fixtures; "
        f"selection is the dimension this Pick is meant to add value on."
    )
    drivers = [
        f"Pre-tournament Elo gives {side_name} a stronger prior than the {venue_label} line implies.",
        f"The {edge:+.1f}pp gap clears our 3 percentage point threshold for a Pick.",
        f"Calibration sits with the closing market across recent fixtures, so selection is the lever.",
        f"Late-binding signals — form, confirmed XI, weather — re-evaluate closer to kickoff.",
    ]
    return Copy(title=title, summary=summary, blurb=blurb, drivers=drivers)


def _pass_copy(i: Inputs) -> Copy:
    a, b = i["team_a"], i["team_b"]
    title = f"{a} v {b} · model and market agree"
    summary = (
        f"Across all three sides the model and the market sit within a percentage point. "
        f"The state reads Pass — no actionable edge today."
    )
    blurb = (
        f"For {a} versus {b}, our Elo prior — adjusted for venue and altitude — "
        f"agrees with the closing line within a percentage point on every side. "
        f"Pass is the honest call when calibration is in agreement; we'll re-evaluate "
        f"as kickoff approaches and late-binding signals (form, weather, confirmed XI) "
        f"come in."
    )
    drivers = [
        "Model and market sit within a percentage point on every side.",
        "No structural disagreement to publish — both are pricing the same shape.",
        "Late-binding signals (form, weather, confirmed XI) re-evaluate near kickoff.",
    ]
    return Copy(title=title, summary=summary, blurb=blurb, drivers=drivers)


def _avoid_copy(i: Inputs) -> Copy:
    a, b = i["team_a"], i["team_b"]
    edge = i["edge_pp"] or 0.0
    title = f"{a} v {b} · every side priced inside the model"
    summary = (
        f"The market is shorter than our number on every side — most-negative edge is "
        f"{edge:+.1f}pp. The state reads Avoid: no edge to take, even on the side "
        f"closest to fair."
    )
    blurb = (
        f"In {a} versus {b}, our Elo prior comes in below the closing line on all three sides. "
        f"Avoid signals that the market has assigned more probability than the model on every "
        f"outcome. A reader's takeaway: this market doesn't carry an edge for the engine, "
        f"and we surface that distinctly from Pass so it isn't read as ambiguous."
    )
    drivers = [
        f"Every side priced shorter than our model — most-negative gap is {edge:+.1f}pp.",
        "No side priced attractively against the engine's Elo prior.",
        "Avoid is reported separately from Pass so it doesn't read as ambiguous.",
    ]
    return Copy(title=title, summary=summary, blurb=blurb, drivers=drivers)


# ── Public entry point ────────────────────────────────────────────────

def build_copy(i: Inputs) -> Copy:
    """Build editorial copy for one match. Voice-checked before return.

    Returns an empty `Copy` for unknown verdict states (defensive — the
    runner will write that as `{"title":"","summary":"","blurb":""}`,
    matching the previous behaviour).
    """
    state = (i.get("state") or "").lower()
    if state == VerdictState.PICK.value or state == VerdictState.PICK:
        c = _pick_copy(i)
    elif state == VerdictState.PASS.value or state == VerdictState.PASS:
        c = _pass_copy(i)
    elif state == VerdictState.AVOID.value or state == VerdictState.AVOID:
        c = _avoid_copy(i)
    else:
        return Copy()

    # Enforce voice rules. If any field fails, fall back to empty Copy
    # rather than ship a banned phrase to Faktor.
    fields_to_check = [c.title, c.summary, c.blurb, *c.drivers]
    for field in fields_to_check:
        try:
            assert_voice_clean(field)
        except Exception:                       # noqa: BLE001
            return Copy()
    return c
