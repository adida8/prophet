"""Public enqueue helper for the runner.

Single entry point so the runner doesn't need to know about the outbox,
the byte budget, or how config gets resolved. Idempotent at the
call-site level — calling enqueue with the same (match_id, updated_at)
twice produces one pending row via the outbox collapse rule.
"""

from __future__ import annotations

import logging
from datetime import datetime

from desk.distribute.config import DistributeConfig
from desk.distribute.outbox import Outbox
from desk.publish import MatchOutput
from desk.publish.etag import canonical_json

log = logging.getLogger("desk.distribute.enqueue")


class BodyTooLarge(ValueError):
    """Raised when a payload exceeds the configured byte ceiling.

    Defensive: contract bounds put the worst-case JSON at ~32KB, so
    a hit on this guard means a contract drift we want to see loudly.
    """


def canonical_body(match: MatchOutput) -> bytes:
    """The single canonical encoding used by both the disk writer and
    the distribute wire. `desk/desk/publish/etag.py::canonical_json` is
    the source of truth for shape (sort_keys=True, no whitespace)."""
    return canonical_json(match.model_dump(mode="json", exclude_none=False)).encode("utf-8")


def enqueue_match(
    match: MatchOutput,
    *,
    config: DistributeConfig,
    outbox: Outbox | None = None,
    body: bytes | None = None,
) -> int | None:
    """Enqueue one match for delivery.

    Returns the outbox row id on enqueue, or None when push is disabled
    (the runner calls this unconditionally; the gate lives here so the
    caller is one branch simpler).

    Raises BodyTooLarge when the canonical body exceeds config.max_body_bytes.
    The runner catches it, logs, and continues — the on-disk write has
    already happened, so the data isn't lost; the wire just doesn't carry
    this payload until the contract is brought back under budget.
    """
    if not config.push_enabled:
        return None

    body = body if body is not None else canonical_body(match)
    if len(body) > config.max_body_bytes:
        raise BodyTooLarge(
            f"match {match.match_id} body {len(body)} bytes exceeds "
            f"max {config.max_body_bytes}"
        )

    updated_at_iso = _iso(match.updated_at)
    owns_outbox = outbox is None
    box = outbox if outbox is not None else Outbox(config.db_path)
    try:
        return box.enqueue(
            match_id=match.match_id,
            updated_at=updated_at_iso,
            body=body,
        )
    finally:
        if owns_outbox:
            box.close()


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")
