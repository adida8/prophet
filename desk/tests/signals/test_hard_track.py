"""Hard-track signal selection — `hard_signals_for`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from desk.signals.cache import SignalsCache
from desk.signals.hard_track import DEFAULT_MAX_AGE, hard_signals_for
from desk.signals.models import Signal, SignalType, Source
from desk.signals.registry import Registry

_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def _source(*, id: str, reliability: float = 0.95, bias_flag: str = "none",
            tier: str = "trusted_core", parent_org: str | None = None,
            coverage_tags: str = "global|sport:football") -> Source:
    return Source.model_validate(dict(
        id=id, name=id, feed_type="rss",
        feed_ref=f"https://{id}.example.com/rss",
        language="en", coverage_tags=coverage_tags,
        reliability=reliability, bias_flag=bias_flag,
        parent_org=parent_org, tier=tier, enabled=True,
    ))


def _registry(*sources: Source) -> Registry:
    return Registry(sources)


def _signal(*, source_id: str, type: SignalType = SignalType.INJURY,
            team: str = "France", url: str = "https://x/y",
            published_at: datetime | None = None,
            claim: str = "Mbappé out with calf strain",
            quote: str = "Mbappé will miss the match with a calf strain.",
            ) -> Signal:
    return Signal(
        type=type, team=team, claim=claim, quote=quote,
        source_id=source_id, url=url,
        published_at=published_at or _NOW,
        confidence=0.9,
    )


@pytest.fixture
def cache(tmp_path: Path):
    with SignalsCache(tmp_path / "signals.db") as c:
        yield c


def _seed(cache: SignalsCache, source_id: str, signals: list[Signal]) -> None:
    cache.cache_signals(
        source_id=source_id,
        canonical_url=f"https://{source_id}.example.com/article",
        content_hash="h", extractor_id="fake:test",
        signals=signals, extracted_at=_NOW,
    )


# ── source-gate routing ───────────────────────────────────────────────

def test_hard_signal_from_trusted_source_passes_gate(cache):
    src = _source(id="bbc", reliability=0.95, bias_flag="none")
    _seed(cache, "bbc", [_signal(source_id="bbc")])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert len(rows) == 1
    assert rows[0][0].type == SignalType.INJURY


def test_injury_from_biased_source_does_not_pass_hard_gate(cache):
    # The defining failure mode in the spec: homer outlets must never
    # move the model. The trust gate filters them out here.
    src = _source(id="ole", reliability=0.85, bias_flag="national")
    _seed(cache, "ole", [_signal(source_id="ole")])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert rows == []


def test_morale_signal_from_trusted_source_does_not_pass_hard_gate(cache):
    src = _source(id="bbc", reliability=0.95)
    _seed(cache, "bbc", [_signal(source_id="bbc", type=SignalType.MORALE)])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert rows == []


def test_predicted_lineup_does_not_pass_hard_gate(cache):
    # Only confirmed_lineup is hard-eligible; speculation stays editorial.
    src = _source(id="bbc", reliability=0.95)
    _seed(cache, "bbc", [_signal(source_id="bbc", type=SignalType.PREDICTED_LINEUP)])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert rows == []


def test_confirmed_lineup_passes_hard_gate(cache):
    src = _source(id="bbc", reliability=0.95)
    _seed(cache, "bbc", [_signal(source_id="bbc", type=SignalType.CONFIRMED_LINEUP)])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert len(rows) == 1


# ── tag coverage ──────────────────────────────────────────────────────

def test_source_not_covering_fixture_excluded(cache):
    src = _source(id="cricket", reliability=0.95, coverage_tags="sport:cricket")
    _seed(cache, "cricket", [_signal(source_id="cricket")])
    rows = hard_signals_for(
        fixture_tags={"sport:football"}, cache=cache,
        registry=_registry(src), now=_NOW,
    )
    assert rows == []


# ── recency ───────────────────────────────────────────────────────────

def test_signals_older_than_max_age_excluded(cache):
    src = _source(id="bbc")
    ancient = _NOW - DEFAULT_MAX_AGE - timedelta(days=1)
    _seed(cache, "bbc", [_signal(source_id="bbc", published_at=ancient)])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert rows == []


def test_ordering_newest_first(cache):
    src = _source(id="bbc")
    older = _NOW - timedelta(hours=12)
    newer = _NOW - timedelta(hours=1)
    _seed(cache, "bbc", [
        _signal(source_id="bbc", url="https://bbc/older", published_at=older),
        _signal(source_id="bbc", url="https://bbc/newer", published_at=newer),
    ])
    rows = hard_signals_for(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert [r[0].url for r in rows] == ["https://bbc/newer", "https://bbc/older"]
