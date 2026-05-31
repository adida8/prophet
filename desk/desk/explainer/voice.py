"""Voice rules for The Desk's editorial copy.

These rules apply equally to the templated stub (PR 4.x) and to the
PR 5 Haiku output. Treat them as enforcement constants, not style
guidelines — the post-check raises if any of them is violated.

Source: `Odds Primer Design System/README.md` (CONTENT FUNDAMENTALS),
plus the trustability brief §3 Phase F (no false certainty).
"""

from __future__ import annotations

import re

# Phrases that imply certainty or sportsbook-speak. We never use them.
#
# IMPORTANT: each entry is matched with **word boundaries** by
# `assert_voice_clean`, so "bet" doesn't accidentally trigger on the
# brand names "Betfair" / "Sky Bet" (a real bug that landed in prod
# 2026-05-31 — empty Copy() shipped for every Betfair pick, and MTA
# 400'd because the wire body had no editorial fields). Brand names
# that happen to contain a banned-word substring are now safe.
BANNED_PHRASES: tuple[str, ...] = (
    "bet",
    "back the",
    "lock",
    "lock in",
    "free bet",
    "boost",
    "smart money",
    "no-brainer",
    "destined",
    "will win",
    "is set to",
    "is going to win",
    "guaranteed",
    "cash in",
    "buy now",
)

# Build the compiled regex once. Each phrase is wrapped in `\b…\b` so
# "bet" matches "place a bet" but NOT "Betfair". Multi-word phrases
# (e.g. "back the") preserve their literal space; the bounding `\b`
# still works at each end.
_BANNED_PHRASE_RE = re.compile(
    "|".join(r"\b" + re.escape(p) + r"\b" for p in BANNED_PHRASES),
    flags=re.IGNORECASE,
)

# Brand names that contain a banned-word as a SEPARATE token (e.g.
# "Sky Bet"). Word boundaries can't distinguish brand from gambling-
# speak when the banned word is a whole token — `\bbet\b` matches
# both "place a bet" and "Sky Bet". We pre-strip these brand names
# from the text before running the regex so "Sky Bet" passes but
# "place a bet on Mexico" still fails.
#
# Order matters: longer strings first so "Betfair Exchange" replaces
# before the regex sees "Betfair". Case-insensitive replacement.
_SAFE_BRAND_NAMES: tuple[str, ...] = (
    "Betfair Exchange (UK)",
    "Betfair Exchange (EU)",
    "Betfair Exchange",
    "Betfair_Ex_Uk",
    "Betfair_Ex_Eu",
    "Betfair",
    "Sky Bet",
    "Skybet",
)
_SAFE_BRAND_RE = re.compile(
    "|".join(re.escape(n) for n in _SAFE_BRAND_NAMES),
    flags=re.IGNORECASE,
)


def _strip_safe_brands(text: str) -> str:
    """Remove venue brand names from `text` before voice-checking so
    'Sky Bet' / 'Betfair' don't trip the 'bet' rule."""
    return _SAFE_BRAND_RE.sub(" ", text)

# Patterns that indicate an exclamation point or emoji codepoint.
_EXCLAMATION_RE = re.compile(r"!")
_EMOJI_RE       = re.compile(
    "[\U0001F300-\U0001FAFF"     # Misc symbols / pictographs / supplemental
    "\U0001F600-\U0001F64F"      # Emoticons
    "\U00002702-\U000027B0"      # Dingbats
    "☀-⛿"              # Misc symbols (sun/moon/etc)
    "]",
    flags=re.UNICODE,
)


class VoiceCheckFailed(ValueError):
    """Raised when generated copy violates the editorial voice rules."""


def assert_voice_clean(text: str) -> None:
    """Reject text that breaks any of the banned-phrase or formatting
    rules. Caller wraps with try/except to fall back to a safe stub.
    """
    text = text or ""
    # Strip safe brand names FIRST so 'Sky Bet' / 'Betfair' don't
    # match the 'bet' rule. The banned-phrase regex runs against the
    # stripped text; exclamation/emoji checks run against the original
    # (brand names don't contain those).
    stripped = _strip_safe_brands(text)
    m = _BANNED_PHRASE_RE.search(stripped)
    if m is not None:
        raise VoiceCheckFailed(
            f"banned phrase {m.group(0)!r} in copy: {text!r}"
        )
    if _EXCLAMATION_RE.search(text):
        raise VoiceCheckFailed(f"exclamation mark in copy: {text!r}")
    if _EMOJI_RE.search(text):
        raise VoiceCheckFailed(f"emoji in copy: {text!r}")


def is_voice_clean(text: str) -> bool:
    try:
        assert_voice_clean(text)
        return True
    except VoiceCheckFailed:
        return False
