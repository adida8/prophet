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
    # Team-news payloads (injuries + lineup status) per side. Threaded
    # onto Inputs so the Haiku blurb writer can address availability
    # explicitly per the team-news spec. Stub ignores these — they only
    # drive Haiku's prompt + post-checks. `object` typing keeps the
    # forward-ref free for the stub side, which never imports the
    # football-package payload type.
    team_a_news: object | None
    team_b_news: object | None
    # Cross-venue best-place-to-act (ADR 0004). When present, the
    # picked-side driver list adds one line naming the cheapest venue
    # + the effective implied % paid there. None when the cross-venue
    # flag is off OR the picked venue is Polymarket (no new info to
    # surface — `venue_label` already names it).
    best_venue_label:      str  | None
    best_venue_true_price: float | None


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
        f"{model_split} The Desk publishes a three-way read against the same W/D/L "
        f"resolution Polymarket and Kalshi settle on — not a scoreline guess. {side_name} "
        f"sits at {_pct(model_p)} of the mass.",
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
        f" The claim is narrow: on this fixture, on this side, the price is below what the "
        f"underlying read supports. We don't argue the market is broadly wrong — across the "
        f"priced field the model and the line agree more often than they disagree. We surface "
        f"the ones where they don't.",
        f" The point is selection, not a blanket call. Most matches the model and the market "
        f"agree on. This is one of the ones where they don't, and the gap is on the "
        f"{side_name} side specifically.",
        f" The engine isn't arguing reputation, recency, or narrative. It's reading the "
        f"underlying numbers and finding {side_name} priced shorter on the market than the "
        f"prior supports — that's the disagreement.",
    ]
    para_discipline = bootstrap_line + pick("§5-posture", posture_options)

    # ── §6. What moves this — vary by time-to-kickoff ────────────────
    cadence_phrase: str
    if days_out is None:
        cadence_phrase = (
            "The engine republishes on a regular cadence and again after major news."
        )
    elif days_out > 30:
        cadence_phrase = (
            f"With kickoff {days_out} days out, the refresh is weekly until we cross five "
            f"days, then daily, then hourly inside the final day."
        )
    elif days_out > 5:
        cadence_phrase = (
            f"With kickoff {days_out} days out, refresh is weekly; daily cadence picks up "
            f"inside the final five days."
        )
    elif days_out > 1:
        cadence_phrase = (
            f"Inside the final five days now — {days_out} days to kickoff — so the model "
            f"refreshes daily. Hourly inside the final 24 hours."
        )
    elif days_out >= 0:
        cadence_phrase = (
            f"Inside the final 24 hours — hourly refresh. Team news and weather re-enter "
            f"the prior on every cycle until kickoff."
        )
    else:
        cadence_phrase = (
            f"Match has kicked off; the published number is the last pre-match read."
        )

    para_close_options = [
        f"This number will move. The confirmed starting eleven, fitness news, weather at the "
        f"venue, and any tournament suspension carried in from previous matches all feed back "
        f"into the prior. {cadence_phrase} A wide Pick can collapse into a Pass if news moves "
        f"enough of the read. Editorial analysis only — Odds Primer does not place trades "
        f"and does not recommend a wager.",
        f"The read above is the most recent one, not a frozen call. {cadence_phrase} Injury "
        f"news, the actual XI, and conditions at kickoff all change what the model sees. "
        f"We re-publish on every refresh. The page shows what the engine reads; what to do "
        f"with that information is a reader's call.",
        f"What would close this gap: confirmed team news that pulls the prior down on the "
        f"side we like, a venue or weather change, or a tournament suspension landing before "
        f"kickoff. {cadence_phrase} A Pick this wide doesn't collapse on small news; a narrow "
        f"one can flip to Pass on a single refresh. Either way, the engine republishes and "
        f"the page reflects the latest read.",
    ]
    para_close = pick("§6", para_close_options)

    return "\n\n".join([
        para_fixture, para_elo, para_model, para_market, para_discipline, para_close,
    ])


