"""LLM-based signal extraction.

For each cached `SourceItem`, we ask Claude Haiku to identify
structured football signals (injury, suspension, lineup, morale,
manager quote, form, other) and emit them via a forced tool call.

The extractor's job is identification only. It does NOT decide which
track the signal lands on — that's `Signal.track()` in `models.py`,
which applies the source's trust gate. A biased outlet can identify a
real injury; the source gate keeps it out of the model.

Guarantees we enforce on the way back from the LLM:
  * Engine sets `source_id`, `url`, `published_at`. The LLM never picks
    those — too easy to drift if it does.
  * The `quote` (or `quote_original`, if translated) must appear in the
    article text. The citation guarantee in §8 of the news-signals spec
    rests on this — "according to local press…" must point at a real,
    fetchable line. We drop any signal that fails.
  * Extractions are cached by `(source_id, canonical_url, extractor_id)`
    against the item's `content_hash`. If the item gets re-fetched and
    edited, the hash changes and we re-extract.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from desk.signals.cache import SignalsCache
from desk.signals.models import Signal, SignalType, Source, SourceItem

_LOG = logging.getLogger(__name__)

# Default Claude Haiku model. Override via env or constructor arg.
DEFAULT_MODEL = "claude-haiku-4-5"
EXTRACTOR_PREFIX = "anthropic:"
_TOOL_NAME = "emit_signals"
_MAX_TOKENS = 2000


# ── public interfaces ────────────────────────────────────────────────

class Extractor(Protocol):
    """The boundary between this module and an LLM. Tests inject a fake."""

    @property
    def id(self) -> str: ...

    def extract_raw(self, *, item: SourceItem, source: Source) -> list[dict[str, Any]]:
        """Return raw signal payloads (only the LLM-filled fields)."""


@dataclass(frozen=True)
class ExtractionOutcome:
    source_id:     str
    canonical_url: str
    status:        str   # extracted / cached / dropped_invalid / dropped_empty / error
    new_signals:   int = 0
    error:         str | None = None


# ── prompt + response ────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You extract structured football news signals from one article at a time.

Output via the `emit_signals` tool. Allowed signal types:
  injury            — a named player is unavailable due to injury
  suspension        — a named player is unavailable due to suspension or ban
  confirmed_lineup  — the starting XI has been officially announced
  predicted_lineup  — speculation about the XI, not an official announcement
  morale            — squad mood / pressure / training-ground reports
  manager_quote     — a direct quote from the head coach / manager
  form              — narrative about recent results or performance
  other             — anything else worth recording

Rules — read them all before you start:
1. Only extract claims clearly supported by the article. No inference, no \
filling in. If the article is a transfer rumour, a ticketing notice, or an \
opinion column with no factual claims, return `{"signals": []}`.
2. The `quote` field MUST be a sentence copied character-for-character from \
the article. Verbatim. If you cannot find a supporting sentence, drop the \
signal. The downstream pipeline cites this quote to readers; it must be real.
3. For non-English articles, set `quote` to a faithful English translation, \
copy the original sentence into `quote_original`, and set `quote_lang` to \
the article's ISO-639-1 code (e.g. `es`, `pt`, `fr`).
4. Use `confirmed_lineup` ONLY when the article explicitly says the XI has \
been confirmed / announced / officially named. Anything speculative is \
`predicted_lineup`.
5. `team` is the team the signal is about, as it appears in the article. \
Don't normalise — the engine maps team names to IDs downstream.
6. `claim` is one short sentence, normalised, English. Engine-side.
7. `confidence` is your self-rated extraction confidence (0.0–1.0). It is \
NOT the source's reliability — that's a separate field on the source.
"""

# The tool schema enforces the JSON shape — the model can't ad-lib here.
_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Emit the structured signals extracted from the article.",
    "input_schema": {
        "type": "object",
        "properties": {
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [t.value for t in SignalType],
                        },
                        "team":           {"type": "string", "minLength": 1},
                        "claim":          {"type": "string", "minLength": 1},
                        "quote":          {"type": "string", "minLength": 1},
                        "quote_original": {"type": "string"},
                        "quote_lang":     {"type": "string"},
                        "confidence":     {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["type", "team", "claim", "quote", "confidence"],
                },
            },
        },
        "required": ["signals"],
    },
}


