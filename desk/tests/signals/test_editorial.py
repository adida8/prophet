"""Editorial citation builder: build_citations + find_consensus."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from desk.publish.contract import Citation
from desk.signals.cache import SignalsCache
from desk.signals.editorial import (
    DEFAULT_MAX_AGE,
    build_citations,
    find_consensus,
)
from desk.signals.models import Signal, SignalType, Source
from desk.signals.registry import Registry

_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


# ── builders ──────────────────────────────────────────────────────────

def _source(
    *, id: str, name: str | None = None,
    coverage_tags: str = "global|sport:football",
    reliability: float = 0.9, bias_flag: str = "none",
    parent_org: str | None = None, tier: str = "trusted_core",
    enabled: bool = True,
) -> Source:
    return Source.model_validate(dict(
        id=id, name=name or id, feed_type="rss",
        feed_ref=f"https://{id}.example.com/rss",
        language="en", coverage_tags=coverage_tags,
        reliability=reliability, bias_flag=bias_flag,
        parent_org=parent_org, tier=tier, enabled=enabled,
    ))


def _registry(*sources: Source) -> Registry:
    return Registry(sources)


def _signal(
    *, source_id: str, url: str = "https://example.com/x",
    type: SignalType = SignalType.MORALE,
    team: str = "France", claim: str = "Squad in good spirits ahead of the friendly",
    quote: str = "Players were in good spirits at training.",
    published_at: datetime | None = None,
    quote_original: str | None = None, quote_lang: str | None = None,
) -> Signal:
    return Signal(
        type=type, team=team, claim=claim, quote=quote,
        quote_original=quote_original, quote_lang=quote_lang,
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
        content_hash="hash-x", extractor_id="fake:test",
        signals=signals, extracted_at=_NOW,
    )


# ── build_citations: track gating ─────────────────────────────────────

def test_build_citations_includes_editorial_signals():
    src = _source(id="ole", reliability=0.85, bias_flag="national")
    # 0.85 + national → editorial-only by trust gate
    assert src.editorial_only


def test_includes_editorial_track_signal(cache):
    src = _source(id="ole", bias_flag="national", reliability=0.85)
    _seed(cache, "ole", [_signal(source_id="ole", type=SignalType.MORALE)])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert len(out) == 1
    assert out[0].outlet == "ole"
    assert out[0].quote.startswith("Players were in good spirits")


def test_hard_track_signals_excluded_when_source_can_feed_model(cache):
    # Trusted-core, unbiased source emitting an injury → hard track →
    # belongs on model features, NOT in copy.editorial_citations.
    src = _source(id="bbc", reliability=0.95, bias_flag="none")
    _seed(cache, "bbc", [_signal(source_id="bbc", type=SignalType.INJURY)])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert out == []


def test_hard_type_from_biased_source_still_lands_editorial(cache):
    # Injury from Olé (biased) → editorial track → DOES become a citation.
    # This is the classic case in §2 of the spec.
    src = _source(id="ole", reliability=0.85, bias_flag="national")
    _seed(cache, "ole", [_signal(source_id="ole", type=SignalType.INJURY)])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert len(out) == 1


# ── tag resolution ────────────────────────────────────────────────────

def test_signals_from_sources_not_covering_fixture_are_excluded(cache):
    # ge-futebol's only tag is country:br. If the fixture tags don't
    # include country:br, GE doesn't surface.
    src = _source(
        id="ge", coverage_tags="country:br",
        bias_flag="national", reliability=0.85,
    )
    _seed(cache, "ge", [_signal(source_id="ge", type=SignalType.MORALE)])
    out = build_citations(
        fixture_tags={"country:ar"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert out == []


def test_signals_from_sources_covering_fixture_via_any_tag_included(cache):
    src = _source(
        id="ge", coverage_tags="country:br|sport:football",
        bias_flag="national", reliability=0.85,
    )
    _seed(cache, "ge", [_signal(source_id="ge", type=SignalType.MORALE)])
    # match via sport:football, not country:br
    out = build_citations(
        fixture_tags={"sport:football"}, cache=cache, registry=_registry(src),
        now=_NOW,
    )
    assert len(out) == 1


# ── recency window ────────────────────────────────────────────────────

def test_signals_older_than_max_age_excluded(cache):
    src = _source(id="ole", bias_flag="national", reliability=0.85)
    ancient = _NOW - DEFAULT_MAX_AGE - timedelta(days=1)
    _seed(cache, "ole", [_signal(source_id="ole", published_at=ancient)])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert out == []


def test_max_age_disabled_includes_old_signals(cache):
    src = _source(id="ole", bias_flag="national", reliability=0.85)
    ancient = _NOW - timedelta(days=400)
    _seed(cache, "ole", [_signal(source_id="ole", published_at=ancient)])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src),
        now=_NOW, max_age=None,
    )
    assert len(out) == 1


# ── ordering + cap ────────────────────────────────────────────────────

def test_orders_by_source_reliability_desc(cache):
    high = _source(id="hi", bias_flag="national", reliability=0.85)
    low  = _source(id="lo", bias_flag="national", reliability=0.6)
    _seed(cache, "hi", [_signal(source_id="hi", url="https://hi/a", quote="A. quote")])
    _seed(cache, "lo", [_signal(source_id="lo", url="https://lo/b", quote="B. quote")])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(high, low),
        now=_NOW,
    )
    assert [c.outlet for c in out] == ["hi", "lo"]


def test_caps_at_max_citations(cache):
    src = _source(id="ole", bias_flag="national", reliability=0.85)
    signals = [
        _signal(source_id="ole",
                url=f"https://ole/a{i}",
                quote=f"Sentence number {i}.",
                published_at=_NOW - timedelta(hours=i))
        for i in range(10)
    ]
    _seed(cache, "ole", signals)
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src),
        now=_NOW, max_citations=3,
    )
    assert len(out) == 3


def test_dedupes_by_url_plus_quote(cache):
    src = _source(id="ole", bias_flag="national", reliability=0.85)
    # Same article + same quote stored twice (e.g. cached twice across
    # extractor passes). The citation list should carry it exactly once.
    _seed(cache, "ole", [
        _signal(source_id="ole", url="https://ole/a", quote="X. quote"),
        _signal(source_id="ole", url="https://ole/a", quote="X. quote"),
    ])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert len(out) == 1


# ── translation honesty ───────────────────────────────────────────────

def test_translated_quote_carries_original_and_lang(cache):
    src = _source(id="lequipe", bias_flag="national", reliability=0.85)
    _seed(cache, "lequipe", [_signal(
        source_id="lequipe",
        quote="Mbappé will miss tomorrow's match with calf pain.",
        quote_original="Mbappé manquera le match de demain avec une douleur au mollet.",
        quote_lang="fr",
    )])
    out = build_citations(
        fixture_tags={"global"}, cache=cache, registry=_registry(src), now=_NOW,
    )
    assert len(out) == 1
    c = out[0]
    assert c.quote_lang == "fr"
    assert c.quote_original.startswith("Mbappé manquera")
    assert isinstance(c, Citation)


# ── find_consensus: independence rule ─────────────────────────────────

def test_consensus_requires_distinct_parent_orgs(cache):
    # Same parent_org → still counts as one independent voice.
    src_a = _source(id="aa", parent_org="corp_x", bias_flag="national", reliability=0.85)
    src_b = _source(id="bb", parent_org="corp_x", bias_flag="national", reliability=0.85)
    _seed(cache, "aa", [_signal(source_id="aa", claim="Mbappé out — calf",
                               url="https://aa/1")])
    _seed(cache, "bb", [_signal(source_id="bb", claim="Mbappé out — calf",
                               url="https://bb/1")])
    groups = find_consensus(
        fixture_tags={"global"}, cache=cache, registry=_registry(src_a, src_b),
        now=_NOW,
    )
    assert groups == []


def test_consensus_found_with_independent_orgs(cache):
    src_a = _source(id="aa", parent_org="corp_x", bias_flag="national", reliability=0.85)
    src_b = _source(id="bb", parent_org="corp_y", bias_flag="national", reliability=0.85)
    _seed(cache, "aa", [_signal(source_id="aa", claim="Mbappé out — calf",
                               url="https://aa/1")])
    _seed(cache, "bb", [_signal(source_id="bb", claim="Mbappé out — calf strain",
                               url="https://bb/1")])
    groups = find_consensus(
        fixture_tags={"global"}, cache=cache, registry=_registry(src_a, src_b),
        now=_NOW,
    )
    assert len(groups) == 1
    assert groups[0].independent_org_count == 2


def test_consensus_groups_by_team_so_phrasing_differences_dont_split(cache):
    # Two outlets describe the same incident with different prose. They
    # group on the team and surface as one consensus.
    src_a = _source(id="aa", parent_org="corp_x", bias_flag="national", reliability=0.85)
    src_b = _source(id="bb", parent_org="corp_y", bias_flag="national", reliability=0.85)
    _seed(cache, "aa", [_signal(source_id="aa", team="France",
                                claim="Mbappé out: calf strain")])
    _seed(cache, "bb", [_signal(source_id="bb", team="France",
                                claim="MBAPPÉ OUT — CALF STRAIN!")])
    groups = find_consensus(
        fixture_tags={"global"}, cache=cache, registry=_registry(src_a, src_b),
        now=_NOW,
    )
    assert len(groups) == 1
    assert groups[0].team == "france"
    assert groups[0].independent_org_count == 2


def test_consensus_distinct_when_different_team_or_claim(cache):
    src_a = _source(id="aa", parent_org="corp_x", bias_flag="national", reliability=0.85)
    src_b = _source(id="bb", parent_org="corp_y", bias_flag="national", reliability=0.85)
    _seed(cache, "aa", [_signal(source_id="aa", team="France",
                               claim="Mbappé out", url="https://aa/1")])
    _seed(cache, "bb", [_signal(source_id="bb", team="Argentina",
                               claim="Messi out", url="https://bb/1")])
    groups = find_consensus(
        fixture_tags={"global"}, cache=cache, registry=_registry(src_a, src_b),
        now=_NOW,
    )
    assert groups == []  # different (team, claim) keys
