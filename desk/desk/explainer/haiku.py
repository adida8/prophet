"""Haiku-driven blurb writer — PR 5.

Replaces the templated `stub.py` for the prose fields (title / summary /
blurb) on demand. Drivers stay deterministic in `stub.py` because they
encode model internals the LLM should not paraphrase.

Contract guarantees enforced on the way back from Anthropic:

  * Forced tool-use via `write_blurb` — the model can't ad-lib JSON;
    if the tool input is malformed, the call returns None and the
    caller falls back to the stub.
  * Voice rules — `voice.assert_voice_clean` runs on every field;
    a banned phrase, exclamation, or emoji falls back to the stub.
  * Word count — the blurb must land in [80, 220] words. Outside that
    window we treat the output as off-voice and fall back.
  * Outlet allowlist — any "[Outlet] reported / per [Outlet]" attribution
    must name an outlet present in `editorial_citations`. Hallucinated
    outlets are a hard fail.

Failures are never fatal: `try_haiku_copy` returns `None` and the
caller (`desk/explainer/__init__.py`) keeps the templated copy.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Protocol

from desk.explainer.stub import Inputs
from desk.explainer.voice import is_voice_clean
from desk.publish.contract import Citation, Copy

_LOG = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5"
_TOOL_NAME = "write_blurb"
_MAX_TOKENS = 1500
_TIMEOUT_SECONDS = 30.0

# Word-count guard for the blurb. VOICE.md targets 120-180 words; we
# allow a wider [80, 220] window so reasonable Haiku outputs survive
# without being too permissive. Outside the window → fall back to stub.
#
# Q3 squad-paragraph spec raises the ceiling to 240 words when either
# side has a non-empty squad picture (confirmed lineup OR an absence OR
# an at-risk card). The dedicated squad paragraph would otherwise
# squeeze the verdict prose; +20 words is enough headroom for one
# focused paragraph without inviting padding elsewhere.
_BLURB_MIN_WORDS = 80
_BLURB_MAX_WORDS = 220
_BLURB_MAX_WORDS_WITH_SQUAD = 240


# ── voice doc loader ────────────────────────────────────────────────

# `desk/VOICE.md` is the canonical voice spec. We embed it into the
# system prompt at module-import time so a single source of truth
# drives every Haiku call. If the file is missing (unlikely — it's
# committed) we fall back to a stub instruction and log a warning.
_VOICE_DOC_PATH = Path(__file__).resolve().parent.parent.parent / "VOICE.md"

_VOICE_DOC_FALLBACK = """\
Voice: dry, confident, never a tipster.
- Every blurb has a point (the gap, or the absence of it).
- 5-8 sentences, ~120-180 words.
- Attribute every real-world claim to an outlet in `editorial_citations`.
  Never invent a source.
- No exclamation marks, no emoji, no certainty ("will win", "guaranteed").
"""


def _load_voice_doc() -> str:
    try:
        return _VOICE_DOC_PATH.read_text(encoding="utf-8")
    except OSError as e:
        _LOG.warning("VOICE.md not loadable at %s (%s) — using fallback", _VOICE_DOC_PATH, e)
        return _VOICE_DOC_FALLBACK


_VOICE_DOC = _load_voice_doc()


# ── system prompt + tool schema ─────────────────────────────────────

_SYSTEM_PROMPT = f"""\
You write the editorial copy for one prediction-market football match.
For each match you produce three fields via the `write_blurb` tool:

  * title    — one line. Sentence case. Shape: "Team A v Team B · <hook>".
  * summary  — 1-2 sentences, plain prose, no source attribution.
  * blurb    — 5-8 sentences (~120-180 words). This is the main body.
               Attribute every real-world claim inline to an outlet in the
               provided `editorial_citations` list. If no citations are
               provided, source against model and market only — and claim
               nothing that would need a citation.

You MUST emit via the `write_blurb` tool. Do not write any prose around
the tool call.

The Desk's full voice spec — read it before writing:

---
{_VOICE_DOC}
---

Additional hard constraints:
- Never name an outlet that is not in `editorial_citations`.
- Never quote a sentence that is not in `editorial_citations[i].quote`.
- Never assert certainty about a result. The model rates probabilities;
  it does not predict outcomes.
