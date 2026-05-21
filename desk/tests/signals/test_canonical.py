"""Canonical-URL normalization."""

from __future__ import annotations

import pytest

from desk.signals.canonical import canonical_url


@pytest.mark.parametrize("raw,expected", [
    # tracker stripping
    ("https://example.com/a?utm_source=rss&utm_medium=feed",         "https://example.com/a"),
    ("https://example.com/a?utm_campaign=spring&id=42",              "https://example.com/a?id=42"),
    ("https://example.com/a?fbclid=ZZZ",                             "https://example.com/a"),
    ("https://example.com/a?mc_cid=abc",                             "https://example.com/a"),
    ("https://example.com/a?CMP=share_btn",                          "https://example.com/a"),
    # fragment dropped
    ("https://example.com/a#section",                                "https://example.com/a"),
    # host lowercase
    ("https://Example.COM/Path",                                     "https://example.com/Path"),
    # default port stripped
    ("https://example.com:443/a",                                    "https://example.com/a"),
    ("http://example.com:80/a",                                      "http://example.com/a"),
    # query keys sorted (stable hashing)
    ("https://example.com/a?b=2&a=1",                                "https://example.com/a?a=1&b=2"),
    # trailing slash stripped (but not root)
    ("https://example.com/path/",                                    "https://example.com/path"),
    ("https://example.com/",                                         "https://example.com/"),
])
def test_canonicalization(raw, expected):
    assert canonical_url(raw) == expected


def test_non_http_url_passthrough():
    assert canonical_url("mailto:hello@oddsprimer.com") == "mailto:hello@oddsprimer.com"


def test_empty_returns_empty():
    assert canonical_url("") == ""


def test_two_links_to_same_article_canonicalize_equally():
    a = canonical_url("https://example.com/sport/x?utm_source=rss&utm_medium=feed#top")
    b = canonical_url("https://EXAMPLE.com/sport/x?fbclid=ZZZ")
    assert a == b == "https://example.com/sport/x"