def _squad_blurb_for_inputs(i: Inputs) -> str:
    """Deterministic squad sentence for the stub.

    Spec 2026-05-31: every published match must carry a non-empty
    `squad_blurb` so the website's Squad section is never blank, even
    when Haiku is unavailable.

    Strategy:
      * If team_a_news / team_b_news carry absences, render a short
        "Out: Name (injury). Out for {team}: ..." line per side.
      * If at-risk cards present, append "{Name} carries one yellow"
        per side. Phrased as risk, not fact (matches the prompt rules).
      * Otherwise: deterministic positive default. We rotate three
        variants by a salt so the stub doesn't repeat the same sentence
        across the slate.
    """
    a = i.get("team_a") or "Home"
    b = i.get("team_b") or "Away"
    salt = f"{a}|{b}|squad"

    news_a = i.get("team_a_news")
    news_b = i.get("team_b_news")

    parts: list[str] = []

    def _names_from(news, attr: str) -> list[str]:
        if news is None:
            return []
        rows = getattr(news, attr, ()) or ()
        names: list[str] = []
        for r in rows:
            n = (getattr(r, "name", "") or "").strip()
            if n:
                names.append(n)
        return names

    a_out = _names_from(news_a, "absences")
    b_out = _names_from(news_b, "absences")
    a_risk = _names_from(news_a, "cards")
    b_risk = _names_from(news_b, "cards")

    if a_out:
        parts.append(f"Out for {a}: {', '.join(a_out)}.")
    if b_out:
        parts.append(f"Out for {b}: {', '.join(b_out)}.")
    if a_risk:
        parts.append(f"{', '.join(a_risk)} carries one yellow into the {a} fixture.")
    if b_risk:
        parts.append(f"{', '.join(b_risk)} carries one yellow into the {b} fixture.")

    if parts:
        return " ".join(parts)

    # No-data default — seven positive variants rotated by salt so the
    # stub doesn't sound like the same line on every match. Operator-
    # voiced (2026-05-31): less boilerplate, more like something a
    # human-written column would say.
    defaults = (
        "No team news worth the name on either side.",
        "Nothing's surfaced on either squad this week — no absences, no bans.",
        "Quiet on the team-news front: no reported injuries or suspensions either way.",
        "Neither camp has flagged a thing this close to kickoff.",
        "No late fitness or discipline news on either side.",
        "Both benches are quiet — nothing reported, nothing suspended.",
        "Clean bill on the team sheets, as far as anyone's said.",
    )
    return defaults[_variant_index(salt, len(defaults))]


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
    blurb = _with_chorus(blurb, i.get("editorial_citations"), salt=salt)
    pick_driver_pool = [
        f"Pre-match Elo gives {side_name} a stronger prior than the {venue_label} line implies.",
        f"The {edge:+.1f}pp gap clears the Desk's 3 percentage point threshold for a Pick.",
        f"This is a selection call on the {side_name} side, not a blanket read on the market.",
        f"Confirmed XI, fitness news, and weather re-enter the prior closer to kickoff.",
        f"Bootstrap lower-bound on the {side_name} side still clears the Pick threshold.",
        f"Editorial analysis only — Odds Primer does not place trades or recommend a wager.",
    ]
    # Cross-venue best-place line (ADR 0004). Slot it ahead of the
    # generic Elo / threshold lines so it lands in the rendered top-3
    # without re-tuning the rotation salt.
    bv_label = i.get("best_venue_label")
    bv_e     = i.get("best_venue_true_price")
    if bv_label and bv_e is not None and bv_label != venue_label:
        pick_driver_pool.insert(
            0,
            f"Cheapest way in on {side_name} is {bv_label} at an effective {_pct(bv_e)}.",
        )
    _pd = _variant_index(salt + "/drivers", len(pick_driver_pool))
    drivers = [pick_driver_pool[(_pd + k) % len(pick_driver_pool)] for k in range(4)]
    return Copy(
        title=title, summary=summary, blurb=blurb, drivers=drivers,
        squad_blurb=_squad_blurb_for_inputs(i),
    )