- Never use exclamation marks or emoji.
- Sentence case throughout, except proper nouns.

TEAM NEWS POLICY

You are given `team_a_news` and `team_b_news` — structured availability
data for each side. Each carries:
  * absences   — players ruled out (injury / suspension), with position,
                 reason, source, and source_url when available.
  * lineup     — state ("confirmed" / "predicted" / "unknown"), source,
                 starters (when confirmed via api-football), and
                 announced_at when confirmed.
  * cards      — players one booking from a ban (state="at_risk"). Each
                 carries name, position, yellows count, and importance.
  * materiality — directive for how forcefully the blurb must address
                 availability: "high" / "medium" / "low" / "none".

SQUAD PARAGRAPH

The blurb MUST contain ONE dedicated paragraph covering the squad
picture, kept separate from the verdict / edge paragraph. It fires
on every match. What goes into it depends on what's known:

  1. Opening XI — when lineup.state="confirmed", name the formation
     once and 1–2 recognisable starters. ("France open 4-3-3 with
     Mbappé and Dembélé.") Never list all 11.
  2. Out — name absent players (injury / suspension), attributing to
     an outlet when source_url is present, stating the fact
     unattributed when source is api-football.
  3. At-risk — name players one booking from a ban, phrased as RISK,
     never as fact. ("Tchouaméni is one yellow from a suspension.")
  4. No-data case — when NONE of the above is known for either side
     (both team_a_news and team_b_news have materiality=none, both
     lineup states are "unknown", and both cards lists are empty),
     write ONE short sentence confirming the squad picture is clean.
     Use POSITIVE availability language only — examples:

       "Both squads come through clean; no late absences flagged."
       "Neither side carries any flagged availability concerns into kickoff."
       "Squad picture is straightforward — nothing flagged either way."
       "Both sides arrive ready, no late concerns surfaced."
       "No flagged absences on either side."

     NEVER name a player in the no-data case. NEVER claim a specific
     injury, suspension, or card status — we have no data behind any
     such claim. NEVER use phrases like "is injured", "is suspended",
     "ruled out", "out with", "one yellow from", "at risk of a ban"
     in the no-data case. Vary the phrasing across matches to avoid
     repetition.

If some clauses (1)-(3) are known and others aren't, write only the
known ones; don't pad with a no-data sentence on top.

NEVER invent a starter, an absence, a formation, or a card count.
NEVER name a player who is not in starters[], absences[], or cards[].
NEVER present an at-risk player as already banned or suspended.

Materiality matrix (controls how forcefully the squad paragraph
addresses the absences, not whether it fires — it always fires):

  materiality=high   → the squad paragraph MUST name at least one
                       absent player and the impact.
  materiality=medium → one short sentence naming the most important
                       absence.
  materiality=low    → optional; mention only when it fits the verdict
                       narrative (e.g. when an at-risk card is the only
                       availability content for the team).
  materiality=none   → write the no-data sentence per (4) above. Do
                       NOT claim any specific player is injured /
                       suspended / out — there's no data behind it.

Attribution rules for absences:
  * When an absence carries source_url (an RSS outlet covered it),
    attribute using the outlet name once on first mention, following
    the normal allowed-outlet rules. Example: "per Guardian, Mbappé
    will miss the match with a calf strain."
  * When source is "api-football" with no source_url, state the fact
    without press attribution. Example: "Vázquez and Pizarro are out
    for Mexico." api-football is the fact engine, not an editorial
    outlet — do not name it.

Lineup rules:
  * When lineup.state="confirmed" AND starters[] is non-empty, name
    1–2 notable starters by surname. Pick the most globally recognised
    attacker / captain / playmaker from the list — the kind of name a
    casual reader would recognise from a World Cup poster. Examples:

      "Neymar opens for Brazil; Vinicius starts on the left."
      "Mbappé leads the France XI from a 4-3-3."
      "Argentina go 4-4-2 with Messi and Lautaro Martínez up top."

    Do NOT list the full XI. One sentence, 1–2 names max.

  * When lineup.state="confirmed" but starters[] is empty (RSS-only
    confirmed signal), state the announcement without naming starters.

  * When lineup.state="confirmed" AND lineup.formation is present,
    name the formation once ("4-3-3", "3-5-2", etc.).

  * When the lineup source is "api-football" with no source_url, write
    "official lineup confirms ..." — that phrasing is allowed without
    naming a press outlet.

  * When lineup.state="predicted", you MAY mention the expected XI
    only with explicit hedging ("ESPN expects ..." with attribution).

  * When lineup.state="unknown", say nothing about formation or XI.

At-risk card rules:
  * cards[] entries with state="at_risk" are players ONE BOOKING from
    a ban. Phrase as risk, never as fact. Allowed shapes: "one yellow
    from a suspension", "a booking away from missing the next round",
    "carries one yellow into the match". Forbidden shapes: "will be
    suspended", "is banned for the next match", "out of the next round".
  * Name the player. Do not mention a card-count without naming the
    player it belongs to.
  * If the same player is in BOTH cards[] (state="at_risk") and
    absences[] (type="suspension"), the absence wins — name them as
    out, not as at-risk. The builder reconciles this for you; trust
    the payload you receive.
"""

_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Emit the three editorial fields for one match.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title":   {"type": "string", "minLength": 1, "maxLength": 120},
            "summary": {"type": "string", "minLength": 1, "maxLength": 400},
            "blurb":   {"type": "string", "minLength": 1, "maxLength": 2000},
        },
        "required": ["title", "summary", "blurb"],
    },
}


# ── prompt construction ─────────────────────────────────────────────

def _format_citations(cites: list[Citation] | None) -> str:
    """Render the citation list as a compact JSON-ish block for the prompt.

    Includes outlet, url, English quote, published date. The translated
    `quote_original` / `quote_lang` are omitted from the prompt — the
    English quote is what the blurb attributes.
    """
    cites = cites or []
    if not cites:
        return "[] (no editorial citations — source against market and model only)"
    lines = []
    for c in cites:
        pub = c.published_at.isoformat() if c.published_at else "unknown"
        # Escape backticks and trim quotes hard for prompt safety.
        quote = (c.quote or "").replace("\n", " ").strip()
        lines.append(
            f'  - outlet: {c.outlet}\n'
            f'    url: {c.url}\n'
            f'    published: {pub}\n'
            f'    quote: "{quote}"'
        )
    return "[\n" + "\n".join(lines) + "\n]"


def _pct(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p * 100:.0f}%"


def _format_team_news(news: Any, *, label: str) -> str:
    """Render a TeamNews payload as a compact YAML-ish block.

    Returns "<label>: (no data)\n" when news is None — so the prompt
    always carries the two `team_a_news` / `team_b_news` keys, just with
    a clear absence marker the model can read.
    """
    if news is None:
        return f"{label}: (no data)\n"
    absences = getattr(news, "absences", ()) or ()
    lineup = getattr(news, "lineup", None)
    materiality = getattr(news, "materiality", "none")

    lines = [
        f"{label}:",
        f"  materiality: {materiality}",
        f"  absences:",
    ]
    if not absences:
        lines.append("    [] (no players ruled out)")
    else:
        for a in absences:
            url = getattr(a, "source_url", None) or ""
            src = getattr(a, "source_name", None) or getattr(a, "source", "")
            pos = getattr(a, "position", None) or "—"
            reason = getattr(a, "reason", None) or "—"
            lines.append(
                f"    - name: {a.name}\n"
                f"      type: {a.type}\n"
                f"      position: {pos}\n"
                f"      reason: {reason}\n"
                f"      importance: {a.importance}\n"
                f"      source: {src}\n"
                f"      source_url: {url}"
            )
    cards = getattr(news, "cards", ()) or ()
    if not cards:
        lines.append("  cards:\n    [] (no at-risk players)")
    else:
        lines.append("  cards:")
        for c in cards:
            pos = getattr(c, "position", None) or "—"
            url = getattr(c, "source_url", None) or ""
            src = getattr(c, "source_name", None) or getattr(c, "source", "")
            lines.append(
                f"    - name: {c.name}\n"
                f"      state: {c.state}\n"
                f"      position: {pos}\n"
                f"      yellows: {c.yellows}\n"
                f"      importance: {c.importance}\n"
                f"      source: {src}\n"
                f"      source_url: {url}"
            )
    if lineup is None:
        lines.append("  lineup:\n    state: unknown")
    else:
        state = getattr(lineup, "state", "unknown")
        formation = getattr(lineup, "formation", None) or "—"
        coach = getattr(lineup, "coach", None) or "—"
        src = getattr(lineup, "source_name", None) or getattr(lineup, "source", None) or "—"
        url = getattr(lineup, "source_url", None) or ""
        starters = getattr(lineup, "starters", ()) or ()
        # Render starters as a flat list — Haiku reads names left-to-right.
        if starters:
            starters_str = ", ".join(str(s) for s in starters)
        else:
            starters_str = "[] (no starters listed)"
        lines.append(
            f"  lineup:\n"
            f"    state: {state}\n"
            f"    formation: {formation}\n"
            f"    coach: {coach}\n"
            f"    starters: {starters_str}\n"
            f"    source: {src}\n"
            f"    source_url: {url}"
        )
    return "\n".join(lines) + "\n"


def build_user_message(i: Inputs) -> str:
    """Render the match context as the per-match user message.

    Kept stable + structured so prompt caching on the system prompt
    yields the maximum hit rate. Per-match content varies; system stays
    constant.
    """
    a = i.get("team_a", "?")
    b = i.get("team_b", "?")
    state = (i.get("state") or "").lower()
    side = i.get("side") or "—"
    edge = i.get("edge_pp")
    price = i.get("price") or "—"
    venue = i.get("market_venue") or "—"
    competition = i.get("competition") or "—"
    kickoff = i.get("kickoff_utc") or "—"
    venue_city = i.get("venue_city") or "—"
    venue_stadium = i.get("venue_stadium") or "—"
    venue_country = i.get("venue_country") or "—"

    cites = i.get("editorial_citations") or []

    bounds_a = ""
    if i.get("model_p_a_lower") is not None and i.get("model_p_a_upper") is not None:
        bounds_a = f" (95% CI {_pct(i['model_p_a_lower'])}-{_pct(i['model_p_a_upper'])})"
    bounds_b = ""
    if i.get("model_p_b_lower") is not None and i.get("model_p_b_upper") is not None:
        bounds_b = f" (95% CI {_pct(i['model_p_b_lower'])}-{_pct(i['model_p_b_upper'])})"

    edge_str = f"{edge:+.1f}pp" if edge is not None else "—"

    return (
        f"match: {a} v {b}\n"
        f"competition: {competition}\n"
        f"kickoff (UTC): {kickoff}\n"
        f"venue: {venue_stadium}, {venue_city} ({venue_country})\n"
        f"\n"
        f"verdict: {state.upper()}"
        f"{f' · side {side}' if side and side != '—' else ''}"
        f" · edge {edge_str}"
        f"{f' · best price {price} on {venue}' if price and price != '—' else ''}\n"
        f"\n"
        f"model probabilities:\n"
        f"  {a}: {_pct(i.get('model_p_a'))}{bounds_a}\n"
        f"  draw: {_pct(i.get('model_p_draw'))}\n"
        f"  {b}: {_pct(i.get('model_p_b'))}{bounds_b}\n"
        f"\n"
        f"market probabilities (closing):\n"
        f"  {a}: {_pct(i.get('market_p_a'))}\n"
        f"  draw: {_pct(i.get('market_p_draw'))}\n"
        f"  {b}: {_pct(i.get('market_p_b'))}\n"
        f"\n"
        f"model internals (do not quote verbatim; use as context):\n"
        f"  {a} Elo: {i.get('team_a_elo') or '—'} (source: {i.get('team_a_elo_source') or '—'})\n"
        f"  {b} Elo: {i.get('team_b_elo') or '—'} (source: {i.get('team_b_elo_source') or '—'})\n"
        f"  adjusted: {a} {i.get('elo_a_adj') or '—'}, {b} {i.get('elo_b_adj') or '—'}\n"
        f"\n"
        f"editorial_citations (the ONLY outlets you may attribute):\n"
        f"{_format_citations(cites)}\n"
        f"\n"
        f"{_format_team_news(i.get('team_a_news'), label=f'team_a_news ({a})')}"
        f"{_format_team_news(i.get('team_b_news'), label=f'team_b_news ({b})')}"
    )


def build_messages(i: Inputs) -> tuple[list[dict], list[dict]]:
    """Return (system_blocks, messages) for an Anthropic call."""
    system_blocks = [{
        "type": "text",
        "text": _SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]
    messages = [{"role": "user", "content": build_user_message(i)}]
    return system_blocks, messages


# ── response parsing ────────────────────────────────────────────────

def parse_tool_use(response: Any) -> dict[str, str] | None:
    """Pull the `write_blurb` tool input. Returns None when missing or
    when required fields are absent / empty."""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            payload = getattr(block, "input", None) or {}
            title = (payload.get("title") or "").strip()
            summary = (payload.get("summary") or "").strip()
            blurb = (payload.get("blurb") or "").strip()
            if not (title and summary and blurb):
                return None
            return {"title": title, "summary": summary, "blurb": blurb}
    return None


# ── post-checks ─────────────────────────────────────────────────────

def _word_count(s: str) -> int:
    return len(s.split())


def _allowed_outlets(cites: list[Citation] | None) -> set[str]:
    """Outlet names the blurb may attribute. Lowercased + stripped."""
    out: set[str] = set()
    for c in cites or []:
        if c.outlet:
            out.add(c.outlet.strip().lower())
            # Also accept a common short form — drop trailing parenthetical
            # qualifiers, e.g. "The Guardian (football)" → "the guardian".
            base = c.outlet.split("(")[0].strip().lower()
            if base:
                out.add(base)
    return out


# Heuristic: any "X reported", "per X", "according to X" / "X added" /
# "X carried" / "X noted" attribution. We extract the X and check it
# against the allowlist. Pattern is permissive — false positives prefer
# stub fallback over shipping an invented outlet.
import re as _re

_ATTRIBUTION_RE = _re.compile(
    r"\b(?:per|according to|from)\s+([A-Z][A-Za-z0-9 &.'\-]{1,50}?)(?=[:,.\s])"
    r"|([A-Z][A-Za-z0-9 &.'\-]{1,50}?)\s+(?:reported|added|carried|noted|wrote)\b",
)


def _attribution_outlets(text: str) -> list[str]:
    """Best-effort outlet names extracted from attribution patterns."""
    out: list[str] = []
    for m in _ATTRIBUTION_RE.finditer(text):
        name = (m.group(1) or m.group(2) or "").strip()
        if name:
            out.append(name.lower())
    return out


def _attributions_are_allowed(blurb: str, cites: list[Citation] | None) -> bool:
    """Every attribution in the blurb must name a known outlet.

    No citations at all → blurb must contain no attribution patterns,
    matching VOICE.md's "When no editorial source exists" guidance.
    """
    found = _attribution_outlets(blurb)
    if not found:
        return True
    allowed = _allowed_outlets(cites)
    if not allowed:
        # Attribution claims with no citations available — reject.
        return False
    for name in found:
        # Substring match either way so partial outlet shorthand works
        # (e.g. "BBC" matches "BBC Sport"; "The Guardian" matches "The
        # Guardian (football)").
        if not any(name in a or a in name for a in allowed):
            return False
    return True


# Negative-availability CLAIM patterns. Used by the materiality=none
# guard to catch fabricated injury/suspension/card claims while still
# allowing the positive "squad is clean" sentence the prompt mandates
# in the no-data case.
#
# Rule: the guard rejects only phrasings that commit to a specific
# negative state ("X is injured", "ruled out", "out with a knock",
# "one yellow from a ban"). Generic vocabulary ("no flagged absences",
# "no availability concerns", "at full strength") is allowed — those
# are the positive sentences the prompt asks Haiku to write when there
# are no absences, no at-risk cards, and no confirmed XI on either side.
_NEGATIVE_AVAILABILITY_CLAIMS = (
    r"\bis\s+(?:out|injured|suspended|sidelined|unavailable|absent|missing|ruled\s+out)\b",
    r"\bare\s+(?:out|injured|suspended|sidelined|unavailable|absent|missing)\b",
    r"\bruled\s+out\b",
    r"\bout\s+(?:with|for|of\s+the\s+(?:squad|matchday|lineup|line[- ]?up|fixture|game|match))\b",
    r"\bmissing\s+the\s+(?:match|fixture|game)\b",
    r"\bsidelined\s+(?:with|by|for)\b",
    # at-risk / card-status claims when no cards data was supplied
    r"\bone\s+(?:booking|yellow)\s+(?:from|away)\b",
    r"\bat[\s-]risk\s+of\s+(?:a\s+)?(?:ban|suspension)\b",
    r"\bcarries\s+(?:a|one)\s+yellow\b",
    r"\byellow\s+accumulation\b",
)
_NEGATIVE_AVAILABILITY_CLAIM_RE = _re.compile(
    "|".join(_NEGATIVE_AVAILABILITY_CLAIMS), _re.IGNORECASE,
)

# Words that present a player as a confirmed absence (ban / suspension).
# Used by the Q3 at-risk guard: an at-risk player named in the blurb
# must NOT appear within `_AT_RISK_BAN_PROXIMITY` tokens of any of
# these — otherwise the blurb is presenting risk as fact.
_BAN_PROXIMITY_WORDS = (
    "suspended", "suspension", "banned", "ban", "missing",
    "ruled out", "out of",
)
_AT_RISK_BAN_PROXIMITY = 6   # words on either side of the player name


def _names_from(news: Any) -> list[str]:
    """Lowercased absence-player names from a TeamNews payload."""
    if news is None:
        return []
    out: list[str] = []
    for a in getattr(news, "absences", ()) or ():
        n = (getattr(a, "name", "") or "").strip().lower()
        if n:
            out.append(n)
    return out


def _card_names_from(news: Any) -> list[str]:
    """Lowercased at-risk player names from a TeamNews payload."""
    if news is None:
        return []
    out: list[str] = []
    for c in getattr(news, "cards", ()) or ():
        n = (getattr(c, "name", "") or "").strip().lower()
        if n:
            out.append(n)
    return out


def _has_squad_content(news: Any) -> bool:
    """True when a side has anything that triggers the squad paragraph:
    a confirmed lineup, an absence, or an at-risk card."""
    if news is None:
        return False
    if (getattr(news, "absences", ()) or ()):
        return True
    if (getattr(news, "cards", ()) or ()):
        return True
    lu = getattr(news, "lineup", None)
    state = getattr(lu, "state", "unknown") or "unknown"
    if state == "confirmed":
        return True
    return False


def _at_risk_player_presented_as_banned(
    blurb: str, at_risk_names: list[str],
) -> bool:
    """Q3 spec: an at-risk player named in the blurb must NOT appear
    within `_AT_RISK_BAN_PROXIMITY` words of a ban / suspension word.
    Returns True when a violation is detected.

    Approximation: tokenise the blurb on whitespace + lowercase, scan
    for each at-risk surname (or full name), and inspect the surrounding
    window for the ban keywords. False positives prefer fall-back over
    shipping a wrong claim — strict mode rejects, soft mode warns.
    """
    if not at_risk_names:
        return False
    tokens = [t.strip(".,;:'\"()[]") for t in blurb.lower().split()]
    if not tokens:
        return False
    ban_words = set()
    for w in _BAN_PROXIMITY_WORDS:
        # Single word entries go in directly; multi-word entries get
        # joined back during proximity checks (rare here — only
        # "ruled out" / "out of"). For the simple set we only need
        # the leading token to flag the window.
        ban_words.add(w.split()[0])
    for name in at_risk_names:
        # Match either full name or surname (last meaningful token).
        surname_tokens = [t for t in name.split() if len(t) >= 3]
        candidates = [name]
        if surname_tokens:
            candidates.append(surname_tokens[-1])
        candidates = [c for c in candidates if c]
        for idx, tok in enumerate(tokens):
            if not any(c == tok or (len(c) > 3 and c in tok) for c in candidates):
                continue
            lo = max(0, idx - _AT_RISK_BAN_PROXIMITY)
            hi = min(len(tokens), idx + _AT_RISK_BAN_PROXIMITY + 1)
            window = tokens[lo:hi]
            if any(w in ban_words for w in window):
                return True
    return False


def _name_appears_in(blurb: str, names: list[str]) -> bool:
    """True if any absence name (or its last-word surname) appears in blurb.

    Case-insensitive. Sub-name match handles "Mbappé" vs "Kylian Mbappé"
    by also looking for the last token of each name. Player names
    almost always survive Haiku's prose without modification.
    """
    if not names:
        return False
    lowered = blurb.lower()
    for n in names:
        if n in lowered:
            return True
        # Surname-only fallback — covers "Mbappé" → matched on full
        # name "Kylian Mbappé", and vice versa.
        tokens = [t for t in n.split() if len(t) >= 3]
        if tokens and tokens[-1] in lowered:
            return True
    return False


def _materiality_of(news: Any) -> str:
    return getattr(news, "materiality", "none") or "none"


def _lineup_state_of(news: Any) -> str:
    lu = getattr(news, "lineup", None)
    return getattr(lu, "state", "unknown") or "unknown"


def post_check(
    fields: dict[str, str],
    *,
    cites: list[Citation] | None,
    team_a_news: Any = None,
    team_b_news: Any = None,
    enforce_team_news: bool | None = None,
) -> bool:
    """Return True only when every guard passes.

    Team-news guards (Slice A of THE_DESK_TEAM_NEWS_BLURB_SPEC):

      * materiality=high → blurb must mention at least one absent
        player name from that side. Failure → fall back to stub.
      * lineup.state="confirmed" → blurb must mention "lineup" or the
        formation OR a named change. Soft until N3 ships real formations.
      * materiality=none on BOTH sides → blurb must NOT contain
        availability keywords. Prevents Haiku hallucinating injuries.

    The `enforce_team_news` knob ships the new guards as warnings-only
    when False (default behaviour driven by env so the operator can
    flip to strict after eyeballing). When env var
    `DESK_TEAM_NEWS_BLURB_REQUIRED=1`, guards are hard.
    """
    title, summary, blurb = fields["title"], fields["summary"], fields["blurb"]
    for f in (title, summary, blurb):
        if not is_voice_clean(f):
            return False
    # Q3 squad-paragraph: a side with squad content earns +20 words of
    # headroom so the dedicated paragraph doesn't push the verdict
    # prose into the floor.
    max_words = (
        _BLURB_MAX_WORDS_WITH_SQUAD
        if _has_squad_content(team_a_news) or _has_squad_content(team_b_news)
        else _BLURB_MAX_WORDS
    )
    wc = _word_count(blurb)
    if wc < _BLURB_MIN_WORDS or wc > max_words:
        _LOG.debug("blurb word count %d outside [%d, %d]",
                   wc, _BLURB_MIN_WORDS, max_words)
        return False
    if not _attributions_are_allowed(blurb, cites):
        _LOG.debug("blurb attribution names an outlet not in editorial_citations")
        return False

    # ── Team-news guards ────────────────────────────────────────────
    if enforce_team_news is None:
        enforce_team_news = os.getenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "0") == "1"

    mat_a = _materiality_of(team_a_news)
    mat_b = _materiality_of(team_b_news)
    lineup_a = _lineup_state_of(team_a_news)
    lineup_b = _lineup_state_of(team_b_news)

    # materiality=high → blurb must name an absent player from that side.
    if mat_a == "high":
        if not _name_appears_in(blurb, _names_from(team_a_news)):
            _LOG.warning("team_a materiality=high but blurb names no absent player")
            if enforce_team_news:
                return False
    if mat_b == "high":
        if not _name_appears_in(blurb, _names_from(team_b_news)):
            _LOG.warning("team_b materiality=high but blurb names no absent player")
            if enforce_team_news:
                return False

    # materiality=none on BOTH sides → the prompt now mandates ONE
    # positive squad sentence ("squad picture is clean", etc.). The
    # guard rejects only NEGATIVE claims — phrasings that commit to a
    # specific player being out, injured, suspended, or one card from
    # a ban. Generic vocabulary ("no flagged absences") is allowed.
    if mat_a == "none" and mat_b == "none":
        if _NEGATIVE_AVAILABILITY_CLAIM_RE.search(blurb):
            _LOG.warning("blurb makes a negative availability claim but both sides have materiality=none")
            if enforce_team_news:
                return False

    # Q3 squad-paragraph: an at-risk player named in the blurb must be
    # phrased as risk, not as a confirmed ban. Approximation: if any
    # at-risk name appears within `_AT_RISK_BAN_PROXIMITY` words of a
    # ban / suspension keyword, that's a violation.
    for side_label, news in (
        ("team_a", team_a_news), ("team_b", team_b_news),
    ):
        at_risk_names = _card_names_from(news)
        if not at_risk_names:
            continue
        if _at_risk_player_presented_as_banned(blurb, at_risk_names):
            _LOG.warning(
                "%s at-risk player presented as banned/suspended in blurb",
                side_label,
            )
            if enforce_team_news:
                return False

    # confirmed lineup with starters[] non-empty → blurb must mention
    # at least one starter or the formation/lineup hook word. Soft by
    # default; strict mode rejects on miss.
    for side_label, news, state in (
        ("team_a", team_a_news, lineup_a),
        ("team_b", team_b_news, lineup_b),
    ):
        if state != "confirmed":
            continue
        lineup_obj = getattr(news, "lineup", None)
        starters = getattr(lineup_obj, "starters", ()) or ()
        formation = getattr(lineup_obj, "formation", None)
        if not starters and not formation:
            continue
        names_ok = _name_appears_in(blurb, [s.lower() for s in starters])
        hook_ok = bool(_re.search(
            r"\b(lineup|formation|starting (?:xi|eleven)|line-up|opens? for|starts? for)\b",
            blurb, _re.IGNORECASE,
        ))
        if not (names_ok or hook_ok):
            _LOG.warning(
                "%s confirmed lineup present but blurb does not name a "
                "starter or mention the formation", side_label,
            )
            if enforce_team_news:
                return False

    return True


# ── extractor interface ─────────────────────────────────────────────

class BlurbExtractor(Protocol):
    """The boundary between this module and the LLM. Tests inject a fake."""

    def write_raw(self, i: Inputs) -> dict[str, str] | None:
        """Return the raw {title, summary, blurb} dict, or None on failure."""


class AnthropicBlurbWriter:
    """Real Claude Haiku writer. Lazy-imports `anthropic` so test code
    without the SDK doesn't fail at import."""

    def __init__(self, *, model: str = DEFAULT_MODEL, api_key: str | None = None):
        import anthropic  # local — keep this out of test imports
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model

    def write_raw(self, i: Inputs) -> dict[str, str] | None:
        system_blocks, messages = build_messages(i)
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system_blocks,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=messages,
                timeout=_TIMEOUT_SECONDS,
            )
        except Exception as e:  # noqa: BLE001 — any SDK / network error → fall back
            _LOG.warning("haiku blurb call failed: %s", e)
            return None
        try:
            from desk.ops.cost import log_call
            log_call(model=self._model, usage=getattr(resp, "usage", None),
                     caller="explainer.blurb")
        except Exception:                                  # noqa: BLE001
            pass
        return parse_tool_use(resp)


