"""Wire encoding + enqueue for the stub.

The live Desk builds a `MatchOutput` Pydantic model, then encodes it with
`canonical_json(model.model_dump(mode="json"))`. The on-disk JSON file
the publisher wrote IS that same canonical encoding — so for the stub we
can skip the contract entirely and canonicalise the loaded dict directly.
The bytes are identical because `canonical_json` sorts keys.

Two payload shapes, mirroring the live Desk:

  * Match    — canonical JSON of the on-disk dict. When
               `include_cross_venue=False`, the three ADR 0004 fields are
               stripped from the wire copy (the disk file is untouched).
  * Outright — `outright_wire_payload()` (add content_type, lift
               hard_signal_adjustments to top level) then canonical JSON.

This keeps the HMAC body byte-identical to what the live Desk pushes, so
MTAI's verifier + validator behave exactly the same after cutover.
"""

from __future__ import annotations

import copy as _copy
import logging

from stubdesk.config import DistributeConfig
from stubdesk.etag import canonical_json
from stubdesk.outbox import Outbox

log = logging.getLogger("stubdesk.wire")

CONTENT_TYPE_OUTRIGHT = "outright"

# Fields added by ADR 0004 (cross-venue prices). Stripped from the wire
# body when the consumer's validator doesn't know about them.
_CROSS_VENUE_FIELDS: tuple[str, ...] = ("market_prices", "consensus_fair", "region")


class BodyTooLarge(ValueError):
    """Raised when a payload exceeds the configured byte ceiling."""


# ── match ──────────────────────────────────────────────────────────────

def canonical_body_match(match: dict, *, include_cross_venue: bool = True) -> bytes:
    payload = _copy.deepcopy(match)
    if not include_cross_venue:
        for k in _CROSS_VENUE_FIELDS:
            payload.pop(k, None)
    return canonical_json(payload).encode("utf-8")


def enqueue_match(
    match: dict,
    *,
    config: DistributeConfig,
    outbox: Outbox | None = None,
    body: bytes | None = None,
) -> int | None:
    """Enqueue one frozen match dict for delivery. None when push disabled."""
    if not config.push_enabled:
        return None

    body = body if body is not None else canonical_body_match(
        match, include_cross_venue=config.include_cross_venue,
    )
    match_id = match["match_id"]
    if len(body) > config.max_body_bytes:
        raise BodyTooLarge(
            f"match {match_id} body {len(body)} bytes exceeds max {config.max_body_bytes}"
        )

    updated_at = str(match.get("updated_at", ""))
    owns_outbox = outbox is None
    box = outbox if outbox is not None else Outbox(config.db_path)
    try:
        return box.enqueue(match_id=match_id, updated_at=updated_at, body=body)
    finally:
        if owns_outbox:
            box.close()


# ── outright ─────────────────────────────────────────────────────────────

def outright_wire_payload(published: dict) -> dict:
    """Map a published outright dict onto the MTA wire shape.

    Pure + non-mutating. Kept in lockstep with the live Desk's
    `desk/desk/distribute/outright.py::outright_wire_payload`.
    """
    wire = _copy.deepcopy(published)
    wire["content_type"] = CONTENT_TYPE_OUTRIGHT
    model = wire.get("model")
    hsa: list = []
    if isinstance(model, dict):
        hsa = model.pop("hard_signal_adjustments", []) or []
    wire["hard_signal_adjustments"] = hsa
    return wire


def canonical_body_outright(published: dict) -> bytes:
    return canonical_json(outright_wire_payload(published)).encode("utf-8")


def enqueue_outright(
    published: dict,
    *,
    config: DistributeConfig,
    outbox: Outbox | None = None,
    body: bytes | None = None,
) -> int | None:
    """Enqueue one frozen outright dict for delivery. None when push disabled."""
    if not config.push_enabled:
        return None

    outright_id = published["outright_id"]
    body = body if body is not None else canonical_body_outright(published)
    if len(body) > config.max_body_bytes:
        raise BodyTooLarge(
            f"outright {outright_id} body {len(body)} bytes exceeds max {config.max_body_bytes}"
        )

    updated_at = str(published.get("updated_at", ""))
    owns_outbox = outbox is None
    box = outbox if outbox is not None else Outbox(config.db_path)
    try:
        return box.enqueue(match_id=outright_id, updated_at=updated_at, body=body)
    finally:
        if owns_outbox:
            box.close()