def _pass_copy(i: Inputs) -> Copy:
    a, b = i["team_a"], i["team_b"]
    venue_label = (i.get("market_venue") or "the market").title()
    p_a  = float(i.get("model_p_a")    or 0.0)
    p_d  = float(i.get("model_p_draw") or 0.0)
    p_b  = float(i.get("model_p_b")    or 0.0)
    mp_a = float(i.get("market_p_a")    or 0.0)
    mp_d = float(i.get("market_p_draw") or 0.0)
    mp_b = float(i.get("market_p_b")    or 0.0)
    # Favourite by model probability — used by a couple of framings.
    _sides = [(a, p_a, mp_a), ("the draw", p_d, mp_d), (b, p_b, mp_b)]
    fav, fav_mp, fav_kp = max(_sides, key=lambda s: s[1])

    salt = f"{a}|{b}|pass"

    def pick(key: str, opts: list[str]) -> str:
        return opts[_variant_index(salt + "/" + key, len(opts))]

    pass_title_options = [
        f"{a} v {b} · the price already reflects what we see",
        f"{a} v {b} · no real gap to publish",
        f"{a} v {b} · the line is doing its job",
        f"{a} v {b} · two reads, one answer",
        f"{a} v {b} · model and market line up",
        f"{a} v {b} · nothing to chase here",
        f"{a} v {b} · the read is the same on both sides",
        f"{a} v {b} · priced about right",
    ]

    pass_summary_options = [
        # 1 — quiet convergence
        f"Our model lands close to {venue_label} on every side of {a} v {b}. Nothing wide "
        f"enough to publish as a Pick. Pass.",
        # 2 — favourite priced about right
        f"{fav} is the favourite at {_pct(fav_kp)}; the model lands within touching distance "
        f"at {_pct(fav_mp)}. Nothing to chase. Pass.",
        # 3 — tight match
        f"{a} v {b} is genuinely tight, and the market knows it. No side gives the model "
        f"enough room to disagree. Pass.",
        # 4 — noise vs signal
        f"Any gap on {a} v {b} sits inside the model's own uncertainty band. Pass — the "
        f"signal isn't there yet.",
        # 5 — line is doing its work
        f"The line on {a} v {b} is doing its job: the price is already absorbing the same "
        f"reads the model is using. Pass.",
        # 6 — news pending
        f"On {a} v {b} the model and the market read the fixture the same way. Line-ups, "
        f"weather, and any late news will be revisited closer to kickoff. Pass for now.",
        # 7 — no manufactured edge
        f"There's no Pick to manufacture on {a} v {b}. The model and {venue_label} arrive "
        f"at the same shape. Pass.",
        # 8 — short note, sides equal
        f"Across {a}, the draw, and {b}, neither side stretches more than a point past the "
        f"market. Pass.",
    ]

    pass_blurb_options = [
        # 1 · two reads, same answer
        f"On {a} versus {b}, our model and the market arrive at the same shape from different "
        f"directions. {a} reads at {_pct(p_a)}, the draw at {_pct(p_d)}, {b} at {_pct(p_b)}. "
        f"The market's shape sits on top of that read. When two independent estimates "
        f"converge, there is rarely a Pick worth publishing. We'll revisit closer to kickoff "
        f"when team news and weather can pull the two numbers apart.",
        # 2 · market is doing its work
        f"The line on {a} versus {b} is already absorbing the same information our model is "
        f"weighing. {venue_label} prices {a} at {_pct(mp_a)}, the draw at {_pct(mp_d)}, {b} at "
        f"{_pct(mp_b)}; our read is the same shape. Pass means the market is doing its job — "
        f"not a missed opportunity, not a lazy verdict. We look for disagreement; today, "
        f"there isn't enough of it on either side.",
        # 3 · favourite already priced
        f"{fav} should win, and the price already says so. The model has {fav} at "
        f"{_pct(fav_mp)}, the market at {_pct(fav_kp)}. Strong favourites priced shorter than "
        f"the model rates them is where we get Picks; the reverse — both numbers landing in "
        f"the same place — is where we get a Pass. We'll check again near kickoff when the "
        f"confirmed eleven and any fitness news land; until then, the price reads fair.",
        # 4 · close fixture, no separation
        f"{a} versus {b} is a tight one — neither side carries enough mass to break out, the "
        f"draw is in play, and the model's three-way ({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}) "
        f"runs close to the market throughout. Tight fixtures rarely produce Picks because the "
        f"prior is spread, not concentrated. Pass. A single piece of late team news — a "
        f"surprise omission, a fitness scare — could move this, so it stays on the watch list "
        f"to the day of the match.",
        # 5 · signal inside the noise
        f"Our model carries a confidence band around every estimate, and on {a} versus {b} "
        f"the market price sits inside that band on all three sides. The point estimates "
        f"({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}) run close to {venue_label}, but more "
        f"importantly the small differences that do exist are smaller than the model's own "
        f"uncertainty about its number. Pass is what we publish when the signal is inside "
        f"the noise. The bands tighten as kickoff nears.",
        # 6 · sentiment vs read
        f"Talk around {a} versus {b} can move a price faster than the underlying read "
        f"changes — narrative pulls one side short, momentum pulls the other. The model's "
        f"job is to read the fixture, not the room, and on this one the read agrees with the "
        f"market regardless. {a} {_pct(p_a)}, draw {_pct(p_d)}, {b} {_pct(p_b)}; the line "
        f"holds the same shape. No disagreement, no Pick. Pass.",
        # 7 · discipline / no manufactured edge
        f"On {a} versus {b}, the line and the model are saying the same thing, and we will "
        f"not invent a disagreement that isn't there. The model rates the three sides at "
        f"{_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}; the market's split runs close enough that "
        f"any gap is well below our Pick threshold. The verdict that says 'we looked, the "
        f"line is fair, there's nothing to add today' is more useful than a forced call. "
        f"Pass.",
        # 8 · stability / no recent move
        f"Nothing in the lead-up to {a} versus {b} has pulled the price meaningfully off the "
        f"model. Team news has been quiet, no shock injury or suspension has landed, and the "
        f"market's three-way ({_pct(mp_a)} / {_pct(mp_d)} / {_pct(mp_b)}) tracks the model's "
        f"read ({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}). Pass holds in a quiet week. The "
        f"engine republishes as news moves the prior; a confirmed XI surprise is the most "
        f"likely thing to turn this into a Pick.",
    ]

    title   = pick("pass-title",   pass_title_options)
    summary = pick("pass-summary", pass_summary_options)
    blurb   = pick("pass-blurb",   pass_blurb_options)
    blurb   = _with_chorus(blurb, i.get("editorial_citations"), salt=salt)
    # Rotate driver pools so every Pass page doesn't read three identical bullets.
    driver_pool = [
        f"Model puts {a} at {_pct(p_a)}, the draw at {_pct(p_d)}, {b} at {_pct(p_b)} — close to the market on each side.",
        f"No side runs more than a couple of points clear of the model on this fixture.",
        f"Team news, weather, and the confirmed XI feed back into the prior as kickoff approaches.",
        f"Tight three-way pricing rarely produces a Pick — the disagreement isn't there to publish.",
        f"The market is absorbing the same reads the model is weighing; nothing to chase.",
        f"Pass for now. The engine republishes hourly inside T-24h and after major news.",
    ]
    # Pick three drivers, deterministic by fixture but rotated so cards differ.
    _d_idx = _variant_index(salt + "/drivers", len(driver_pool))
    drivers = [driver_pool[(_d_idx + k) % len(driver_pool)] for k in range(3)]
    return Copy(
        title=title, summary=summary, blurb=blurb, drivers=drivers,
        squad_blurb=_squad_blurb_for_inputs(i),
    )