# ── public API ──────────────────────────────────────────────────────

def haiku_enabled() -> bool:
    """Gate read by `__init__.build_copy`. Both env vars must be set."""
    if os.getenv("DESK_BLURB_HAIKU", "0") != "1":
        return False
    if not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        return False
    return True


def _make_default_extractor() -> BlurbExtractor | None:
    """Construct the real Anthropic writer. Returns None when the SDK
    isn't installed (kept conservative — caller falls back to stub)."""
    try:
        model = os.getenv("DESK_BLURB_HAIKU_MODEL") or DEFAULT_MODEL
        return AnthropicBlurbWriter(model=model)
    except Exception as e:  # noqa: BLE001
        _LOG.warning("could not construct Haiku blurb writer: %s", e)
        return None


def try_haiku_copy(
    i: Inputs,
    *,
    extractor: BlurbExtractor | None = None,
) -> Copy | None:
    """Try to produce a {title, summary, blurb} Copy via Haiku.

    Returns None on any failure (no extractor, malformed response,
    voice-check fail, word-count fail, attribution to an unknown
    outlet). Caller keeps the templated copy.

    `drivers` and `citations` are left empty here — the dispatcher in
    `__init__.build_copy` merges Haiku's prose fields over the stub's
    Copy, which already carries those.
    """
    if extractor is None:
        extractor = _make_default_extractor()
    if extractor is None:
        return None

    raw = extractor.write_raw(i)
    if raw is None:
        return None

    if not post_check(
        raw,
        cites=i.get("editorial_citations"),
        team_a_news=i.get("team_a_news"),
        team_b_news=i.get("team_b_news"),
    ):
        return None

    return Copy(
        title=raw["title"],
        summary=raw["summary"],
        blurb=raw["blurb"],
    )
