"""URL canonicalization for dedupe.

Two articles published with different tracking params or fragment IDs
must hash to the same key, otherwise the cache stores the same story
twice and the extractor pays twice. We strip the well-known tracker
params + fragments, lowercase host, drop default ports, and sort the
remaining query keys for stable ordering.

Non-http(s) URLs pass through untouched.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Tracker params seen in trusted-core feeds. Conservative — only strip
# things that are obviously analytics, not anything that could change
# the page (no "id", "p", "story", etc.).
_TRACKER_EXACT = frozenset({
    "fbclid", "gclid", "msclkid", "yclid", "dclid", "igshid",
    "_ga", "_gl", "ref", "ref_src", "ref_url", "feature", "share",
    "CMP", "cmpid", "ito", "ns_campaign", "ns_mchannel", "ns_source",
})
_TRACKER_PREFIXES = ("utm_", "mc_", "_hs", "vero_", "ns_")


def _is_tracker(key: str) -> bool:
    if key in _TRACKER_EXACT:
        return True
    return any(key.startswith(p) for p in _TRACKER_PREFIXES)


def canonical_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return raw  # leave mailto:, data:, etc. alone

    host = (parts.hostname or "").lower()
    if not host:
        return raw
    netloc = host
    if parts.port and parts.port not in {80, 443}:
        netloc = f"{host}:{parts.port}"

    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not _is_tracker(k)
    ]
    kept.sort()
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, ""))
