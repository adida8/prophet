"""SignalsRuntime + runner editorial-citation wiring."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.signals.cache import SignalsCache
from desk.signals.editorial import build_citations
from desk.signals.models import Signal, SignalType, Source
from desk.signals.registry import Registry
from desk.signals.runtime import SignalsRuntime

_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def _source(**overrides) -> Source:
    base = dict(
        id="ole", name="Olé", feed_type="rss",
        feed_ref="https://ole/rss", language="es",
        coverage_tags="global|sport:football", reliability=0.85,
        bias_flag="national", parent_org="clarin",
        tier="trusted_core", enabled=True,
    )
    base.update(overrides)
    return Source.model_validate(base)


def _signal(source_id: str = "ole") -> Signal:
    return Signal(
        type=SignalType.MORALE, team="Argentina",
        claim="Squad in good spirits ahead of friendly",
        quote="Players were in good spirits at training.",
        source_id=source_id, url=f"https://{source_id}/x",
        published_at=_NOW, confidence=0.9,
    )


# ── for_sport gating ──────────────────────────────────────────────────

def test_for_sport_returns_none_when_cache_file_missing(tmp_path: Path):
    class _Sport:
        def signals_tags_for(self, fx):
            return {"global"}
    rt = SignalsRuntime.for_sport(
        _Sport(), cache_path=tmp_path / "missing.db", now=_NOW,
    )
    assert rt is None


def test_for_sport_returns_none_when_sport_has_no_tag_builder(tmp_path: Path):
    db = tmp_path / "signals.db"
    SignalsCache(db).close()                           # touch
    class _Sport:
        pass
    rt = SignalsRuntime.for_sport(_Sport(), cache_path=db, now=_NOW)
    assert rt is None


def test_for_sport_returns_runtime_when_both_ready(tmp_path: Path):
    db = tmp_path / "signals.db"
    SignalsCache(db).close()
    class _Sport:
        def signals_tags_for(self, fx):
            return {"global"}
    rt = SignalsRuntime.for_sport(
        _Sport(), cache_path=db, registry=Registry(()), now=_NOW,
    )
    assert rt is not None


# ── happy-path round trip ─────────────────────────────────────────────

def test_runtime_yields_citations_for_a_fixture(tmp_path: Path):
    db = tmp_path / "signals.db"
    src = _source()
    with SignalsCache(db) as cache:
        cache.cache_signals(
            source_id=src.id, canonical_url="https://ole/x",
            content_hash="h", extractor_id="fake:test",
            signals=[_signal()], extracted_at=_NOW,
        )

    class _Sport:
        def signals_tags_for(self, fx):
            return {"global"}

    rt = SignalsRuntime.for_sport(
        _Sport(), cache_path=db, registry=Registry((src,)), now=_NOW,
    )
    assert rt is not None
    with rt:
        out = rt.editorial_citations_for(fixture=object())
    assert len(out) == 1
    assert out[0].outlet == "Olé"


def test_runtime_must_be_entered_before_use(tmp_path: Path):
    db = tmp_path / "signals.db"
    SignalsCache(db).close()

    class _Sport:
        def signals_tags_for(self, fx):
            return {"global"}

    rt = SignalsRuntime.for_sport(
        _Sport(), cache_path=db, registry=Registry(()), now=_NOW,
    )
    with pytest.raises(RuntimeError, match="not entered"):
        rt.editorial_citations_for(fixture=object())


# ── runner integration (smoke) ────────────────────────────────────────

def test_runner_does_not_blow_up_without_signals_db(tmp_path: Path, monkeypatch):
    """Smoke test: with no signals.db, the runner module imports cleanly
    and the editorial path is silently skipped. This is the default
    state on a fresh clone; we must not regress it."""
    # Importing the runner is the asserted no-op.
    from desk import runner  # noqa: F401
    assert hasattr(runner, "run_once")
