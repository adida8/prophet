"""SQLite cache: insert / dedupe / change detection / fetch metadata."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from desk.signals.cache import SignalsCache
from desk.signals.models import SourceItem

_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def _item(*, canonical_url="https://example.com/a", title="T", body="B",
          content_hash="hash-1", url=None, fetched_at=None) -> SourceItem:
    return SourceItem(
        source_id="src",
        url=url or canonical_url,
        canonical_url=canonical_url,
        title=title,
        body=body,
        published_at=_NOW,
        fetched_at=fetched_at or _NOW,
        content_hash=content_hash,
    )


@pytest.fixture
def cache(tmp_path: Path):
    with SignalsCache(tmp_path / "signals.db") as c:
        yield c


def test_first_insert_is_new(cache):
    assert cache.upsert_item(_item()) == "new"


def test_reinsert_same_content_is_unchanged(cache):
    cache.upsert_item(_item())
    assert cache.upsert_item(_item()) == "unchanged"


def test_changed_body_detected_via_content_hash(cache):
    cache.upsert_item(_item(content_hash="h1", body="body-v1"))
    result = cache.upsert_item(_item(content_hash="h2", body="body-v2"))
    assert result == "changed"
    stored = cache.get_item("src", "https://example.com/a")
    assert stored is not None
    assert stored.body == "body-v2"
    assert stored.content_hash == "h2"


def test_dedupes_on_canonical_url_not_raw_url(cache):
    cache.upsert_item(_item(
        url="https://example.com/a?utm_source=rss", canonical_url="https://example.com/a",
        content_hash="h1",
    ))
    # different raw URL, same canonical → unchanged
    assert cache.upsert_item(_item(
        url="https://example.com/a?fbclid=zzz", canonical_url="https://example.com/a",
        content_hash="h1",
    )) == "unchanged"
    assert len(cache.list_items("src")) == 1


def test_upsert_many_returns_counts(cache):
    counts = cache.upsert_many([
        _item(canonical_url="https://example.com/a", content_hash="h-a"),
        _item(canonical_url="https://example.com/b", content_hash="h-b"),
    ])
    assert counts == {"new": 2, "changed": 0, "unchanged": 0}

    counts = cache.upsert_many([
        _item(canonical_url="https://example.com/a", content_hash="h-a"),         # unchanged
        _item(canonical_url="https://example.com/b", content_hash="h-b-edited",
              body="edited"),                                                      # changed
        _item(canonical_url="https://example.com/c", content_hash="h-c"),         # new
    ])
    assert counts == {"new": 1, "changed": 1, "unchanged": 1}


def test_list_items_filters_by_source(cache):
    cache.upsert_item(SourceItem(
        source_id="src-a", url="https://a", canonical_url="https://a",
        title="A", body="b", published_at=None, fetched_at=_NOW, content_hash="h",
    ))
    cache.upsert_item(SourceItem(
        source_id="src-b", url="https://b", canonical_url="https://b",
        title="B", body="b", published_at=None, fetched_at=_NOW, content_hash="h",
    ))
    assert {i.source_id for i in cache.list_items()} == {"src-a", "src-b"}
    assert {i.source_id for i in cache.list_items("src-a")} == {"src-a"}


def test_mark_fetched_overwrites(cache):
    cache.mark_fetched("src", _NOW, "ok")
    assert cache.last_status("src") == "ok"
    cache.mark_fetched("src", _NOW + timedelta(minutes=5), "http_error")
    assert cache.last_status("src") == "http_error"
    assert cache.last_fetched("src") == _NOW + timedelta(minutes=5)


def test_last_fetched_none_for_unknown(cache):
    assert cache.last_fetched("never-touched") is None
    assert cache.last_status("never-touched") is None


def test_db_path_created_on_demand(tmp_path: Path):
    deep = tmp_path / "a" / "b" / "signals.db"
    with SignalsCache(deep) as c:
        c.upsert_item(_item())
    assert deep.exists()
