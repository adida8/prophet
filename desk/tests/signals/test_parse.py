"""RSS 2.0 + Atom feed parser."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.signals.parse import parse_feed

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ── RSS 2.0 ───────────────────────────────────────────────────────────

def test_rss_parses_items():
    items = parse_feed(source_id="sample-rss", body=_read("sample-rss.xml"), fetched_at=_NOW)
    assert len(items) == 2  # third item has empty title → dropped
    titles = [i.title for i in items]
    assert "Mbappé out with calf strain" in titles
    assert "Argentina name unchanged XI for opener" in titles


def test_rss_canonicalizes_url():
    items = parse_feed(source_id="sample-rss", body=_read("sample-rss.xml"), fetched_at=_NOW)
    mbappe = next(i for i in items if "Mbappé" in i.title)
    # utm_* stripped on the canonical URL; raw URL untouched
    assert mbappe.canonical_url == "https://example.com/sport/football/mbappe-calf"
    assert "utm_source" in mbappe.url


def test_rss_parses_pubdate_to_aware_datetime():
    items = parse_feed(source_id="sample-rss", body=_read("sample-rss.xml"), fetched_at=_NOW)
    mbappe = next(i for i in items if "Mbappé" in i.title)
    assert mbappe.published_at == datetime(2026, 5, 19, 8, 15, tzinfo=timezone.utc)


def test_rss_content_hash_is_stable():
    a = parse_feed(source_id="sample-rss", body=_read("sample-rss.xml"), fetched_at=_NOW)
    b = parse_feed(source_id="sample-rss", body=_read("sample-rss.xml"), fetched_at=_NOW)
    assert [i.content_hash for i in a] == [i.content_hash for i in b]


def test_rss_content_hash_differs_when_body_changes():
    base = _read("sample-rss.xml")
    edited = base.replace(
        "miss tomorrow's match",
        "miss the next two matches",
    )
    a = parse_feed(source_id="sample-rss", body=base,   fetched_at=_NOW)
    b = parse_feed(source_id="sample-rss", body=edited, fetched_at=_NOW)
    a_hash = next(i.content_hash for i in a if "Mbappé" in i.title)
    b_hash = next(i.content_hash for i in b if "Mbappé" in i.title)
    assert a_hash != b_hash


# ── Atom ──────────────────────────────────────────────────────────────

def test_atom_parses_entries():
    items = parse_feed(source_id="sample-atom", body=_read("sample-atom.xml"), fetched_at=_NOW)
    assert len(items) == 2
    titles = [i.title for i in items]
    assert "Brazil drop Vinicius after training spat" in titles


def test_atom_prefers_alternate_link():
    items = parse_feed(source_id="sample-atom", body=_read("sample-atom.xml"), fetched_at=_NOW)
    vini = next(i for i in items if "Vinicius" in i.title)
    # not the rel="replies" link
    assert vini.canonical_url == "https://example.org/articles/vini-dropped"


def test_atom_parses_published_or_updated_to_aware_datetime():
    items = parse_feed(source_id="sample-atom", body=_read("sample-atom.xml"), fetched_at=_NOW)
    vini = next(i for i in items if "Vinicius" in i.title)
    assert vini.published_at == datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc)
    # second entry has no <published>, falls back to <updated>
    england = next(i for i in items if "England" in i.title)
    assert england.published_at == datetime(2026, 5, 18, 18, 30, tzinfo=timezone.utc)


def test_atom_falls_back_to_summary_when_no_content():
    items = parse_feed(source_id="sample-atom", body=_read("sample-atom.xml"), fetched_at=_NOW)
    vini = next(i for i in items if "Vinicius" in i.title)
    assert "miss the qualifier" in vini.body


# ── error paths ───────────────────────────────────────────────────────

def test_rejects_unknown_root():
    body = "<?xml version='1.0'?><something><other/></something>"
    with pytest.raises(ValueError, match="unrecognised feed root"):
        parse_feed(source_id="x", body=body, fetched_at=_NOW)


def test_raises_on_malformed_xml():
    from xml.etree.ElementTree import ParseError
    with pytest.raises(ParseError):
        parse_feed(source_id="x", body="<not really xml", fetched_at=_NOW)