def _avoid_copy(i: Inputs) -> Copy:
    a, b = i["team_a"], i["team_b"]
    edge = i["edge_pp"] or 0.0
    venue_label = (i.get("market_venue") or "the market").title()
    competition = i.get("competition") or "this competition"
    p_a = float(i.get("model_p_a")    or 0.0)
    p_d = float(i.get("model_p_draw") or 0.0)
    p_b = float(i.get("model_p_b")    or 0.0)

    salt = f"{a}|{b}|avoid"

    def pick(key: str, opts: list[str]) -> str:
        return opts[_variant_index(salt + "/" + key, len(opts))]

    avoid_title_options = [
        f"{a} v {b} · the whole field is priced rich",
        f"{a} v {b} · every side reads short",
        f"{a} v {b} · nothing in the reader's favour",
        f"{a} v {b} · the market is asking a premium",
        f"{a} v {b} · no side this engine would take",
        f"{a} v {b} · priced ahead of the read on every line",
        f"{a} v {b} · sit it out",
        f"{a} v {b} · the field reads overpriced",
    ]

    avoid_summary_options = [
        # 1 — every side rich
        f"Every side of {a} v {b} is priced shorter than the model makes it — the worst gap "
        f"is {edge:+.1f}pp. Avoid.",
        # 2 — premium across the field
        f"{venue_label} is asking a premium on all three sides of {a} v {b}, the widest gap "
        f"running to {edge:+.1f}pp. Avoid — sit this one out.",
        # 3 — even the best side is rich
        f"On {a} v {b}, even the side closest to fair is {edge:+.1f}pp short of the model. "
        f"Avoid: there's no line the engine would take.",
        # 4 — model below market throughout
        f"The model reads {a} v {b} lower than the market on every side. Worst gap "
        f"{edge:+.1f}pp. Avoid.",
        # 5 — plain language
        f"Every line on {a} v {b} reads rich against the model. Worst case {edge:+.1f}pp. "
        f"Avoid — leave this one alone.",
        # 6 — different from Pass
        f"{a} v {b} isn't a quiet Pass — it's an Avoid. The market is short of the model "
        f"on all three sides, by as much as {edge:+.1f}pp.",
        # 7 — narrative
        f"On {a} v {b}, the price is running ahead of what the read can justify on every "
        f"side. Worst gap {edge:+.1f}pp. Avoid.",
        # 8 — short
        f"All three sides of {a} v {b} read short of the model — the worst is {edge:+.1f}pp. "
        f"Avoid.",
    ]

    avoid_blurb_options = [
        # 1 · field overpriced, no carve-out
        f"On {a} versus {b}, the model lands lower than the market on every side. The "
        f"widest gap runs {edge:+.1f}pp against the reader, and even the side closest to fair "
        f"doesn't clear into value. That separates an Avoid from a Pass: a Pass says the "
        f"line is fair, an Avoid says the line is rich. There's no clever carve-out "
        f"here, no underrated side hiding inside the spread. The useful thing is to point it "
        f"out and move on. We surface Avoid so the absence of a good side is named, not left "
        f"to inference.",
        # 2 · sentiment / overreaction
        f"Pricing on {a} versus {b} is running ahead of what either side's underlying read "
        f"would support. The model's three-way ({_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}) sits "
        f"below the market on each outcome, and the most negative gap reaches {edge:+.1f}pp. "
        f"This is the pattern that fires when narrative — a big-name favourite, a high-profile "
        f"opponent, a tournament storyline — pulls one or both sides shorter than they "
        f"deserve. The verdict is Avoid: there is no side here the engine would take, even "
        f"on the conservative reading.",
        # 3 · over-tight overround
        f"{venue_label} has priced every line on {a} versus {b} above what the model makes "
        f"it. Read as a probability distribution, the market's overround on this fixture is "
        f"working against the reader on all three sides at once — and that's what produces an "
        f"Avoid rather than a single mispriced Pick. The model rates the three sides at "
        f"{_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}; the market sits short of each one. The "
        f"widest gap is {edge:+.1f}pp. We're not picking a side here; we're naming the shape.",
        # 4 · favourite reputation / overvaluation
        f"On {a} versus {b}, the model's read is materially lower than the market across the "
        f"board, with the worst gap at {edge:+.1f}pp. When the field reads rich and there is "
        f"no obvious carve-out, the engine isn't seeing what the price is seeing — usually "
        f"because reputation, recency, or a single salient performance has pulled one or both "
        f"sides shorter than the fundamentals justify. The model is built to ignore that and "
        f"read the prior. Avoid is the call when the prior doesn't support the price anywhere.",
        # 5 · stale or thin liquidity
        f"On a fixture this far from kickoff, with thinner two-way action than the headline "
        f"markets, prices can sit ahead of the model for a while without being corrected. "
        f"That's what we're looking at on {a} versus {b}: the model is below {venue_label} on "
        f"every side, worst gap {edge:+.1f}pp, and the line hasn't moved enough to close the "
        f"gap on any of them. The verdict is Avoid. We'll re-publish as the market deepens — "
        f"if the gaps close as kickoff nears, this can shift; today, it reads short throughout.",
        # 6 · short / leave-alone
        f"The market is shorter than the model on all three sides of {a} versus {b}. The "
        f"widest gap runs {edge:+.1f}pp against the reader. Avoid is what we publish when "
        f"there's no side a reader would want, including the side closest to fair. The model's "
        f"three-way reads {_pct(p_a)} / {_pct(p_d)} / {_pct(p_b)}; the market sits over each. "
        f"It's a plain verdict for a plain situation — every side rich, nothing to take, no "
        f"angle worth surfacing.",
        # 7 · contrarian angle / wait
        f"When a whole market reads rich on the model, the useful next step is to wait, "
        f"not to chase a side. On {a} versus {b}, the model sits below the market by as much "
        f"as {edge:+.1f}pp, and that kind of misalignment usually clears one of two ways: the "
        f"line drifts back as money rotates, or fresh news pulls the prior up to meet the "
        f"price. Either path is a future read. Today, the model has no side it would take, "
        f"and the call is Avoid.",
        # 8 · tournament context
        f"In {competition}, the field on {a} versus {b} reads short of the model across the "
        f"board — worst gap {edge:+.1f}pp. Tournament fixtures can carry a tighter overround "
        f"than club football because liquidity concentrates on a smaller number of high-stakes "
        f"matches; when the model lands under the market on every side, the engine reads that "
        f"as a market the reader is paying to be in, not a market with a hidden carve-out. "
        f"Avoid. We re-evaluate as confirmed line-ups and weather arrive — those are what "
        f"would move the prior up to meet a rich price.",
    ]

    title   = pick("avoid-title",   avoid_title_options)
    summary = pick("avoid-summary", avoid_summary_options)
    blurb   = pick("avoid-blurb",   avoid_blurb_options)
    blurb   = _with_chorus(blurb, i.get("editorial_citations"), salt=salt)
    avoid_driver_pool = [
        f"Model reads {a} {_pct(p_a)} / draw {_pct(p_d)} / {b} {_pct(p_b)} — short of the market on every side.",
        f"Worst gap is {edge:+.1f}pp against the reader; even the side closest to fair doesn't clear.",
        f"Avoid is a separate verdict from Pass — a Pass is fair, an Avoid is rich across the board.",
        f"No carve-out side. When the model sits under the market everywhere, the right call is to wait.",
        f"Pricing is running ahead of what the underlying read on either side supports.",
        f"The engine re-evaluates as team news, weather, and the confirmed XI land closer to kickoff.",
    ]
    _ad = _variant_index(salt + "/drivers", len(avoid_driver_pool))
    drivers = [avoid_driver_pool[(_ad + k) % len(avoid_driver_pool)] for k in range(3)]
    return Copy(
        title=title, summary=summary, blurb=blurb, drivers=drivers,
        squad_blurb=_squad_blurb_for_inputs(i),
    )


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


