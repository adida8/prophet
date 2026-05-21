"""RSS 2.0 + Atom feed parser → `SourceItem[]`.

We roll our own (stdlib `xml.etree.ElementTree`) instead of pulling in
feedparser. The trusted-core seed is hand-picked, well-formed feeds —
the breadth of feedparser's quirks-mode handling buys us nothing here.
If we ever add a feed that needs it, swap this module out; the public
function signature is the boundary.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from desk.signals.canonical import canonical_url
from desk.signals.models import SourceItem

_LOG = logging.getLogger(__name__)
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def parse_feed(*, source_id: str, body: str, fetched_at: datetime) -> list[SourceItem]:
    """Parse a feed body into items. Raises on malformed XML; skips
    entries with no usable link or title."""
    root = ET.fromstring(body)
    tag = _localname(root.tag)
    if tag == "rss":
        return list(_parse_rss(root, source_id, fetched_at))
    if tag == "feed":
        return list(_parse_atom(root, source_id, fetched_at))
    raise ValueError(f"unrecognised feed root element: {tag!r}")


def _localname(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _parse_rss(root, source_id: str, fetched_at: datetime) -> Iterable[SourceItem]:
    channel = root.find("channel")
    if channel is None:
        return
    for item in channel.findall("item"):
        link  = (item.findtext("link")        or "").strip()
        title = (item.findtext("title")       or "").strip()
        if not link or not title:
            continue
        body = (item.findtext("description") or "").strip()
        published = _parse_rfc822(item.findtext("pubDate"))
        yield _build_item(source_id, link, title, body, published, fetched_at)


def _parse_atom(root, source_id: str, fetched_at: datetime) -> Iterable[SourceItem]:
    for entry in root.findall(_ATOM_NS + "entry"):
        link = _atom_link(entry)
        title = (entry.findtext(_ATOM_NS + "title") or "").strip()
        if not link or not title:
            continue
        body = (
            entry.findtext(_ATOM_NS + "content")
            or entry.findtext(_ATOM_NS + "summary")
            or ""
        ).strip()
        published = _parse_rfc3339(
            entry.findtext(_ATOM_NS + "published")
            or entry.findtext(_ATOM_NS + "updated")
        )
        yield _build_item(source_id, link, title, body, published, fetched_at)


def _atom_link(entry) -> str:
    """Atom can carry multiple <link> elements with different `rel`s.
    Prefer rel="alternate"; fall back to the first href we see."""
    links = entry.findall(_ATOM_NS + "link")
    for link in links:
        if link.get("rel", "alternate") == "alternate":
            href = (link.get("href") or "").strip()
            if href:
                return href
    for link in links:
        href = (link.get("href") or "").strip()
        if href:
            return href
    return ""


def _build_item(source_id, url, title, body, published_at, fetched_at) -> SourceItem:
    canon = canonical_url(url)
    content = hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest()
    return SourceItem(
        source_id=source_id,
        url=url,
        canonical_url=canon,
        title=title,
        body=body,
        published_at=published_at,
        fetched_at=fetched_at,
        content_hash=content,
    )


def _parse_rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_rfc3339(value: str | None) -> datetime | None:
    if not value:
        return None
    # datetime.fromisoformat in 3.11+ handles most ISO 8601, but trailing
    # 'Z' is only accepted from 3.11 onwards. Replace defensively.
    s = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
