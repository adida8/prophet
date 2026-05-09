"""ETag from content hash.

Faktor's CDN/edge will key on this for `If-None-Match`. We compute a
deterministic hash over canonical JSON (sorted keys, no whitespace) so
identical content yields identical ETag regardless of when it was written.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_etag(obj: Any) -> str:
    """Strong ETag — `"<sha256-hex>"` quoted per RFC 7232."""
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return f'"{digest}"'