# Deterministic-by-fixture opener variants. Same fixture → same chorus
# wording across re-runs. The voice rules and length budget filter
# anything that drifts into endorsement-speak or marketing tone.
#
# `{outlet}` is the single attributed outlet for the one-quote shape.
# `{quote}` is the truncated, voice-clean line, rendered between double
# quotes by the caller.
_ONE_QUOTE_OPENERS: tuple[str, ...] = (
    'Per {outlet}: "{quote}"',
    'From {outlet}: "{quote}"',
    '{outlet} reported: "{quote}"',
    '{outlet} carried the line: "{quote}"',
    '{outlet}\'s line on this fixture: "{quote}"',
)

# Two-quote shape: cite a second outlet to evidence the consensus.
_TWO_QUOTE_OPENERS: tuple[str, ...] = (
    '{outlet1} reported: "{quote1}" {outlet2} added: "{quote2}"',
    'Per {outlet1}: "{quote1}" {outlet2} carried the same line: "{quote2}"',
    'Two outlets covered the build-up this week — {outlet1}: "{quote1}"; {outlet2}: "{quote2}"',
)


def _press_chorus(
    cites: list[Citation] | None,
    *,
    salt: str = "",
) -> str | None:
    """Voice-clean press chorus appended to a blurb when news citations
    are present. Returns None when nothing safe to say.

    Three shapes, picked by what survives the voice filter:

      1. **Two-quote shape** — when ≥ 2 outlets each contribute a voice-
         clean quote: cite both. Variant chosen deterministically by
         `salt` so the same fixture always reads the same way.
      2. **One-quote shape** — when only one outlet has a usable quote:
         feature it. Variant also salt-deterministic.
      3. **Count shape** — when no quote survives the voice filter but
         ≥ 2 distinct outlets remain: name the outlets, skip the prose.
         Last-resort framing that still tells the reader who covered
         the fixture.

    All output is voice-checked one final time before return. A failing
    final check returns None — the blurb body still ships unchanged.
    """
    cites = cites or []
    distinct_outlets = _distinct_outlets(cites)
    if len(distinct_outlets) < _CHORUS_MIN_OUTLETS:
        return None

    # Pre-filter quotes by voice — banned phrases like "guaranteed",
    # "lock", "back the" get nuked. The outlet's URL + name still ship
    # via the editorial_citations contract; we just don't quote them.
    safe = [c for c in cites if c.quote and is_voice_clean(c.quote)]

    candidate = _try_two_quote(safe, salt) \
             or _try_one_quote(safe, salt) \
             or _count_shape(distinct_outlets)

    return candidate if (candidate and is_voice_clean(candidate)) else None


