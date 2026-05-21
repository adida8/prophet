"""GDELT aggregator: URL building + response parsing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.signals.aggregator import (
    build_gdelt_url,
    parse_aggregator_ref,
    parse_gdelt_response,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


# ── parse_aggregator_ref ──────────────────────────────────────────────

def test_parse_aggregator_ref_splits_scheme_and_query():
    assert parse_aggregator_ref("gdelt:query=football") == ("gdelt", "query=football")


def test_parse_aggregator_ref_lowercases_scheme():
    assert parse_aggregator_ref("GDELT:query=x") == ("gdelt", "query=x")


def test_parse_aggregator_ref_rejects_missing_scheme():
    with pytest.raises(ValueError, match="scheme"):
        parse_aggregator_ref("no-colon-here")


# ── build_gdelt_url ───────────────────────────────────────────────────

def test_gdelt_url_strips_query_prefix_and_uses_param_form():
    url = build_gdelt_url("query=football OR soccer")
    assert url.startswith("https://api.gdeltproject.org/api/v2/doc/doc?")
    # urlencode → spaces become "+"
    assert "query=football+OR+soccer" in url
    assert "mode=ArtList" in url
    assert "format=json" in url


def test_gdelt_url_accepts_bare_query():
    url = build_gdelt_url("sport:football")
    assert "query=sport%3Afootball" in url


def test_gdelt_url_respects_maxrecords_and_timespan():
    url = build_gdelt_url("football", maxrecords=10, timespan="1day")
    assert "maxrecords=10" in url
    assert "timespan=1day" in url


# ── parse_gdelt_response ──────────────────────────────────────────────

def _read_fixture() -> str:
    return (FIXTURES / "sample-gdelt.json").read_text(encoding="utf-8")


def test_parse_gdelt_returns_source_items():
    items = parse_gdelt_response(
        source_id="gdelt-football", body=_read_fixture(), fetched_at=_NOW,
    )
    # five raw entries → three valid (two dropped for empty url or title)
    assert len(items) == 3
    assert {i.source_id for i in items} == {"gdelt-football"}


def test_parse_gdelt_strips_trackers_and_canonicalises_url():
    items = parse_gdelt_response(
        source_id="gdelt-football", body=_read_fixture(), fetched_at=_NOW,
    )
    arg = next(i for i in items if "Argentina" in i.title)
    assert "utm_source" in arg.url
    assert arg.canonical_url == "https://example.com/argentina-injury"


def test_parse_gdelt_body_equals_title():
    """GDELT doesn't return article bodies — the headline IS the body.
    The extractor's citation guarantee then only admits signals whose
    quote sits inside the headline."""
    items = parse_gdelt_response(
        source_id="gdelt-football", body=_read_fixture(), fetched_at=_NOW,
    )
    for i in items:
        assert i.body == i.title


def test_parse_gdelt_seendate_to_aware_datetime():
    items = parse_gdelt_response(
        source_id="gdelt-football", body=_read_fixture(), fetched_at=_NOW,
    )
    arg = next(i for i in items if "Argentina" in i.title)
    assert arg.published_at == datetime(2026, 5, 19, 8, 0, tzinfo=timezone.utc)


def test_parse_gdelt_missing_seendate_keeps_item_with_null_publish():
    items = parse_gdelt_response(
        source_id="gdelt-football", body=_read_fixture(), fetched_at=_NOW,
    )
    nodate = next(i for i in items if "missing seendate" in i.title)
    assert nodate.published_at is None


def test_parse_gdelt_raises_on_malformed_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_gdelt_response(source_id="x", body="{not json", fetched_at=_NOW)


def test_parse_gdelt_handles_empty_articles_list():
    items = parse_gdelt_response(
        source_id="x", body='{"articles": []}', fetched_at=_NOW,
    )
    assert items == []


def test_parse_gdelt_tolerates_articles_key_missing():
    items = parse_gdelt_response(
        source_id="x", body='{"meta": "ok"}', fetched_at=_NOW,
    )
    assert items == []
