"""LLM extraction: prompt build, response parse, validation, cache hit/miss."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from desk.signals.cache import SignalsCache
from desk.signals.extract import (
    _quote_is_in_article,
    build_messages,
    extract_all,
    extract_item,
    parse_tool_use,
)
from desk.signals.models import Signal, SignalType, Source, SourceItem

_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


# ── helpers ───────────────────────────────────────────────────────────

def _source(**overrides) -> Source:
    base = dict(
        id="bbc-test",
        name="BBC Test",
        feed_type="rss",
        feed_ref="https://example.com/rss",
        language="en",
        coverage_tags="global|sport:football",
        reliability=0.9,
        bias_flag="none",
        parent_org="bbc",
        tier="trusted_core",
        enabled=True,
    )
    base.update(overrides)
    return Source.model_validate(base)


def _item(*, body: str = "Mbappé will miss tomorrow's match with a calf strain.",
          title: str = "Mbappé out with calf strain",
          source_id: str = "bbc-test",
          url: str = "https://example.com/mbappe-calf") -> SourceItem:
    content = hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()
    return SourceItem(
        source_id=source_id,
        url=url,
        canonical_url=url,
        title=title,
        body=body,
        published_at=_NOW,
        fetched_at=_NOW,
        content_hash=content,
    )


class _FakeExtractor:
    """Test double: returns canned raw-signal dicts per (source_id, url)."""

    def __init__(self, *, model_id: str = "fake:test"):
        self._id = model_id
        self.canned: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.calls: list[tuple[str, str]] = []
        self.raise_on: set[tuple[str, str]] = set()

    @property
    def id(self) -> str:
        return self._id

    def set(self, item: SourceItem, raws: list[dict[str, Any]]) -> None:
        self.canned[(item.source_id, item.canonical_url)] = raws

    def extract_raw(self, *, item: SourceItem, source: Source) -> list[dict[str, Any]]:
        key = (item.source_id, item.canonical_url)
        self.calls.append(key)
        if key in self.raise_on:
            raise RuntimeError("simulated SDK error")
        return list(self.canned.get(key, []))


# ── prompt building ───────────────────────────────────────────────────

def test_build_messages_has_cached_system_block():
    src = _source()
    item = _item()
    system, messages = build_messages(item, src)
    assert len(system) == 1
    assert system[0]["type"] == "text"
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "emit_signals" in system[0]["text"]
    assert "verbatim" in system[0]["text"].lower()


def test_build_messages_user_carries_source_and_article():
    src = _source(name="L'Équipe", language="fr", reliability=0.85, bias_flag="national")
    item = _item(title="Mbappé absent", body="Le forward est absent.")
    _, messages = build_messages(item, src)
    text = messages[0]["content"]
    assert "L'Équipe" in text
    assert "fr" in text
    assert "national" in text
    assert "Mbappé absent" in text
    assert "Le forward est absent." in text


# ── response parsing ──────────────────────────────────────────────────

def test_parse_tool_use_pulls_signals_array():
    block = SimpleNamespace(
        type="tool_use",
        name="emit_signals",
        input={"signals": [{"type": "injury", "team": "France"}]},
    )
    resp = SimpleNamespace(content=[block])
    out = parse_tool_use(resp)
    assert out == [{"type": "injury", "team": "France"}]


def test_parse_tool_use_ignores_text_blocks():
    text_block = SimpleNamespace(type="text", text="hello")
    resp = SimpleNamespace(content=[text_block])
    assert parse_tool_use(resp) == []


def test_parse_tool_use_ignores_wrong_tool_name():
    block = SimpleNamespace(
        type="tool_use", name="something_else",
        input={"signals": [{"type": "injury"}]},
    )
    assert parse_tool_use(SimpleNamespace(content=[block])) == []


def test_parse_tool_use_empty_response():
    assert parse_tool_use(SimpleNamespace(content=None)) == []
    assert parse_tool_use(SimpleNamespace(content=[])) == []


# ── quote-must-be-in-article guard ────────────────────────────────────

def test_quote_in_article_substring():
    item = _item(body="The France forward will miss tomorrow's match with a calf strain.")
    assert _quote_is_in_article(
        "miss tomorrow's match with a calf strain", item,
    )


def test_quote_in_article_tolerates_whitespace():
    item = _item(body="Line one.\n  Line two.\nLine\tthree.")
    # multi-line/whitespace-collapsed match should still succeed
    assert _quote_is_in_article("Line one. Line two. Line three.", item)


def test_quote_not_in_article_rejected():
    item = _item(body="Nothing about that here.")
    assert not _quote_is_in_article("Made-up sentence the LLM hallucinated.", item)


def test_quote_can_match_title():
    item = _item(title="Mbappé out with calf strain", body="...")
    assert _quote_is_in_article("Mbappé out with calf strain", item)


# ── extract_item: full path with engine-side fields ───────────────────

def test_extract_item_fills_engine_fields_and_keeps_valid_signals():
    src = _source()
    item = _item()
    extractor = _FakeExtractor()
    extractor.set(item, [{
        "type": "injury",
        "team": "France",
        "claim": "Mbappé out with calf strain",
        "quote": "Mbappé will miss tomorrow's match with a calf strain.",
        "confidence": 0.92,
    }])
    sigs = extract_item(item, src, extractor=extractor)
    assert len(sigs) == 1
    s = sigs[0]
    # LLM-supplied
    assert s.type == SignalType.INJURY
    assert s.team == "France"
    assert s.claim == "Mbappé out with calf strain"
    assert s.confidence == 0.92
    # engine-supplied — these are NOT trusted to the LLM
    assert s.source_id == src.id
    assert s.url == item.url
    assert s.published_at == item.published_at


def test_extract_item_drops_signals_whose_quote_is_not_in_article():
    src = _source()
    item = _item(body="Nothing about Mbappé here.")
    extractor = _FakeExtractor()
    extractor.set(item, [{
        "type": "injury", "team": "France", "claim": "x",
        "quote": "A sentence the LLM made up.",
        "confidence": 0.9,
    }])
    assert extract_item(item, src, extractor=extractor) == []


def test_extract_item_keeps_translation_uses_quote_original_for_check():
    src = _source(language="fr", bias_flag="national", reliability=0.85)
    body_fr = "Mbappé manquera le match de demain avec une douleur au mollet."
    item = _item(body=body_fr, title="Mbappé forfait")
    extractor = _FakeExtractor()
    extractor.set(item, [{
        "type": "injury", "team": "France", "claim": "Mbappé out — calf",
        "quote": "Mbappé will miss tomorrow's match with calf pain.",   # English (translated)
        "quote_original": "Mbappé manquera le match de demain avec une douleur au mollet.",
        "quote_lang": "fr",
        "confidence": 0.9,
    }])
    sigs = extract_item(item, src, extractor=extractor)
    assert len(sigs) == 1
    assert sigs[0].quote_lang == "fr"
    assert sigs[0].quote_original == body_fr


def test_extract_item_rejects_mismatched_source():
    src = _source(id="src-a")
    item = _item(source_id="src-b")
    with pytest.raises(ValueError):
        extract_item(item, src, extractor=_FakeExtractor())


def test_extract_item_drops_invalid_payload_silently():
    src = _source()
    item = _item()
    extractor = _FakeExtractor()
    extractor.set(item, [
        {"type": "not_a_real_type", "team": "X", "claim": "y", "quote": "z", "confidence": 0.5},
        {"type": "injury", "team": "France", "claim": "ok",
         "quote": "Mbappé will miss tomorrow's match with a calf strain.",
         "confidence": 0.9},
    ])
    sigs = extract_item(item, src, extractor=extractor)
    # the bad row is dropped; the good one keeps going
    assert len(sigs) == 1
    assert sigs[0].claim == "ok"


def test_extract_item_track_routes_via_source_gate_even_for_injury():
    # Same INJURY signal from a biased outlet must stay editorial.
    biased = _source(id="ole-test", bias_flag="national", reliability=0.85)
    item = _item(source_id="ole-test")
    extractor = _FakeExtractor()
    extractor.set(item, [{
        "type": "injury", "team": "France", "claim": "x",
        "quote": "Mbappé will miss tomorrow's match with a calf strain.",
        "confidence": 0.9,
    }])
    sigs = extract_item(item, biased, extractor=extractor)
    assert len(sigs) == 1
    assert sigs[0].track(biased) == "editorial"


# ── extract_all + cache integration ───────────────────────────────────

@pytest.fixture
def cache(tmp_path: Path):
    with SignalsCache(tmp_path / "signals.db") as c:
        yield c


def _seed_cache(cache: SignalsCache, items: list[SourceItem]) -> None:
    for item in items:
        cache.upsert_item(item)


def test_extract_all_calls_extractor_once_per_item_then_caches(cache, monkeypatch):
    src = _source()
    item = _item()
    _seed_cache(cache, [item])

    # Force the runner to find our source.
    monkeypatch.setattr("desk.signals.extract._resolve_source", lambda sid: src)

    extractor = _FakeExtractor()
    extractor.set(item, [{
        "type": "injury", "team": "France", "claim": "x",
        "quote": "Mbappé will miss tomorrow's match with a calf strain.",
        "confidence": 0.9,
    }])

    first  = extract_all(cache, extractor=extractor)
    second = extract_all(cache, extractor=extractor)

    assert len(extractor.calls) == 1            # only the first pass hit the LLM
    assert first[0].status  == "extracted"
    assert second[0].status == "cached"
    assert first[0].new_signals == second[0].new_signals == 1


def test_extract_all_re_extracts_when_content_hash_changes(cache, monkeypatch):
    src = _source()
    item = _item()
    _seed_cache(cache, [item])
    monkeypatch.setattr("desk.signals.extract._resolve_source", lambda sid: src)

    extractor = _FakeExtractor()
    extractor.set(item, [{
        "type": "injury", "team": "France", "claim": "x",
        "quote": "Mbappé will miss tomorrow's match with a calf strain.",
        "confidence": 0.9,
    }])

    extract_all(cache, extractor=extractor)
    assert len(extractor.calls) == 1

    # Body edited → new content_hash. Re-seed and re-run.
    edited = _item(body="The France forward will miss the next two matches.")
    cache.upsert_item(edited)
    extractor.set(edited, [{
        "type": "injury", "team": "France", "claim": "y",
        "quote": "The France forward will miss the next two matches.",
        "confidence": 0.9,
    }])
    out = extract_all(cache, extractor=extractor)
    assert len(extractor.calls) == 2
    assert out[0].status == "extracted"


def test_extract_all_caches_empty_extractions_so_we_dont_retry(cache, monkeypatch):
    src = _source()
    item = _item()
    _seed_cache(cache, [item])
    monkeypatch.setattr("desk.signals.extract._resolve_source", lambda sid: src)

    extractor = _FakeExtractor()
    extractor.set(item, [])  # nothing relevant in this article

    out1 = extract_all(cache, extractor=extractor)
    out2 = extract_all(cache, extractor=extractor)

    assert out1[0].status == "dropped_empty"
    assert out2[0].status == "cached"
    assert len(extractor.calls) == 1


def test_extract_all_skips_when_source_not_in_registry(cache, monkeypatch):
    item = _item()
    cache.upsert_item(item)
    monkeypatch.setattr("desk.signals.extract._resolve_source", lambda sid: None)
    out = extract_all(cache, extractor=_FakeExtractor())
    assert len(out) == 1 and out[0].status == "error"


def test_extract_all_respects_source_ids_filter(cache, monkeypatch):
    src = _source()
    _seed_cache(cache, [
        _item(url="https://example.com/a", source_id="bbc-test"),
        _item(url="https://example.com/b", source_id="ole-ar"),
    ])
    monkeypatch.setattr("desk.signals.extract._resolve_source", lambda sid: src)
    extractor = _FakeExtractor()

    out = extract_all(cache, extractor=extractor, source_ids={"bbc-test"})
    assert {o.source_id for o in out} == {"bbc-test"}


def test_extract_all_records_error_status_when_extractor_throws(cache, monkeypatch):
    src = _source()
    item = _item()
    _seed_cache(cache, [item])
    monkeypatch.setattr("desk.signals.extract._resolve_source", lambda sid: src)

    extractor = _FakeExtractor()
    extractor.raise_on.add((item.source_id, item.canonical_url))

    out = extract_all(cache, extractor=extractor)
    assert out[0].status == "error"
    # error is NOT cached — next run will retry
    assert cache.cached_signals(
        source_id=src.id, canonical_url=item.canonical_url,
        content_hash=item.content_hash, extractor_id=extractor.id,
    ) is None


# ── SignalsCache: extraction round-trip ───────────────────────────────

def test_cache_signals_roundtrip(cache):
    src = _source()
    item = _item()
    sig = Signal(
        type=SignalType.INJURY, team="France",
        claim="x", quote="Mbappé will miss tomorrow's match with a calf strain.",
        source_id=src.id, url=item.url, published_at=item.published_at,
        confidence=0.9,
    )
    cache.cache_signals(
        source_id=src.id, canonical_url=item.canonical_url,
        content_hash=item.content_hash, extractor_id="fake:test",
        signals=[sig], extracted_at=_NOW,
    )
    got = cache.cached_signals(
        source_id=src.id, canonical_url=item.canonical_url,
        content_hash=item.content_hash, extractor_id="fake:test",
    )
    assert got is not None and len(got) == 1
    assert got[0].claim == "x"
    assert got[0].source_id == src.id


def test_cache_signals_returns_none_when_content_hash_changed(cache):
    src = _source()
    item = _item()
    cache.cache_signals(
        source_id=src.id, canonical_url=item.canonical_url,
        content_hash="old-hash", extractor_id="fake:test",
        signals=[], extracted_at=_NOW,
    )
    got = cache.cached_signals(
        source_id=src.id, canonical_url=item.canonical_url,
        content_hash="new-hash", extractor_id="fake:test",
    )
    assert got is None


def test_list_signals_returns_all_and_filters_by_source(cache):
    sig_a = Signal(
        type=SignalType.INJURY, team="France",
        claim="a", quote="Mbappé will miss tomorrow's match with a calf strain.",
        source_id="src-a", url="https://example.com/a",
        confidence=0.9,
    )
    sig_b = Signal(
        type=SignalType.SUSPENSION, team="Brazil",
        claim="b", quote="Vinicius will serve a one-match ban.",
        source_id="src-b", url="https://example.com/b",
        confidence=0.85,
    )
    cache.cache_signals(
        source_id="src-a", canonical_url="https://example.com/a",
        content_hash="h", extractor_id="fake:test",
        signals=[sig_a], extracted_at=_NOW,
    )
    cache.cache_signals(
        source_id="src-b", canonical_url="https://example.com/b",
        content_hash="h", extractor_id="fake:test",
        signals=[sig_b], extracted_at=_NOW,
    )
    assert {s.source_id for s in cache.list_signals()} == {"src-a", "src-b"}
    assert {s.source_id for s in cache.list_signals(source_id="src-a")} == {"src-a"}
