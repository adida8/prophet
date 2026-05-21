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

from desk.signals.models import Signal, SignalType, Source, SourceItem
from desk.signals.registry import Registry
from desk.signals.resolve import sources_for

__all__ = [
    "Signal",
    "SignalType",
    "Source",
    "SourceItem",
    "Registry",
    "sources_for",
]
