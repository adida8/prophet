"""Aggregator clients — long-tail discovery via cross-source queries.

Today GDELT (https://gdeltproject.org) is the only aggregator we
support. It's a free, global, multilingual index of news articles, no
API key required. The price for free + global is depth: the DOC API
returns headlines + URLs + outlet metadata, not article bodies. We
therefore store the headline as both `title` AND `body` — the
extractor sees the same string twice and either pulls a signal it can
verbatim-cite from the headline or returns nothing.

Long-tail items always route editorial-only by the trust gate (`tier =
long_tail` ⇒ `editorial_only`) so a headline-as-quote can never become
a model feature. The `desk fetch-signals` CLI defaults to skipping the
aggregator path; operators opt in with `--include-long-tail` so the
extra cost is a conscious choice.

The aggregator feed_ref uses a small URI scheme:

    gdelt:query=football+OR+soccer

`query=` is the GDELT search expression — see
https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ for syntax.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from desk.signals.canonical import canonical_url
from desk.signals.models import SourceItem

_LOG = logging.getLogger(__name__)
_GDELT_BASE         = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_MAXRECORDS  = 75
DEFAULT_TIMESPAN    = "3days"


def parse_aggregator_ref(feed_ref: str) -> tuple[str, str]:
    """Split `gdelt:query=foo` into (`gdelt`, `query=foo`). Raises
    `ValueError` on a missing scheme."""
    if ":" not in feed_ref:
        raise ValueError(f"aggregator feed_ref missing scheme: {feed_ref!r}")
    scheme, _, rest = feed_ref.partition(":")
    return scheme.lower(), rest


def build_gdelt_url(
    raw_query: str, *,
    maxrecords: int = DEFAULT_MAXRECORDS,
    timespan:   str = DEFAULT_TIMESPAN,
) -> str:
    """Build the GDELT DOC ArtList URL from a feed_ref's raw_query.

    Accepts either `query=...` (matches the feed_ref shape) or a bare
    query string."""
    query = raw_query
    if query.startswith("query="):
        query = query[len("query="):]
    params = {
        "query":      query,
        "mode":       "ArtList",
        "format":     "json",
        "maxrecords": str(maxrecords),
        "timespan":   timespan,
    }
    return f"{_GDELT_BASE}?{urlencode(params)}"


def parse_gdelt_response(
    *, source_id: str, body: str, fetched_at: datetime,
) -> list[SourceItem]:
    """Parse a GDELT DOC ArtList JSON response into `SourceItem` rows.

    Skips entries with no URL or no title. Tolerates missing seendate
    by leaving `published_at` unset."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"GDELT response is not valid JSON: {e}") from e
    articles = data.get("articles") or []
    out: list[SourceItem] = []
    for art in articles:
        url   = (art.get("url")   or "").strip()
        title = (art.get("title") or "").strip()
        if not url or not title:
            continue
        # GDELT doesn't return article bodies; the headline IS the body.
        # The extractor's citation guarantee will only allow signals
        # whose quote appears in this string — so anything beyond the
        # headline is structurally rejected.
        body_text = title
        published = _parse_gdelt_date(art.get("seendate"))
        content_hash = hashlib.sha256(
            f"{title}\n{body_text}".encode("utf-8")
        ).hexdigest()
        out.append(SourceItem(
            source_id=source_id,
            url=url,
            canonical_url=canonical_url(url),
            title=title,
            body=body_text,
            published_at=published,
            fetched_at=fetched_at,
            content_hash=content_hash,
        ))
    return out


def _parse_gdelt_date(value) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    # GDELT's most common form: "20260519T080000Z" (YYYYMMDDTHHMMSSZ).
    if len(s) == 16 and s.endswith("Z"):
        try:
            return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    # Fall back to ISO 8601 — some endpoints normalise dates.
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
