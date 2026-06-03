"""Canonical JSON encoder — copied verbatim from the live Desk.

`canonical_json` is the single source of truth for wire shape
(sort_keys=True, no whitespace). The HMAC signing path depends on this
being byte-identical to what the live Desk produces, so do not change
the separators or sort behaviour.
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
