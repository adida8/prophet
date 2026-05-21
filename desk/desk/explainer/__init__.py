"""Explainer — produces the contract's `copy.title / summary / blurb`.

Two writers ship side-by-side:

  * `stub.build_copy` — deterministic templated copy. Always-safe
    fallback; runs offline; produces the `drivers` list and the
    `_press_chorus` sentence when news citations are present.

  * `haiku.try_haiku_copy` — PR 5. Real Anthropic Haiku writer that
    produces voice-checked prose per `desk/VOICE.md`. Gated on
    `DESK_BLURB_HAIKU=1` + `ANTHROPIC_API_KEY`. Returns `None` on any
    failure (no API key, network error, voice-check fail, word-count
    out of range, attribution to an unknown outlet).

The dispatcher below tries Haiku first when enabled; on any miss it
keeps the stub Copy verbatim. When Haiku succeeds the prose fields are
overlaid on the stub Copy and the merged Copy is voice-checked one more
time before return.
"""

from __future__ import annotations

import logging

from desk.explainer import haiku as _haiku
from desk.explainer.stub import Inputs, build_copy as _stub_build_copy
from desk.explainer.voice import is_voice_clean
from desk.publish.contract import Copy

_LOG = logging.getLogger(__name__)


def build_copy(i: Inputs) -> Copy:
    """Produce one match's Copy. Dispatches to Haiku when enabled,
    falls back to the stub on any failure."""
    fallback = _stub_build_copy(i)
    if not _haiku.haiku_enabled():
        return fallback

    overlay = _haiku.try_haiku_copy(i)
    if overlay is None:
        return fallback

    merged = fallback.model_copy(update={
        "title":   overlay.title,
        "summary": overlay.summary,
        "blurb":   overlay.blurb,
    })
    for field in (merged.title, merged.summary, merged.blurb):
        if not is_voice_clean(field):
            return fallback
    return merged


__all__ = ["build_copy", "Inputs"]
