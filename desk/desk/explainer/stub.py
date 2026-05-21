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

from desk.explainer.voice import assert_voice_clean, is_voice_clean
from desk.publish.contract import Citation, Copy, VerdictState

# Minimum distinct outlets behind a fixture before a press-chorus
# sentence is appended. Below this we stay silent rather than name a
# single source as "coverage" — that risks reading like an endorsement
# of one outlet's framing.
_CHORUS_MIN_OUTLETS = 2

# Outlet names listed in the count-shape sentence stop at this many.
# Beyond it we say "{first}, {second}, {third}, and N others".
_CHORUS_MAX_NAMED_OUTLETS = 3

# A quoted line in the consensus shape is truncated to this many chars
# (best-effort at word boundary) so the chorus stays a single sentence.
_CHORUS_QUOTE_MAX_CHARS = 140


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
    # News-signals editorial citations covering this fixture, in the same
    # shape they ship on the published contract. The templated blurb
    # appends one extra "press chorus" sentence when ≥ 2 citations land
    # — until PR 5 wires real Haiku prose around them.
    editorial_citations: list[Citation] | None


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


def _days_until(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = dt - datetime.now(tz=timezone.utc)
        return int(round(delta.total_seconds() / 86400))
    except Exception:
        return None


def _hour_of_day(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).hour
    except Exception:
        return None


def _weekday_name(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%A")
    except Exception:
        return None


def _kickoff_label(iso: str | None) -> str | None:
    """Return a short label like 'late-night UTC kickoff' or 'afternoon
    UTC kickoff' based on the hour. Used for editorial colour, not
    timezone-correct local time.
    """
    h = _hour_of_day(iso)
    if h is None:
        return None
    if h < 6:
        return "overnight UTC kickoff"
    if h < 12:
        return "morning UTC kickoff"
    if h < 17:
        return "afternoon UTC kickoff"
    if h < 21:
        return "evening UTC kickoff"
    return "late-night UTC kickoff"


def _edge_size_label(edge: float) -> str:
    if edge >= 15:
        return "one of the widest in the priced field"
    if edge >= 10:
        return "a wide disagreement by the engine's standards"
    if edge >= 5:
        return "a substantive gap"
    return "a narrow gap"


def _quality_phrase(src_a: str | None, src_b: str | None) -> str:
    """Plain-English line about how trustworthy the Elo numbers are."""
    a = _quality_label(src_a)
    b = _quality_label(src_b)
    if a == b == "live":
        return "Both Elo numbers are pulled live from the public Elo source."
    if a == b == "seed":
        return "Both Elo numbers are from the engine's frozen v1 seed, refreshed when the live ingest catches up."
    if "stub" in (a, b):
        return "One side resolves to a stub default until the live Elo ingest covers it; treat the prior on that side as low-confidence."
    return f"Elo source: {a} for one side, {b} for the other."


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
    """Long-form (~half-page) blurb drawing on Elo, the three-way model
    + market split, the bootstrap CI, venue + kickoff, and the Desk's
    methodology. Aims for ~400-550 words.

    Every paragraph picks from a pool of variants keyed by a hash of
    the match identity — so no two matches share boilerplate, but the
    same match always re-renders identically.
    """
    # ── Data ─────────────────────────────────────────────────────────
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
    venue_str = _venue_sentence(i)
    kickoff_str = _format_kickoff(i.get("kickoff_utc"))
    kickoff_iso = i.get("kickoff_utc")
    weekday = _weekday_name(kickoff_iso)
    days_out = _days_until(kickoff_iso)
    kickoff_lbl = _kickoff_label(kickoff_iso)
    is_home_side = side == a
    elo_higher = a if (elo_a or 0) > (elo_b or 0) else (b if (elo_b or 0) > (elo_a or 0) else None)
    elo_gap_int = int(round(abs((elo_a or 0) - (elo_b or 0)))) if elo_a and elo_b else None
    odds_str = _odds_translation(market_p)
    edge_label = _edge_size_label(edge)

    def pick(key: str, options: list[str]) -> str:
        return options[_variant_index(salt + "/" + key, len(options))]

    # ── §1. Fixture frame — six varied openers ───────────────────────
    when_clause = f" on {weekday}" if weekday else ""
    venue_clause = f" at {venue_str}" if venue_str else ""
    kickoff_extra = f", {kickoff_lbl}," if kickoff_lbl else ""

    para_fixture_options = [
        # A — opens on the fixture pairing
        f"{a} face {b}{when_clause}{venue_clause}{kickoff_extra} in {competition}. "
        f"This is one of the matches where the model's number disagrees with the "
        f"closing line on Polymarket — {edge_label} on the {side_name} side, +{edge:.1f}pp.",
        # B — opens on the edge
        f"A {edge:+.1f}pp gap on the {side_name} side. {a} v {b}{venue_clause} in {competition} "
        f"is the match. The model has {side_name} stronger than the market does — that's "
        f"the reason this fires as a Pick rather than a Pass.",
        # C — opens on the competition / when
        f"{competition}{when_clause}{kickoff_extra} brings {a} and {b} together"
        f"{venue_clause}. The Desk's read disagrees with the market on the "
        f"{side_name} side, by {edge:+.1f}pp — and that disagreement is the Pick.",
        # D — opens on the team that's the Pick
        f"The model fancies {side_name} more than the market does in this {competition} "
        f"fixture against {a if side_name == b else b}{venue_clause}. {edge:+.1f}pp is "
        f"{edge_label}; that's what fires this as a Pick on the {_side_label(side, a=a, b=b)} side.",
        # E — opens on the timing / lead-up
        f"{kickoff_str + '.' if kickoff_str else f'{competition}.'} {a} and {b} on the card"
        f"{venue_clause}. On the {side_name} side, the engine's number sits {edge:+.1f}pp "
        f"clear of the market — {edge_label} this far out from kickoff.",
        # F — opens on the disagreement
        f"This is a Pick. {a} v {b} in {competition}{when_clause}, and the model and the "
        f"market disagree on the {side_name} side by {edge:+.1f}pp{venue_clause and ' at ' + venue_str or ''}. "
        f"That's the gap the verdict rests on.",
    ]
    para_fixture = pick("§1", para_fixture_options)

    # ── §2. Elo + adjustments — five framings ────────────────────────
    elo_summary = ""
    if elo_a is not None and elo_b is not None:
        if elo_gap_int and elo_higher:
            elo_summary_options = [
                f"On Elo, {elo_higher} comes in {elo_gap_int} points ahead — {a} at "
                f"{int(round(elo_a))}, {b} at {int(round(elo_b))}.",
                f"The Elo prior reads {a} {int(round(elo_a))} vs {b} {int(round(elo_b))}: "
                f"{elo_gap_int} points in favour of {elo_higher}, which is a meaningful but "
                f"not decisive prior.",
                f"Elo numbers going in: {a} {int(round(elo_a))}, {b} {int(round(elo_b))}. "
                f"That's a {elo_gap_int}-point lead for {elo_higher} — closer than a casual "
                f"reader of the market price might assume.",
                f"Public Elo rates {elo_higher} {elo_gap_int} points higher than the other "
                f"side ({a} {int(round(elo_a))}, {b} {int(round(elo_b))}). The match "
                f"model's logistic translates that Elo gap directly into a win-probability.",
            ]
        else:
            elo_summary_options = [
                f"Elo has the two sides level: {a} on {int(round(elo_a))}, {b} on "
                f"{int(round(elo_b))}. With the prior even, the market price carries the "
                f"weight of the disagreement.",
                f"On Elo, this is a coin flip — {int(round(elo_a))} apiece for {a} and {b}. "
                f"A model-vs-market gap of {edge:+.1f}pp on a level prior is unusual.",
            ]
        elo_summary = pick("§2-elo", elo_summary_options) + " " + _quality_phrase(src_a, src_b)
    else:
        elo_summary = (
            "The model starts from a public Elo prior on both sides, refreshed against "
            "international and club Elo feeds."
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
            adj_options = [
                f" Adjustments fire on this fixture — {' and '.join(adj_bits)} — folding "
                f"host-country, home-ground, and altitude effects into the prior where they "
                f"apply.",
                f" Pre-match adjustments lift the prior by {' and '.join(adj_bits)}; the "
                f"engine carries a small set of physically-motivated bonuses (host, home, "
                f"altitude) and reads them off the venue.",
            ]
            adjustments_line = pick("§2-adj", adj_options)
        else:
            adj_options = [
                " No host, home-ground, or altitude adjustments apply here; the prior reads "
                "straight from Elo.",
                " The adjustment layer is quiet on this fixture — no host bonus, no home-"
                "ground correction, no altitude folding in. The Elo numbers above are what "
                "the model uses.",
            ]
            adjustments_line = pick("§2-noadj", adj_options)
    else:
        adjustments_line = ""
    para_elo = elo_summary + adjustments_line

    # ── §3. Model three-way split — four framings ────────────────────
    model_split = _three_way_sentence(
        a=a, b=b, p_a=p_a, p_d=p_d, p_b=p_b_, label="Three-way split from the model"
    )
    para_model_options = [
        f"{model_split} The {_side_label(side, a=a, b=b)} side reads {_pct(model_p)} on this "
        f"distribution — the model's central case for {side_name}.",
        f"{model_split} The Desk's three-way distribution is calibrated against the W/D/L "
        f"resolution Polymarket and Kalshi settle on, not against the exact scoreline. "
        f"{side_name} sits at {_pct(model_p)} of the mass.",
        f"{model_split} Draw share decays with Elo gap; on a fixture this evenly matched "
        f"the draw carries more probability than a casual reader might guess. {side_name} "
        f"on the win side reads {_pct(model_p)}.",
        f"{model_split} Each number is a probability over the full range of plausible "
        f"in-form, no-injury, ninety-minute scenarios — not a prediction of a scoreline.",
    ]
    para_model = pick("§3", para_model_options)

    # ── §4. Market three-way split + odds — four framings ────────────
    market_split = _three_way_sentence(
        a=a, b=b, p_a=mp_a, p_d=mp_d, p_b=mp_b, label=f"On the same three-way, {venue_label}"
    )
    odds_phrase = f", which prices out at American odds of {odds_str}" if odds_str else ""
    para_market_options = [
        f"{market_split} On the {side_name} side specifically the market reads {_pct(market_p)}"
        f"{odds_phrase}. Compared against the model's {_pct(model_p)}, that's the +{edge:.1f}pp "
        f"gap the Pick rests on.",
        f"{market_split} {venue_label} has {side_name} at {_pct(market_p)}{odds_phrase}; the "
        f"model has the same side at {_pct(model_p)}. The {edge:+.1f}pp gap across them is "
        f"the disagreement we're surfacing.",
        f"{market_split} Reading those three numbers as a probability distribution, the "
        f"market's view is internally consistent. The disagreement with the model is "
        f"concentrated on the {side_name} side — {_pct(market_p)} on the market, "
        f"{_pct(model_p)} on the engine, a {edge:+.1f}pp gap.",
        f"{market_split} The {side_name} side trades at {_pct(market_p)} on Polymarket"
        f"{odds_phrase}. That's where the engine differs: our number reads {_pct(model_p)}, "
        f"{edge:+.1f}pp wider.",
    ]
    para_market = pick("§4", para_market_options)

    # ── §5. The discipline — three framings ──────────────────────────
    if lower_p is not None and lower_p > 0:
        lower_gap = (lower_p - market_p) * 100
        discipline_options = [
            f"Pick gate is a lower-bound check, not the point estimate. A 100-sample "
            f"bootstrap perturbs the Elo prior (±20), the host bonus (±15), and the altitude "
            f"bonus (±10), then reads the 5th-percentile probability back out. On the "
            f"{side_name} side that lower bound is {_pct(lower_p)} — {lower_gap:+.1f}pp clear "
            f"of the market's {_pct(market_p)}, comfortably past our +3pp threshold.",
            f"The +3pp Pick threshold isn't on the point estimate, it's on the 5th-percentile "
            f"from a 100-sample bootstrap of the Elo prior plus bonuses. On {side_name}, that "
            f"haircut lands the model at {_pct(lower_p)}; the market is at {_pct(market_p)}. "
            f"Even on the conservative reading, the gap is {lower_gap:+.1f}pp.",
            f"Bootstrap discipline matters most on the longshots — wide bands on small "
            f"point estimates collapse the Pick rate fast. On {side_name} the lower bound "
            f"is {_pct(lower_p)}, which keeps the lower-bound gap at {lower_gap:+.1f}pp "
            f"against the market — past +3pp, so the Pick clears.",
        ]
        bootstrap_line = pick("§5-boot", discipline_options)
    else:
        bootstrap_line = (
            "Our Pick gate uses the 5th-percentile of a 100-sample bootstrap of the Elo "
            "prior plus the bonus adjustments. The discipline keeps the engine from over-"
            "firing on point-estimate noise; a Pick fires only when the lower-bound gap is "
            "wide enough to survive the haircut."
        )

    posture_options = [
        " The Desk's posture is that calibration sits with the closing market across recent "
        "fixtures — we're not claiming the market is generally wrong, only that this side, "
        "on this fixture, looks mispriced. Selection is the dimension this verdict adds value on.",
        " We're not arguing the market is broadly wrong; the closing line and the model are "
        "in approximate agreement across recent fixtures by Brier score. The claim is "
        "narrower: this side specifically reads mispriced.",
        " Calibration tracks the closing market on the bulk sample; selection — picking the "
        "single side where the gap is wide — is where the engine's edge has to come from. "
        "This verdict is a selection call on the {side_name} side.".format(side_name=side_name),
    ]
    para_discipline = bootstrap_line + pick("§5-posture", posture_options)

    # ── §6. Late-binding + close — vary by time-to-kickoff ───────────
    cadence_phrase: str
    if days_out is None:
        cadence_phrase = (
            "The model refreshes weekly outside T-5d of kickoff, daily inside T-5d, and "
            "hourly inside T-24h."
        )
    elif days_out > 30:
        cadence_phrase = (
            f"With kickoff roughly {days_out} days out, the model is on the weekly refresh "
            f"cadence; we'll move to daily once we cross the T-5d window."
        )
    elif days_out > 5:
        cadence_phrase = (
            f"With kickoff {days_out} days out, we're still on weekly refresh; the daily "
            f"cadence picks up inside T-5d."
        )
    elif days_out > 1:
        cadence_phrase = (
            f"Inside T-5d now — {days_out} days to kickoff — so refresh is daily. "
            f"The model will move to hourly inside T-24h."
        )
    elif days_out >= 0:
        cadence_phrase = (
            f"Inside T-24h — hourly refresh active. Late-binding signals re-enter the "
            f"prior on every cycle until kickoff."
        )
    else:
        cadence_phrase = (
            f"Match has kicked off; the published number is the last pre-match read."
        )

    para_close_options = [
        f"This number will move. Confirmed starting elevens, injuries, weather at the venue, "
        f"and suspensions carried in from previous fixtures all re-enter the prior on the "
        f"late-binding cadence. {cadence_phrase} The Pick can flip to a Pass if news moves "
        f"enough of the prior. The Desk does not tip and does not recommend a trade — the "
        f"model price, the market price, and the gap across them are what's on the page.",
        f"The number above is the most recent read; it isn't frozen. {cadence_phrase} Injury "
        f"news, the actual XI, and weather conditions at kickoff all feed back into the prior "
        f"when they land. We republish on every refresh. The Desk surfaces edge; what to do "
        f"with that surface is a reader's call.",
        f"News will move the prior. {cadence_phrase} On a Pick this wide, it would take "
        f"material news — a missing star, a tournament dropout, a venue change — to collapse "
        f"the gap below the +3pp threshold; on the narrower side of the field, a single "
        f"refresh can flip Pick to Pass. Either way, the Desk re-publishes after each "
        f"refresh and does not recommend a trade.",
    ]
    para_close = pick("§6", para_close_options)

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
    blurb = _with_chorus(blurb, i.get("editorial_citations"))
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
    blurb = _with_chorus(blurb, i.get("editorial_citations"))
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
    blurb = _with_chorus(blurb, i.get("editorial_citations"))
    drivers = [
        f"Every side priced shorter than our model — most-negative gap is {edge:+.1f}pp.",
        "No side priced attractively against the engine's Elo prior.",
        "Avoid is reported separately from Pass so it doesn't read as ambiguous.",
    ]
    return Copy(title=title, summary=summary, blurb=blurb, drivers=drivers)


# ── Press chorus (news-signals stopgap until PR 5 / Haiku) ───────────

def _truncate_quote(quote: str, *, limit: int = _CHORUS_QUOTE_MAX_CHARS) -> str:
    """Trim a quoted line to roughly one sentence's worth.

    Tries to break on a word boundary before `limit`, falling back to a
    hard cut. Trailing ellipsis "…" is appended only when we actually
    truncated, so short quotes ride through verbatim.
    """
    q = (quote or "").strip()
    if len(q) <= limit:
        return q
    head = q[: limit].rstrip()
    sp = head.rfind(" ")
    if sp >= limit - 30:                # only honour space if reasonably close to the limit
        head = head[: sp].rstrip()
    return head.rstrip(",.;:") + "…"


def _distinct_outlets(cites: list[Citation]) -> list[str]:
    """Outlet display names in citation order, deduped, falsy stripped."""
    seen: set[str] = set()
    out: list[str] = []
    for c in cites:
        name = (c.outlet or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _press_chorus(cites: list[Citation] | None) -> str | None:
    """One-sentence "press chorus" appended to a blurb when news
    citations are present. Returns None when nothing safe to say.

    Two shapes, picked by what survives the voice filter:

      1. **Consensus shape** — when the top-reliability citation carries
         a voice-clean quote, mention it: `Coverage this week converged
         on the fixture; {Outlet} carried the line "{quote}".`
      2. **Count shape** — when no clean quote survives but ≥ 2 distinct
         outlets remain, list them: `Recent coverage from {N} outlets
         ({first}, {second}, …) sits behind this verdict; full sources
         below.`

    All output is voice-checked one final time before return. A failing
    final check returns None — the blurb body still ships unchanged.
    """
    cites = cites or []
    if len(cites) < _CHORUS_MIN_OUTLETS:
        return None

    # Pre-filter: drop citations whose quote would fail the voice gate.
    # Outlet name + URL stay attached; the quote isn't usable in prose.
    safe_quoted = [c for c in cites if c.quote and is_voice_clean(c.quote)]
    distinct = _distinct_outlets(cites)
    if len(distinct) < _CHORUS_MIN_OUTLETS:
        return None

    candidate: str | None = None

    # Consensus shape: prefer a real quote if one survived the filter.
    # `editorial.build_citations` already sorts by source reliability
    # desc, so the first surviving quote is the best one to feature.
    if safe_quoted:
        c = safe_quoted[0]
        quote = _truncate_quote(c.quote).strip().rstrip('"').rstrip("'")
        candidate = (
            f'Coverage converged on the fixture this week; '
            f'{c.outlet.strip()} carried the line "{quote}".'
        )

    # Count shape: fall back when no usable quote, but ≥ N outlets carry it.
    if candidate is None or not is_voice_clean(candidate):
        names = distinct[:_CHORUS_MAX_NAMED_OUTLETS]
        rest  = len(distinct) - len(names)
        listed = ", ".join(names)
        if rest > 0:
            listed += f", and {rest} other{'s' if rest != 1 else ''}"
        candidate = (
            f'Recent coverage from {len(distinct)} outlets '
            f'({listed}) sits behind this verdict; full sources below.'
        )

    return candidate if is_voice_clean(candidate) else None


def _with_chorus(blurb: str, cites: list[Citation] | None) -> str:
    """Append the press chorus to a blurb when one is available."""
    chorus = _press_chorus(cites)
    if not chorus:
        return blurb
    return f"{blurb} {chorus}".strip()


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
