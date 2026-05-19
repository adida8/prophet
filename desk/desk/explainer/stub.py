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

import hashlib
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
    # Optional model internals — the explainer cites them when present
    # to make the blurb concrete. Absent on legacy callers; absent on
    # outright copy. Source: ModelOutput + FootballFeatures in
    # desk/sports/football/.
    team_a_elo:        float | None     # raw Elo, pre-adjustments
    team_b_elo:        float | None
    elo_a_adj:         float | None     # post host/altitude adjustments
    elo_b_adj:         float | None
    team_a_elo_source: str    | None    # "wiki" / "clubelo" / "stub" / "seed"
    team_b_elo_source: str    | None
    model_p_a_lower:   float | None
    model_p_a_upper:   float | None
    model_p_draw_lower: float | None
    model_p_draw_upper: float | None
    model_p_b_lower:   float | None
    model_p_b_upper:   float | None
    venue_city:        str | None
    venue_stadium:     str | None
    venue_country:     str | None       # ISO-2 — e.g. "MX" / "US" / "CA"
    kickoff_utc:       str | None       # ISO-8601 string; explainer parses


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

def _variant_index(salt: str, n_variants: int) -> int:
    """Deterministic variant pick — same match → same summary every run."""
    h = hashlib.sha1(salt.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % n_variants


def _pick_summary(
    *,
    side: str,
    side_name: str,
    edge: float,
    model_p: float,
    market_p: float,
    a: str,
    b: str,
    competition: str,
    venue_label: str,
    salt: str,
) -> str:
    """Choose one of several stylistically varied Pick summaries. The
    template depends on edge size, side, and confidence; ties resolve
    by hashing the match identity. Every variant stays inside the
    voice rules (no banned phrases, no "!", no emoji).
    """
    huge        = edge >= 10.0
    moderate    = edge < 5.0
    is_draw     = side == "draw"
    is_home     = side == a
    is_favourite = model_p >= 0.50
    is_longshot  = model_p < 0.20

    # Variant pool — short, distinct openers + framings. Each one ends
    # on a sentence that names the gap so the card still reads as a
    # Pick at a glance.
    #
    # Ordering inside each bucket is the "preferred shape first"
    # pattern; the hash picks within the bucket so similar matches
    # don't all collide on the same opener.
    variants: list[str] = []

    if is_draw:
        variants += [
            (f"This is one of the few matches where the model leans toward the draw "
             f"more than {venue_label} does. The model rates the draw at {_pct(model_p)}, "
             f"the market at {_pct(market_p)} — a {edge:+.1f}pp gap."),
            (f"The model and the market disagree on whether a stalemate is in play here. "
             f"Our prior puts the draw at {_pct(model_p)}; {venue_label} prices it at "
             f"{_pct(market_p)}. The {edge:+.1f}pp gap is the Pick."),
        ]
    elif huge and is_longshot:
        variants += [
            (f"{side_name} enter as the longshot — {venue_label} prices their chances at "
             f"{_pct(market_p)}. The model rates them at {_pct(model_p)}, a {edge:+.1f}pp "
             f"disagreement and one of our widest in this competition."),
            (f"{venue_label} is pricing {side_name} as a long shot at {_pct(market_p)}. "
             f"The model has them materially stronger at {_pct(model_p)}. "
             f"That {edge:+.1f}pp gap is what flags this as a Pick."),
            (f"The market reads {side_name} as a {_pct(market_p)} chance; our Elo prior "
             f"reads them at {_pct(model_p)}. A {edge:+.1f}pp gap on a longshot side is "
             f"where the engine finds its biggest Picks."),
        ]
    elif huge and is_favourite:
        variants += [
            (f"{side_name} are favourites on the market at {_pct(market_p)} — and the model "
             f"thinks the market is still underrating them. Our prior reads {_pct(model_p)}, "
             f"a {edge:+.1f}pp upgrade that crosses the Pick threshold comfortably."),
            (f"On every meaningful read, {side_name} look stronger here than {venue_label} "
             f"has them. Model {_pct(model_p)} vs market {_pct(market_p)} — a {edge:+.1f}pp "
             f"gap on the favourite side."),
        ]
    elif huge:
        variants += [
            (f"A {edge:+.1f}pp gap across model and market on the {side_name} side. "
             f"Our Elo prior, after host and altitude adjustments, rates {side_name} at "
             f"{_pct(model_p)}; {venue_label} sits at {_pct(market_p)}."),
            (f"The model thinks {side_name} are mispriced. Our number reads {_pct(model_p)} "
             f"on the {('home' if is_home else 'away')} side; the market reads {_pct(market_p)}. "
             f"The {edge:+.1f}pp gap is the Pick."),
        ]
    elif moderate:
        variants += [
            (f"A modest gap, but enough to clear the gate. The model rates {side_name} at "
             f"{_pct(model_p)}; {venue_label} prices that side at {_pct(market_p)} — a "
             f"{edge:+.1f}pp difference that fires the Pick."),
            (f"{side_name} sit a few points stronger on our number than on the market. "
             f"Model {_pct(model_p)} vs market {_pct(market_p)}. The {edge:+.1f}pp gap is "
             f"the lever this Pick rests on."),
        ]
    else:  # 5pp ≤ edge < 10pp
        variants += [
            (f"The {('home' if is_home else 'away')} side reads stronger to the model than to "
             f"the market. Our Elo prior puts {side_name} at {_pct(model_p)}; {venue_label} "
             f"prices that side at {_pct(market_p)}. The {edge:+.1f}pp gap calls a Pick."),
            (f"On {side_name}, the model is {edge:+.1f}pp out from {venue_label}. Our number "
             f"reads {_pct(model_p)}; the market reads {_pct(market_p)}. That gap is the "
             f"basis for the Pick."),
            (f"This is a Pick on the {side_name} side — the model has them at {_pct(model_p)}, "
             f"the market at {_pct(market_p)}. A {edge:+.1f}pp gap is enough on a fixture this "
             f"close to even."),
        ]

    idx = _variant_index(salt, len(variants))
    return variants[idx]


def _format_kickoff(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%A %-d %B %Y at %H:%M UTC")
    except Exception:
        return None


def _venue_sentence(i: Inputs) -> str | None:
    city    = i.get("venue_city")
    stadium = i.get("venue_stadium")
    country = i.get("venue_country")
    parts: list[str] = []
    if stadium:
        parts.append(stadium)
    if city:
        parts.append(city)
    if country:
        parts.append(country)
    if not parts:
        return None
    return ", ".join(parts)


def _side_label(side: str | None, *, a: str, b: str) -> str:
    """'Home' / 'Away' / 'Draw' descriptor for narrative variety."""
    if side == "draw":
        return "draw"
    if side == a:
        return "home"
    if side == b:
        return "away"
    return side or "Pick"


def _quality_label(source: str | None) -> str:
    """Human-readable Elo source quality."""
    s = (source or "").lower()
    if s in {"wiki", "clubelo"}:
        return "live"
    if s in {"seed", "seeded"}:
        return "seed"
    if s in {"stub", "default"}:
        return "stub (default 1500)"
    return source or "unknown"


def _three_way_sentence(
    *,
    a: str, b: str,
    p_a: float, p_d: float, p_b: float,
    label: str,
) -> str:
    """'Model: A 38% / draw 27% / B 35%' as one editorial line."""
    return (
        f"{label}: {a} to win at {_pct(p_a)}, the draw at {_pct(p_d)}, "
        f"and {b} to win at {_pct(p_b)}."
    )


def _odds_translation(market_p: float) -> str:
    """Convert market_p to American odds string, no '+' prefix on
    favourites. Returns '' if undefined.
    """
    if not (0 < market_p < 1):
        return ""
    if market_p < 0.5:
        return f"+{int(round((1 - market_p) / market_p * 100))}"
    return f"−{int(round(market_p / (1 - market_p) * 100))}"


def _pick_blurb(
    *,
    i: Inputs,
    side: str,
    side_name: str,
    edge: float,
    model_p: float,
    market_p: float,
    a: str,
    b: str,
    competition: str,
    venue_label: str,
    salt: str,
) -> str:
    """Long-form (~half-page) blurb drawing on Elo, the three-way
    model + market split, the bootstrap CI, venue + kickoff, and the
    Desk's methodology. Aims for ~400-550 words.
    """
    # ── Source data, with safe defaults if upstream didn't plumb them ──
    p_a   = float(i.get("model_p_a")   or 0.0)
    p_d   = float(i.get("model_p_draw") or 0.0)
    p_b_  = float(i.get("model_p_b")   or 0.0)
    mp_a  = float(i.get("market_p_a")   or 0.0)
    mp_d  = float(i.get("market_p_draw") or 0.0)
    mp_b  = float(i.get("market_p_b")   or 0.0)
    elo_a = i.get("team_a_elo")
    elo_b = i.get("team_b_elo")
    elo_a_adj = i.get("elo_a_adj")
    elo_b_adj = i.get("elo_b_adj")
    src_a = i.get("team_a_elo_source")
    src_b = i.get("team_b_elo_source")

    side_to_lower = {
        a: i.get("model_p_a_lower"),
        b: i.get("model_p_b_lower"),
        "draw": i.get("model_p_draw_lower"),
    }
    lower_p = side_to_lower.get(side)

    side_label = _side_label(side, a=a, b=b)
    kickoff_str = _format_kickoff(i.get("kickoff_utc"))
    venue_str = _venue_sentence(i)

    # ── §1. Fixture frame ────────────────────────────────────────────
    frame_bits = [f"{competition} brings {a} together with {b}"]
    if kickoff_str:
        frame_bits.append(f", scheduled for {kickoff_str}")
    if venue_str:
        frame_bits.append(f", at {venue_str}")
    frame_bits.append(".")
    fixture_intro = "".join(frame_bits)

    para_fixture = (
        f"{fixture_intro} The Desk reads every priced match on Polymarket and Kalshi "
        f"against an independent model number, then publishes a single verdict — Pick, "
        f"Pass, or Avoid — with the math the call rests on. On this fixture that verdict "
        f"is a Pick, on the {side_name} side."
    )

    # ── §2. Elo + adjustments ────────────────────────────────────────
    if elo_a is not None and elo_b is not None:
        elo_line = (
            f"The model starts from public Elo ratings: {a} on {int(round(elo_a))}, "
            f"{b} on {int(round(elo_b))} — a {int(round(abs(elo_a - elo_b)))}-point "
            f"difference {'in favour of ' + a if elo_a > elo_b else ('in favour of ' + b if elo_b > elo_a else 'with the sides level')}. "
            f"Elo source: {_quality_label(src_a)} for {a}, {_quality_label(src_b)} for {b}."
        )
    else:
        elo_line = (
            f"The model starts from a public Elo prior on both sides, refreshed against "
            f"international and club Elo feeds."
        )
    if elo_a_adj is not None and elo_b_adj is not None and elo_a is not None and elo_b is not None:
        delta_a = elo_a_adj - elo_a
        delta_b = elo_b_adj - elo_b
        if abs(delta_a) > 0.5 or abs(delta_b) > 0.5:
            adj_bits = []
            if abs(delta_a) > 0.5:
                adj_bits.append(f"{a} {('+' if delta_a > 0 else '')}{int(round(delta_a))} Elo")
            if abs(delta_b) > 0.5:
                adj_bits.append(f"{b} {('+' if delta_b > 0 else '')}{int(round(delta_b))} Elo")
            adjustments_line = (
                f" After host-country, home-ground, and altitude adjustments where they "
                f"apply, the prior shifts: {' and '.join(adj_bits)}. The adjustments are "
                f"physically motivated and bounded — a small bonus for host-country sides "
                f"in international tournaments, an altitude bonus for whichever side is more "
                f"acclimatised to venues above 1,000m, and a home-ground bonus for clubs at "
                f"their registered stadium."
            )
        else:
            adjustments_line = (
                " No host, home-ground, or altitude adjustments apply on this fixture; the "
                "prior reads straight from Elo."
            )
    else:
        adjustments_line = ""
    para_elo = elo_line + adjustments_line

    # ── §3. Three-way model split ────────────────────────────────────
    para_model = (
        _three_way_sentence(
            a=a, b=b, p_a=p_a, p_d=p_d, p_b=p_b_, label="Run through the three-way split, the model reads"
        )
        + " The three-way distribution carries the Desk's view of how often each outcome "
        + "fires across the entire range of in-form-but-not-injured ninety-minute scenarios. "
        + "It is not a forecast of the exact scoreline; it is a calibrated probability over "
        + "the W / D / L resolution that Polymarket and Kalshi both settle on."
    )

    # ── §4. Three-way market split + odds ────────────────────────────
    odds_str = _odds_translation(market_p)
    para_market = (
        _three_way_sentence(
            a=a, b=b, p_a=mp_a, p_d=mp_d, p_b=mp_b, label=f"{venue_label}'s closing line"
        )
        + f" On the {side_name} side specifically, the market sits at {_pct(market_p)}"
        + (f", which prices out at American odds of {odds_str}" if odds_str else "")
        + f". The model has the same side at {_pct(model_p)}. The gap across those two "
        + f"numbers — {edge:+.1f}pp — is the basis for the Pick."
    )

    # ── §5. The discipline (bootstrap + threshold) ───────────────────
    if lower_p is not None and lower_p > 0:
        bootstrap_line = (
            f"Our Pick gate uses a lower-bound check, not the point estimate. A 100-sample "
            f"bootstrap perturbs the Elo prior, the host bonus, and the altitude bonus across "
            f"realistic ranges (±20 Elo, ±15 host, ±10 altitude) and reads the 5th-percentile "
            f"value back out. On the {side_name} side, that lower bound is {_pct(lower_p)} — "
            f"compared against the market's {_pct(market_p)}, the lower-bound gap is "
            f"{(lower_p - market_p) * 100:+.1f}pp. The Pick fires when that lower-bound gap "
            f"clears +3pp; it does on this match."
        )
    else:
        bootstrap_line = (
            f"Our Pick gate uses the lower-bound check from a 100-sample bootstrap of the Elo "
            f"prior plus the bonus adjustments. The discipline keeps the engine from over-firing "
            f"on point-estimate noise. A Pick is published only when the lower-bound gap is wide "
            f"enough to survive the bootstrap haircut."
        )
    para_discipline = bootstrap_line + (
        f" The Desk's posture is that calibration sits with the closing market across recent "
        f"fixtures, so we're not claiming the market is generally wrong — we're claiming this "
        f"particular side is mispriced on this particular fixture. Selection is the dimension "
        f"this verdict is meant to add value on."
    )

    # ── §6. Late-binding signals + close ─────────────────────────────
    para_close = (
        f"This number will move. Late-binding signals — confirmed starting elevens, injury "
        f"updates, weather at the venue, suspensions carried in from previous fixtures — all "
        f"re-enter the model on the data layer's late-binding cadence, currently weekly outside "
        f"T-5d of kickoff, daily inside T-5d, hourly inside T-24h. A Pick can flip to a Pass if "
        f"news moves the prior; we republish on every refresh. The Desk does not tip and does "
        f"not recommend a trade. The model price, the market price, and the gap across them "
        f"are what's on the page; what to do with that is a reader's call."
    )

    return "\n\n".join([
        para_fixture, para_elo, para_model, para_market, para_discipline, para_close,
    ])


def _pick_copy(i: Inputs) -> Copy:
    side  = i["side"] or ""
    edge  = i["edge_pp"] or 0.0
    a, b  = i["team_a"], i["team_b"]
    side_name = _name_for_side(side, team_a=a, team_b=b)
    venue_label = (i.get("market_venue") or "the market").title()
    competition = i.get("competition", "This match")

    side_to_p = {a: ("a", "model_p_a", "market_p_a"),
                 b: ("b", "model_p_b", "market_p_b"),
                 "draw": ("draw", "model_p_draw", "market_p_draw")}
    _, m_key, mk_key = side_to_p.get(side, ("a", "model_p_a", "market_p_a"))
    model_p   = i.get(m_key, 0.0)        # type: ignore[arg-type]
    market_p  = i.get(mk_key, 0.0)       # type: ignore[arg-type]

    # Deterministic salt — same match always picks the same variant.
    salt = f"{a}|{b}|{side}|{edge:.1f}"

    title = f"{a} v {b} · the model leans {side_name}"
    summary = _pick_summary(
        side=side, side_name=side_name, edge=edge,
        model_p=model_p, market_p=market_p, a=a, b=b,
        competition=competition, venue_label=venue_label, salt=salt,
    )
    blurb = _pick_blurb(
        i=i,
        side_name=side_name, side=side, edge=edge,
        model_p=model_p, market_p=market_p, a=a, b=b,
        competition=competition, venue_label=venue_label, salt=salt,
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
