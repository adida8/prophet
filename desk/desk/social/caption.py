"""Caption generators for IG + X — purely deterministic templates.

Both captions pass through `desk.explainer.voice.assert_voice_clean`
before they leave this module. On any violation we drop back to a
minimal fallback so a draft is still queued (the operator sees the
problem in the UI and can re-write by hand). The voice check also
catches the social-specific banned phrases registered below.

Citation lockstep is enforced separately: if a generated IG caption
mentions an outlet by name, that outlet must appear in
`copy.editorial_citations[].outlet`. The templated v0.1 form NEVER
names an outlet, so the assertion is paid for in tests; the gate
catches drift if a future template adds press-chorus prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from desk.explainer.voice import (
    VoiceCheckFailed,
    assert_voice_clean,
)
from desk.publish.contract import MatchOutput
from desk.social.models import WeeklyRoundupPayload


# ── Length caps (platform-imposed) ───────────────────────────────────

IG_MAX_CHARS = 2200
X_MAX_CHARS  = 280


# ── Social-only banned phrases ───────────────────────────────────────
# Extends the explainer's banned list so the social path catches
# language that's specifically dangerous in feed copy. Compliance:
# "educational framing only — no 'bet now' / 'guaranteed' / 'lock'."

SOCIAL_BANNED_PHRASES: tuple[str, ...] = (
    "bet now",
    "guaranteed",
    "lock",                  # also in BANNED_PHRASES but kept here for explicitness
    "easy money",
    "sure thing",
    "can't lose",
    "free pick",
    "tip",
)


class CaptionViolation(ValueError):
    """A generated caption broke a hard rule and the fallback fired."""


# ── Public API ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GeneratedCaptions:
    caption_ig: str
    caption_x:  str
    fell_back:  bool          # True when one or both fell back to minimal


def generate_daily_captions(match: MatchOutput) -> GeneratedCaptions:
    """Build IG + X captions for one daily Pick draft.

    Templates are sourced from spec §7. Both run through the voice
    check; either failure fell-back returns True so the runner can log
    a warning + the operator sees a hint in the UI.
    """
    try:
        ig = _build_ig_daily(match)
        _voice_assert_strict(ig)
    except (VoiceCheckFailed, CaptionViolation):
        ig = _fallback_caption(match)
        fell_back_ig = True
    else:
        fell_back_ig = False

    try:
        x  = _build_x_daily(match)
        _voice_assert_strict(x)
    except (VoiceCheckFailed, CaptionViolation):
        x  = _fallback_caption(match)
        fell_back_x  = True
    else:
        fell_back_x  = False

    return GeneratedCaptions(
        caption_ig=ig,
        caption_x=x,
        fell_back=fell_back_ig or fell_back_x,
    )


def generate_weekly_captions(payload: WeeklyRoundupPayload) -> GeneratedCaptions:
    """Build IG + X captions for the Sunday roundup."""
    try:
        ig = _build_ig_weekly(payload)
        _voice_assert_strict(ig)
    except (VoiceCheckFailed, CaptionViolation):
        ig = _fallback_weekly(payload)
        fell_back_ig = True
    else:
        fell_back_ig = False

    try:
        x = _build_x_weekly(payload)
        _voice_assert_strict(x)
    except (VoiceCheckFailed, CaptionViolation):
        x = _fallback_weekly(payload)
        fell_back_x = True
    else:
        fell_back_x = False

    return GeneratedCaptions(
        caption_ig=ig,
        caption_x=x,
        fell_back=fell_back_ig or fell_back_x,
    )


# ── Daily IG ──────────────────────────────────────────────────────────


def _build_ig_daily(m: MatchOutput) -> str:
    title   = (m.copy.title or "").strip()
    summary = (m.copy.summary or "").strip()
    blurb   = (m.copy.blurb or "").strip()
    body_parts: list[str] = [p for p in (title, summary, blurb) if p]
    body = "\n\n".join(body_parts)
    body = _strip_outlet_attributions(body, m)

    sig = "— The Desk"
    link = _match_link(m)
    hashtags = " ".join(_daily_hashtags(m))

    caption = "\n\n".join(p for p in (body, sig, link, hashtags) if p)
    return _truncate_to(caption, IG_MAX_CHARS)


def _build_x_daily(m: MatchOutput) -> str:
    """Title + model/market line + link. Title-only fallback if it's tight."""
    title = (m.copy.title or "").strip()
    link  = _match_link(m)
    pick_side = m.verdict.side or ""
    model_p   = m.verdict.model_p
    market_p  = m.verdict.market_p
    edge_pp   = m.verdict.edge_pp

    short = f"{title}\n\n{link}"
    if len(short) >= X_MAX_CHARS:
        return _truncate_to(short, X_MAX_CHARS)

    if (pick_side and model_p is not None and market_p is not None
            and edge_pp is not None):
        body_line = (
            f"We rate {pick_side} at {round(model_p * 100):.0f}%. "
            f"Market prices it at {round(market_p * 100):.0f}%. "
            f"{_signed_pp(edge_pp)}."
        )
        full = f"{title}\n\n{body_line}\n\n{link}"
        if len(full) <= X_MAX_CHARS:
            return full
    return short