def build_messages(item: SourceItem, source: Source) -> tuple[list[dict], list[dict]]:
    """Build (system_blocks, messages) for an Anthropic `messages.create` call.

    The system prompt is marked `cache_control: ephemeral` so a batch
    extraction run amortises its input-token cost across calls.
    """
    user_text = (
        f"Source: {source.name} (language: {source.language}, "
        f"reliability: {source.reliability}, bias: {source.bias_flag})\n"
        f"Article URL: {item.url}\n"
        f"Published: {item.published_at.isoformat() if item.published_at else 'unknown'}\n"
        f"\n"
        f"Title: {item.title}\n"
        f"\n"
        f"Body:\n{item.body}"
    )
    system_blocks = [{
        "type": "text",
        "text": _SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]
    messages = [{"role": "user", "content": user_text}]
    return system_blocks, messages


def parse_tool_use(response: Any) -> list[dict[str, Any]]:
    """Pull the `emit_signals` tool input out of an Anthropic response.

    Tolerant — if the model returned text instead (it shouldn't, since
    we force the tool), or no signals key, returns []."""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            payload = getattr(block, "input", None) or {}
            return list(payload.get("signals", []) or [])
    return []


# ── validation + Signal construction ─────────────────────────────────

def _quote_is_in_article(quote: str, item: SourceItem) -> bool:
    """Citation guarantee: the quote must be findable in the article text.
    We compare whitespace-collapsed strings to allow for line-wrapping
    differences between the feed body and what the LLM reads."""
    if not quote:
        return False
    needle  = " ".join(quote.split())
    hay     = " ".join(f"{item.title}\n{item.body}".split())
    return needle in hay


def _build_signal(raw: dict[str, Any], item: SourceItem, source: Source) -> Signal | None:
    """Construct a `Signal` from LLM-emitted fields + engine-side fields.
    Returns None when the signal fails the citation guarantee."""
    # The forced tool_use schema *should* always give us a dict per
    # signal, but Haiku occasionally emits a list-of-strings when the
    # article gives it nothing to chew on. Defensive skip so a single
    # mis-typed payload doesn't kill the whole extraction batch.
    if not isinstance(raw, dict):
        _LOG.debug(
            "drop signal: non-dict payload %r  source=%s url=%s",
            type(raw).__name__, source.id, item.canonical_url,
        )
        return None
    quote_for_check = raw.get("quote_original") or raw.get("quote") or ""
    if not _quote_is_in_article(quote_for_check, item):
        _LOG.debug(
            "drop signal: quote not in article  source=%s url=%s",
            source.id, item.canonical_url,
        )
        return None
    try:
        return Signal(
            type=SignalType(raw["type"]),
            team=raw["team"],
            claim=raw["claim"],
            quote=raw["quote"],
            quote_original=raw.get("quote_original"),
            quote_lang=raw.get("quote_lang"),
            source_id=source.id,
            url=item.url,
            published_at=item.published_at,
            confidence=float(raw["confidence"]),
        )
    except (KeyError, ValueError) as e:
        _LOG.debug("drop signal: invalid payload %s — %s", raw, e)
        return None


def extract_item(
    item: SourceItem, source: Source, *, extractor: Extractor,
) -> list[Signal]:
    """One-item extraction. No caching here — caller handles the cache.

    The source.id / item must agree; otherwise we'd be mis-tagging the
    Signal's source_id and the trust gate would route wrongly."""
    if item.source_id != source.id:
        raise ValueError(
            f"extract_item: item.source_id={item.source_id!r} but "
            f"source.id={source.id!r}"
        )
    raws = extractor.extract_raw(item=item, source=source)
    out = [s for s in (_build_signal(r, item, source) for r in raws) if s is not None]
    return out


# ── AnthropicExtractor (real) ────────────────────────────────────────

class AnthropicExtractor:
    """Real Claude Haiku extractor. Lazy-imports `anthropic` so test code
    without the API key / SDK doesn't fail at module import."""

    def __init__(self, *, model: str = DEFAULT_MODEL, api_key: str | None = None):
        import anthropic  # local — keep this out of test imports
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model

    @property
    def id(self) -> str:
        return f"{EXTRACTOR_PREFIX}{self._model}"

    def extract_raw(self, *, item: SourceItem, source: Source) -> list[dict[str, Any]]:
        system_blocks, messages = build_messages(item, source)
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system_blocks,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=messages,
        )
        return parse_tool_use(resp)


