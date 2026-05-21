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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from desk.ops.report import SignalImpactRow, SourceFreshness
from desk.publish.contract import Citation
from desk.signals.cache import SignalsCache
from desk.signals.editorial import build_citations
from desk.signals.hard_track import hard_signals_for
from desk.signals.models import Signal, Source
from desk.signals.registry import Registry

log = logging.getLogger("desk.signals.runtime")

# Derived from the package location, not the cwd. The desk CLI is run
# from `cd desk && python -m desk …`, so a literal `desk/data/...`
# relative path would resolve to `desk/desk/data/...` and the runner
# would silently see "no cache". The absolute form is cwd-independent.
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "signals.db"

# Window inside which a source's last successful fetch keeps it `fresh`.
# RSS feeds polled hourly stay green; daily aggregators may slip to
# `stale` overnight without any signal that something's actually broken.
_FRESH_WINDOW = timedelta(hours=24)


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
        # Per-run impact tallies — populated as the runner asks for
        # citations + hard signals during the per-fixture loop. Read by
        # `impact()` at the tail of the run.
        self._cited_by_source:    dict[str, int] = {}
        self._hard_by_source:     dict[str, int] = {}
        self._fixtures_by_source: dict[str, set[str]] = {}
        # Lazy indexes built at __enter__ from the cache:
        #   url -> source_id  (so we can attribute Citations back to the
        #                      outlet without re-resolving by name)
        #   source_id -> count of cached items + extracted signals
        self._url_to_source:   dict[str, str] = {}
        self._cached_items_by_source:      dict[str, int] = {}
        self._extracted_signals_by_source: dict[str, int] = {}

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
        # Build per-source aggregates + URL→source attribution index
        # once, so per-fixture lookups are O(1). Items + signals are
        # the operator's local news cache; even a generous setup is in
        # the low thousands.
        for source in self._registry.enabled():
            try:
                items = self._cache.list_items(source_id=source.id)
            except Exception as e:                          # noqa: BLE001
                log.warning("cache.list_items(%s) failed: %s", source.id, e)
                items = []
            self._cached_items_by_source[source.id] = len(items)
            for item in items:
                # Index both forms — Citation.url tracks Signal.url which
                # typically matches SourceItem.url, but `canonical_url` is
                # what dedup keys on, so a fixed canonicalisation pass
                # downstream could surface either form.
                if item.url:
                    self._url_to_source[item.url] = source.id
                if item.canonical_url:
                    self._url_to_source[item.canonical_url] = source.id
            try:
                self._extracted_signals_by_source[source.id] = len(
                    self._cache.list_signals(source_id=source.id)
                )
            except Exception as e:                          # noqa: BLE001
                log.warning("cache.list_signals(%s) failed: %s", source.id, e)
                self._extracted_signals_by_source[source.id] = 0
        return self

    def __exit__(self, *exc) -> None:
        if self._cache is not None:
            self._cache.close()
            self._cache = None

    def editorial_citations_for(self, fixture: Any) -> list[Citation]:
        if self._cache is None or self._registry is None:
            raise RuntimeError("SignalsRuntime not entered — use `with` block")
        tags = self._tags_fn(fixture)
        # Bind to the participating teams so the citation pool is
        # specific to the fixture, not a global football-news firehose.
        teams: list[str] = []
        for attr in ("team_a", "team_b"):
            v = getattr(fixture, attr, None)
            if v:
                teams.append(v)
        citations = build_citations(
            fixture_tags=tags,
            cache=self._cache,
            registry=self._registry,
            teams=teams or None,
            now=self._now,
        )
        self._tally_citations(fixture, citations)
        return citations

    def hard_signals_for(self, fixture: Any) -> list[tuple[Signal, Source]]:
        """Return hard-track `(signal, source)` pairs covering the fixture
        — the input to the sport's feature adjuster (PR F)."""
        if self._cache is None or self._registry is None:
            raise RuntimeError("SignalsRuntime not entered — use `with` block")
        tags = self._tags_fn(fixture)
        pairs = hard_signals_for(
            fixture_tags=tags,
            cache=self._cache,
            registry=self._registry,
            now=self._now,
        )
        self._tally_hard(fixture, pairs)
        return pairs

    # ── per-run impact tallying ──────────────────────────────────────

    def _tally_citations(self, fixture: Any, citations: list[Citation]) -> None:
        if not citations:
            return
        fixture_id = self._fixture_id(fixture)
        for cite in citations:
            src_id = self._url_to_source.get(cite.url)
            if src_id is None:
                continue
            self._cited_by_source[src_id] = self._cited_by_source.get(src_id, 0) + 1
            if fixture_id:
                self._fixtures_by_source.setdefault(src_id, set()).add(fixture_id)

    def _tally_hard(self, fixture: Any, pairs: list[tuple[Signal, Source]]) -> None:
        if not pairs:
            return
        fixture_id = self._fixture_id(fixture)
        for _signal, source in pairs:
            self._hard_by_source[source.id] = self._hard_by_source.get(source.id, 0) + 1
            if fixture_id:
                self._fixtures_by_source.setdefault(source.id, set()).add(fixture_id)

    @staticmethod
    def _fixture_id(fixture: Any) -> str | None:
        """Match-id if the fixture exposes one; else None.

        We accept any duck-typed `match_id` so the runtime stays agnostic
        of the sport's exact fixture class (FixtureRef today; sport-
        specific subclasses tomorrow).
        """
        return getattr(fixture, "match_id", None)

    # ── public surface for the ops dashboard ─────────────────────────

    def impact(self) -> list[SignalImpactRow]:
        """Per-outlet status + this-run contribution counts.

        One row per *enabled* source in the registry. Each row carries:
          - status pill derived from `cache.last_status` + `last_fetched`
          - all-time cached items + extracted signals (operator confidence
            that the source actually has data behind it)
          - this-run counts of citations, hard adjustments, and distinct
            fixtures touched

        Must be called while inside the `with` block (cache still open).
        Returns `[]` if no enabled sources, never raises on a single bad
        source — failures are logged + the row reports zeros so the
        dashboard surfaces them rather than swallowing them silently.
        """
        if self._registry is None or self._cache is None:
            return []
        now = self._now or datetime.now(tz=timezone.utc)
        out: list[SignalImpactRow] = []
        for source in self._registry.enabled():
            status, last_ok = self._derive_status(source, now=now)
            out.append(SignalImpactRow(
                source_id=source.id,
                name=source.name,
                status=status,
                last_ok=last_ok,
                cached_items=self._cached_items_by_source.get(source.id, 0),
                extracted_signals=self._extracted_signals_by_source.get(source.id, 0),
                citations=self._cited_by_source.get(source.id, 0),
                hard_adjustments=self._hard_by_source.get(source.id, 0),
                fixtures_touched=len(self._fixtures_by_source.get(source.id, set())),
            ))
        return out

    def _derive_status(
        self,
        source: Source,
        *,
        now: datetime,
    ) -> tuple[SourceFreshness, datetime | None]:
        """Map (feed_type, last_status, last_fetched) → freshness pill.

        - `frozen` for `feed_type=none` (registry-only — not fetchable
          by design, so 'never fetched' isn't a bug).
        - `failed` when the most recent fetch attempt reported an error.
        - `stale` when last successful fetch is older than `_FRESH_WINDOW`
          OR there's no fetch on record at all.
        - `fresh` otherwise.
        """
        if getattr(source, "feed_type", None) == "none":
            return SourceFreshness.FROZEN, None
        try:
            last_at = self._cache.last_fetched(source.id) if self._cache else None
            last_st = self._cache.last_status(source.id)   if self._cache else None
        except Exception as e:                              # noqa: BLE001
            log.warning("cache status lookup for %s failed: %s", source.id, e)
            return SourceFreshness.FAILED, None

        if last_st and last_st != "ok":
            return SourceFreshness.FAILED, None
        if last_at is None:
            return SourceFreshness.STALE, None
        # Last fetch row tz-naive? Treat as UTC — that's what the cache writes.
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        if (now - last_at) > _FRESH_WINDOW:
            return SourceFreshness.STALE, last_at
        return SourceFreshness.FRESH, last_at
