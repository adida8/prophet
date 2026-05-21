"""SignalsRuntime.impact() — per-outlet status + per-run counts.

The runtime tallies citations + hard signals as the runner asks for
them per fixture, then `impact()` returns a row per enabled source for
the ops dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from desk.ops.report import SourceFreshness
from desk.signals.cache import SignalsCache
from desk.signals.models import Signal, SignalType, Source, SourceItem
from desk.signals.registry import Registry
from desk.signals.runtime import SignalsRuntime

_NOW = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)


def _source(**overrides) -> Source:
    base = dict(
        id="bbc-sport", name="BBC Sport (football)", feed_type="rss",
        feed_ref="https://example/rss", language="en",
        coverage_tags="global|sport:football", reliability=0.9,
        bias_flag="none", parent_org=None,
        tier="trusted_core", enabled=True,
    )
    base.update(overrides)
    return Source.model_validate(base)


def _item(source_id: str, url: str, *, fetched_at: datetime = _NOW) -> SourceItem:
    return SourceItem(
        source_id=source_id,
        url=url,
        canonical_url=url,
        title="t", body="b",
        published_at=fetched_at,
        fetched_at=fetched_at,
        content_hash="h-" + url,
    )


def _signal(source_id: str, url: str, team: str = "France") -> Signal:
    return Signal(
        type=SignalType.MORALE,
        team=team,
        claim="claim line",
        quote="A direct quote from the article.",
        source_id=source_id,
        url=url,
        published_at=_NOW,
        confidence=0.9,
    )


class _Fx:
    """Minimal fixture stub: only needs `match_id` for tally attribution."""
    def __init__(self, match_id: str = "fb-wc26-fra-mex-20260612",
                 team_a: str = "France", team_b: str = "Mexico"):
        self.match_id = match_id
        self.team_a   = team_a
        self.team_b   = team_b


def _runtime_for(db: Path, registry: Registry, *, now=_NOW) -> SignalsRuntime:
    class _Sport:
        def signals_tags_for(self, fx): return {"global", "sport:football"}
    rt = SignalsRuntime.for_sport(
        _Sport(), cache_path=db, registry=registry, now=now,
    )
    assert rt is not None
    return rt


# ── status derivation ─────────────────────────────────────────────────

def test_impact_marks_fresh_source_with_recent_ok_fetch(tmp_path: Path) -> None:
    src = _source()
    with SignalsCache(tmp_path / "signals.db") as cache:
        cache.upsert_item(_item(src.id, "https://example/a"))
        cache.mark_fetched(src.id, _NOW - timedelta(minutes=10), "ok")

    rt = _runtime_for(tmp_path / "signals.db", Registry((src,)))
    with rt:
        rows = rt.impact()
    assert len(rows) == 1
    row = rows[0]
    assert row.source_id == src.id
    assert row.status == SourceFreshness.FRESH.value
    assert row.last_ok is not None
    assert row.cached_items == 1


def test_impact_marks_stale_when_last_ok_too_old(tmp_path: Path) -> None:
    src = _source()
    with SignalsCache(tmp_path / "signals.db") as cache:
        cache.upsert_item(_item(src.id, "https://example/a"))
        cache.mark_fetched(src.id, _NOW - timedelta(days=2), "ok")

    rt = _runtime_for(tmp_path / "signals.db", Registry((src,)))
    with rt:
        row = rt.impact()[0]
    assert row.status == SourceFreshness.STALE.value


def test_impact_marks_failed_when_last_status_not_ok(tmp_path: Path) -> None:
    src = _source()
    with SignalsCache(tmp_path / "signals.db") as cache:
        cache.mark_fetched(src.id, _NOW - timedelta(minutes=5), "http_503")

    rt = _runtime_for(tmp_path / "signals.db", Registry((src,)))
    with rt:
        row = rt.impact()[0]
    assert row.status == SourceFreshness.FAILED.value
    assert row.last_ok is None


def test_impact_marks_stale_when_never_fetched(tmp_path: Path) -> None:
    # Cache file exists (so for_sport opens), source enabled, but no
    # mark_fetched call has ever been made. Treat as `stale` — operator
    # sees the row but knows the fetcher hasn't run for this outlet yet.
    src = _source()
    SignalsCache(tmp_path / "signals.db").close()

    rt = _runtime_for(tmp_path / "signals.db", Registry((src,)))
    with rt:
        row = rt.impact()[0]
    assert row.status == SourceFreshness.STALE.value
    assert row.cached_items == 0


# ── per-run tally ─────────────────────────────────────────────────────

def test_impact_counts_citations_per_outlet(tmp_path: Path) -> None:
    """A citation generated for a fixture attributes to the right
    source via the URL→source_id index built at __enter__."""
    src = _source()
    url = "https://example/a"
    with SignalsCache(tmp_path / "signals.db") as cache:
        cache.upsert_item(_item(src.id, url))
        cache.cache_signals(
            source_id=src.id, canonical_url=url,
            content_hash="h-" + url, extractor_id="fake:test",
            signals=[_signal(src.id, url, team="France")],
            extracted_at=_NOW,
        )
        cache.mark_fetched(src.id, _NOW, "ok")

    rt = _runtime_for(tmp_path / "signals.db", Registry((src,)))
    with rt:
        cites = rt.editorial_citations_for(_Fx())
        # Citation came back AND impact attributes it to this source.
        assert len(cites) == 1
        rows = rt.impact()
    row = rows[0]
    assert row.citations == 1
    assert row.fixtures_touched == 1


def test_impact_lists_one_row_per_enabled_source(tmp_path: Path) -> None:
    """Disabled sources are dropped; the rest each get one row even
    when they didn't contribute anything this run."""
    a = _source(id="bbc-sport", name="BBC")
    b = _source(id="guardian-football", name="Guardian")
    disabled = _source(id="old-outlet", name="Retired", enabled=False)
    SignalsCache(tmp_path / "signals.db").close()

    rt = _runtime_for(tmp_path / "signals.db", Registry((a, b, disabled)))
    with rt:
        rows = rt.impact()
    ids = {r.source_id for r in rows}
    assert ids == {"bbc-sport", "guardian-football"}
    assert all(r.citations == 0 and r.hard_adjustments == 0 for r in rows)


def test_impact_fixtures_touched_dedupes_across_calls(tmp_path: Path) -> None:
    """Two citations for the same fixture from one source → 2 citations
    but only 1 fixture touched."""
    src = _source()
    urls = [f"https://example/{i}" for i in range(2)]
    with SignalsCache(tmp_path / "signals.db") as cache:
        for u in urls:
            cache.upsert_item(_item(src.id, u))
            cache.cache_signals(
                source_id=src.id, canonical_url=u,
                content_hash="h-" + u, extractor_id="fake:test",
                signals=[_signal(src.id, u, team="France")],
                extracted_at=_NOW,
            )
        cache.mark_fetched(src.id, _NOW, "ok")

    rt = _runtime_for(tmp_path / "signals.db", Registry((src,)))
    with rt:
        rt.editorial_citations_for(_Fx())
        row = rt.impact()[0]
    assert row.citations == 2
    assert row.fixtures_touched == 1
