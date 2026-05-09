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
    lower = (text or "").lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            raise VoiceCheckFailed(f"banned phrase {phrase!r} in copy: {text!r}")
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