def _try_two_quote(safe: list[Citation], salt: str) -> str | None:
    """Render the two-quote shape if ≥ 2 outlets each have a clean quote.

    Picks the first surviving citation from each of the two top outlets
    (citations arrive pre-sorted by source reliability desc), so the
    pair reflects the strongest two sources.
    """
    by_outlet: dict[str, Citation] = {}
    for c in safe:
        name = (c.outlet or "").strip()
        if name and name not in by_outlet:
            by_outlet[name] = c
    if len(by_outlet) < 2:
        return None
    items = list(by_outlet.items())[:2]
    template = _TWO_QUOTE_OPENERS[_variant_index(salt + "/chorus2", len(_TWO_QUOTE_OPENERS))]
    return template.format(
        outlet1=items[0][0],
        quote1=_truncate_quote(items[0][1].quote).strip().rstrip('"').rstrip("'"),
        outlet2=items[1][0],
        quote2=_truncate_quote(items[1][1].quote).strip().rstrip('"').rstrip("'"),
    )


def _try_one_quote(safe: list[Citation], salt: str) -> str | None:
    """Render the one-quote shape if exactly one outlet has a clean quote."""
    if not safe:
        return None
    c = safe[0]
    outlet = (c.outlet or "").strip()
    if not outlet:
        return None
    template = _ONE_QUOTE_OPENERS[_variant_index(salt + "/chorus1", len(_ONE_QUOTE_OPENERS))]
    return template.format(
        outlet=outlet,
        quote=_truncate_quote(c.quote).strip().rstrip('"').rstrip("'"),
    )


def _count_shape(distinct_outlets: list[str]) -> str:
    """Last-resort framing when no clean quote survived the voice filter."""
    names = distinct_outlets[:_CHORUS_MAX_NAMED_OUTLETS]
    rest  = len(distinct_outlets) - len(names)
    listed = ", ".join(names)
    if rest > 0:
        listed += f", and {rest} other{'s' if rest != 1 else ''}"
    return (
        f'Recent coverage from {len(distinct_outlets)} outlets '
        f'({listed}) sits behind this verdict; full sources below.'
    )


def _with_chorus(
    blurb: str,
    cites: list[Citation] | None,
    *,
    salt: str = "",
) -> str:
    """Append the press chorus to a blurb when one is available."""
    chorus = _press_chorus(cites, salt=salt)
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
