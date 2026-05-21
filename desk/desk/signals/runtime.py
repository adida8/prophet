"""Runtime helper that wires news-signals into a `desk run`.

Owns the *optional, conditional* behaviour. If the signals cache file
exists, the runner opens it for the duration of the pass and asks for
editorial citations per fixture. If not, the runner does nothing
signals-related — the engine still runs end-to-end on a fresh clone
with no extractions.

The conditional shape keeps news-signals additive: same code path,
same contract, richer output when the operator has populated the
cache (via `desk fetch-signals` + `desk extract-signals`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from desk.publish.contract import Citation
from desk.signals.cache import SignalsCache
from desk.signals.editorial import build_citations
from desk.signals.hard_track import hard_signals_for
from desk.signals.models import Signal, Source
from desk.signals.registry import Registry

log = logging.getLogger("desk.signals.runtime")

DEFAULT_CACHE_PATH = Path("desk/data/signals.db")


class SignalsRuntime:
    """Bound to one `run_once` pass. Lazy: cache + registry load on
    `__enter__`, both close on `__exit__`."""

    def __init__(
        self,
        *,
        cache_path: Path,
        tags_fn: Callable[[Any], Iterable[str]],
        registry: Registry | None = None,
        now: datetime | None = None,
    ):
        self._cache_path = cache_path
        self._tags_fn    = tags_fn
        self._registry_override = registry
        self._now        = now
        self._cache:    SignalsCache | None = None
        self._registry: Registry | None     = None

    @classmethod
    def for_sport(
        cls,
        sport: Any,
        *,
        cache_path: Path | None = None,
        registry: Registry | None = None,
        now: datetime | None = None,
    ) -> "SignalsRuntime | None":
        """Build a runtime for `sport` if it has a tag-builder AND the
        cache file exists. Returns None otherwise — the runner reads a
        None back and skips silently."""
        tags_fn = getattr(sport, "signals_tags_for", None)
        if tags_fn is None:
            return None
        path = cache_path or DEFAULT_CACHE_PATH
        if not path.exists():
            return None
        return cls(cache_path=path, tags_fn=tags_fn, registry=registry, now=now)

    def __enter__(self) -> "SignalsRuntime":
        self._cache    = SignalsCache(self._cache_path)
        self._registry = self._registry_override or Registry.from_csv()
        return self

    def __exit__(self, *exc) -> None:
        if self._cache is not None:
            self._cache.close()
            self._cache = None

    def editorial_citations_for(self, fixture: Any) -> list[Citation]:
        if self._cache is None or self._registry is None:
            raise RuntimeError("SignalsRuntime not entered — use `with` block")
        tags = self._tags_fn(fixture)
        return build_citations(
            fixture_tags=tags,
            cache=self._cache,
            registry=self._registry,
            now=self._now,
        )

    def hard_signals_for(self, fixture: Any) -> list[tuple[Signal, Source]]:
        """Return hard-track `(signal, source)` pairs covering the fixture
        — the input to the sport's feature adjuster (PR F)."""
        if self._cache is None or self._registry is None:
            raise RuntimeError("SignalsRuntime not entered — use `with` block")
        tags = self._tags_fn(fixture)
        return hard_signals_for(
            fixture_tags=tags,
            cache=self._cache,
            registry=self._registry,
            now=self._now,
        )