# ── runner ──────────────────────────────────────────────────────────

def extract_all(
    cache: SignalsCache,
    *,
    extractor: Extractor,
    source_ids: Iterable[str] | None = None,
    limit_per_source: int | None = None,
    now: datetime | None = None,
) -> list[ExtractionOutcome]:
    """Walk the cache and extract any items we don't yet have signals for.

    Cache hit when `(source_id, canonical_url, extractor_id)` already has
    a row AND its `content_hash` matches the current item. Otherwise we
    extract and (re-)write.
    """
    now = now or datetime.now(tz=timezone.utc)
    wanted = set(source_ids) if source_ids is not None else None
    outcomes: list[ExtractionOutcome] = []

    items_by_source: dict[str, list[SourceItem]] = {}
    for item in cache.list_items():
        if wanted is not None and item.source_id not in wanted:
            continue
        items_by_source.setdefault(item.source_id, []).append(item)

    for sid, items in items_by_source.items():
        if limit_per_source is not None:
            items = items[:limit_per_source]
        # We need the Source record to call the extractor. Items are
        # keyed by source_id but the LLM prompt wants language / name /
        # reliability / bias. Caller hasn't passed the registry — fetch
        # via the cached item's source_id from the registry the runner
        # holds. To keep this function loose, we accept any source we
        # can build a stub for from cached data. Real callers (the CLI)
        # pass a fully-populated registry via _resolve_source below.
        source = _resolve_source(sid)
        if source is None:
            outcomes.append(ExtractionOutcome(
                sid, "", "error",
                error=f"source {sid!r} not in registry",
            ))
            continue
        for item in items:
            outcomes.append(_extract_one(item, source, cache, extractor, now))
    return outcomes


def _extract_one(
    item: SourceItem, source: Source, cache: SignalsCache,
    extractor: Extractor, now: datetime,
) -> ExtractionOutcome:
    cached = cache.cached_signals(
        source_id=source.id, canonical_url=item.canonical_url,
        content_hash=item.content_hash, extractor_id=extractor.id,
    )
    if cached is not None:
        return ExtractionOutcome(
            source.id, item.canonical_url, "cached", new_signals=len(cached),
        )
    try:
        signals = extract_item(item, source, extractor=extractor)
    except Exception as e:  # noqa: BLE001
        _LOG.warning("extract failed: source=%s url=%s err=%s",
                     source.id, item.canonical_url, e)
        return ExtractionOutcome(
            source.id, item.canonical_url, "error", error=str(e),
        )
    if not signals:
        cache.cache_signals(
            source_id=source.id, canonical_url=item.canonical_url,
            content_hash=item.content_hash, extractor_id=extractor.id,
            signals=[], extracted_at=now,
        )
        return ExtractionOutcome(
            source.id, item.canonical_url, "dropped_empty",
        )
    cache.cache_signals(
        source_id=source.id, canonical_url=item.canonical_url,
        content_hash=item.content_hash, extractor_id=extractor.id,
        signals=signals, extracted_at=now,
    )
    return ExtractionOutcome(
        source.id, item.canonical_url, "extracted", new_signals=len(signals),
    )


def _resolve_source(source_id: str) -> Source | None:
    """Look up a source from the shipped registry. Kept private so
    callers can override (e.g. tests) by injecting via fakes higher up."""
    from desk.signals.registry import Registry
    try:
        return Registry.from_csv().get(source_id)
    except (KeyError, FileNotFoundError):
        return None
