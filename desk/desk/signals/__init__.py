"""News & editorial signals subsystem (sport-agnostic).

The Desk reads a registry of sources, resolves which ones cover a given
fixture, fetches their items, extracts structured `Signal`s, and routes
each signal down one of two tracks:

  * Hard signals (injuries / suspensions / confirmed XI from a high-trust
    source) → model features.
  * Editorial signals (everything else, plus anything from a biased or
    long-tail source) → copy.citations on the published blurb.

The track a signal lands on is decided by its *source*'s trust gate
(`Source.can_feed_model`), never by the extractor — biased outlets can
still be factually accurate, so they're quoted at high reliability while
barred from the model.

This package is sport-agnostic and never imports from `desk/sports/*`.
The mapping of hard signals to sport-specific features lives in each
sport package.
"""

# Re-export the core types only. Callers needing the runners
# (`fetch_all`, `extract_all`) should import from the submodules to
# keep the two namespaces unambiguous.
from desk.signals.cache import SignalsCache
from desk.signals.canonical import canonical_url
from desk.signals.extract import (
    AnthropicExtractor,
    ExtractionOutcome,
    Extractor,
    extract_item,
)
from desk.signals.fetch import FetchOutcome, fetch_source
from desk.signals.models import Signal, SignalType, Source, SourceItem
from desk.signals.parse import parse_feed
from desk.signals.registry import Registry
from desk.signals.resolve import sources_for

__all__ = [
    "Signal",
    "SignalType",
    "Source",
    "SourceItem",
    "Registry",
    "sources_for",
    "canonical_url",
    "parse_feed",
    "SignalsCache",
    "FetchOutcome",
    "fetch_source",
    "Extractor",
    "ExtractionOutcome",
    "AnthropicExtractor",
    "extract_item",
]