# ── Weekly ────────────────────────────────────────────────────────────


def _build_ig_weekly(p: WeeklyRoundupPayload) -> str:
    """Slide-by-slide-mirroring text — the caption is the same payload
    in prose, on a single post. Operator can rewrite live before
    Approving."""
    week_label = p.week_starting.strftime("week of %b %d, %Y")
    head = f"The Desk · {week_label}"
    lines: list[str] = [head, ""]
    if p.top_picks:
        lines.append("This week's top calls:")
        for row in p.top_picks:
            lines.append(
                f"· {row.team_a} vs {row.team_b} — {row.pick_side} "
                f"({_signed_pp(row.edge_pp)})"
            )
        lines.append("")
    if p.hit_rate is not None and p.hit_rate_sample_size:
        pct = round(p.hit_rate * 100)
        lines.append(
            f"Resolved Picks last week: {pct}% landed "
            f"({p.hit_rate_sample_size} settled)."
        )
        lines.append("")
    if p.what_we_got_wrong is not None:
        wrong = p.what_we_got_wrong
        lines.append(
            f"What we got wrong: our highest-conviction call on "
            f"{wrong.pick_side} did not land."
        )
        lines.append("")
    lines.append("— The Desk")
    lines.append("oddsprimer.com")
    lines.append(" ".join(_weekly_hashtags()))
    caption = "\n".join(lines).strip()
    return _truncate_to(caption, IG_MAX_CHARS)


def _build_x_weekly(p: WeeklyRoundupPayload) -> str:
    head = f"The Desk · {p.week_starting.strftime('week of %b %d, %Y')}"
    body_lines: list[str] = []
    if p.hit_rate is not None and p.hit_rate_sample_size:
        pct = round(p.hit_rate * 100)
        body_lines.append(
            f"Resolved Picks: {pct}% landed ({p.hit_rate_sample_size})."
        )
    if p.top_picks:
        top = p.top_picks[0]
        body_lines.append(
            f"Top call: {top.team_a} vs {top.team_b} — {top.pick_side} "
            f"({_signed_pp(top.edge_pp)})."
        )
    link = "oddsprimer.com"
    body = "\n".join(body_lines).strip()
    full = "\n\n".join(p for p in (head, body, link) if p)
    if len(full) <= X_MAX_CHARS:
        return full
    short = f"{head}\n\n{link}"
    return _truncate_to(short, X_MAX_CHARS)


# ── Fallbacks ─────────────────────────────────────────────────────────


def _fallback_caption(m: MatchOutput) -> str:
    return f"{m.team_a} vs {m.team_b} — {_match_link(m)}"


def _fallback_weekly(p: WeeklyRoundupPayload) -> str:
    return (
        f"The Desk · week of {p.week_starting.strftime('%b %d, %Y')} — "
        "oddsprimer.com"
    )


# ── Helpers ───────────────────────────────────────────────────────────


def _voice_assert_strict(text: str) -> None:
    """Run the explainer's voice check AND the social banned-phrase list."""
    assert_voice_clean(text)
    lowered = text.lower()
    for phrase in SOCIAL_BANNED_PHRASES:
        # Use word-aware match for very short phrases like 'tip' / 'lock'
        # so we don't trip on innocuous substrings ("locker"/"lockstep").
        if _has_word(lowered, phrase):
            raise CaptionViolation(f"banned phrase {phrase!r} in caption")


_WORD_BOUNDARY = re.compile(r"\W+")


def _has_word(haystack_lower: str, needle: str) -> bool:
    """Whole-word containment (no false positives on substrings)."""
    needle_lower = needle.lower()
    pattern = r"(?<!\w)" + re.escape(needle_lower) + r"(?!\w)"
    return re.search(pattern, haystack_lower) is not None


def _signed_pp(edge: float) -> str:
    sign = "+" if edge >= 0 else "−"
    return f"{sign}{abs(edge):.1f}pp"


def _match_link(m: MatchOutput) -> str:
    return f"oddsprimer.com/m/{m.match_id}"


def _daily_hashtags(m: MatchOutput) -> list[str]:
    """Static hashtag set: brand + competition + both teams.

    Team tags are lowercased + alnum-only. We keep the set small (≤6) so
    captions stay readable and the operator can edit them by hand.
    """
    tags = ["#oddsprimer", "#predictionmarkets"]
    comp_code = (m.competition.code or "").lower()
    if comp_code == "wc26":
        tags.append("#worldcup2026")
        tags.append("#wc2026")
    elif comp_code:
        tags.append("#" + _slugify(comp_code))
    tags.append("#" + _slugify(m.team_a))
    tags.append("#" + _slugify(m.team_b))
    return tags


def _weekly_hashtags() -> list[str]:
    return ["#oddsprimer", "#worldcup2026", "#wc2026", "#predictionmarkets"]


_HASHTAG_RE = re.compile(r"[^a-z0-9]")


def _slugify(value: str) -> str:
    return _HASHTAG_RE.sub("", value.lower()) or "team"


def _truncate_to(text: str, cap: int) -> str:
    """Hard truncate. If we have to chop, end on a clean word boundary
    so the operator sees a readable ellipsis."""
    if len(text) <= cap:
        return text
    cut = text[: cap - 1]
    # Walk back to the last whitespace boundary inside the cut window.
    last_space = cut.rfind(" ")
    if last_space >= int(cap * 0.7):
        cut = cut[:last_space]
    return cut.rstrip() + "…"


# ── Citation lockstep ────────────────────────────────────────────────


_OUTLET_HINTS = (
    "according to",
    "per ",
    "reports ",
    "reported ",
    "per the ",
)


def _strip_outlet_attributions(body: str, m: MatchOutput) -> str:
    """Sentences that name an outlet must be lockstep with editorial_citations.

    v0.1 templated path never inserts outlet names — the explainer's
    blurb does, when news-signals have populated `editorial_citations`.
    For safety: if a blurb sentence mentions an outlet that isn't in
    the citation list, drop that sentence. Defence in depth, not the
    primary gate (the explainer's own voice check already runs upstream).
    """
    allowed_outlets = {c.outlet.lower() for c in (m.copy.editorial_citations or [])}
    if not body:
        return body
    sentences = re.split(r"(?<=[.?])\s+", body)
    kept: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if not any(hint in lowered for hint in _OUTLET_HINTS):
            kept.append(sentence)
            continue
        # Sentence might name an outlet. Allow it iff at least one of
        # the citation outlets appears.
        if allowed_outlets and any(out in lowered for out in allowed_outlets):
            kept.append(sentence)
            continue
        # Drop the sentence — we can't verify the citation.
    return " ".join(s.strip() for s in kept if s.strip())


__all__ = (
    "SOCIAL_BANNED_PHRASES",
    "CaptionViolation",
    "GeneratedCaptions",
    "IG_MAX_CHARS",
    "X_MAX_CHARS",
    "generate_daily_captions",
    "generate_weekly_captions",
)
