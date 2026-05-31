"""Outright wire — transform a published outright dict into the MTA payload.

Matches are already `MatchOutput`-shaped, so `enqueue.canonical_body` can
dump the model directly. Outrights publish a plain dict (see
`desk/desk/outrights/publish.py::build_payload`) whose spine already
mirrors `MatchOutput`. Two adjustments bring it onto the MTA wire
contract (v1.2, agreed with MTAI 2026-05-31):

  1. add ``content_type: "outright"`` so MTA routes it off the same
     webhook as matches (matches default to ``"match"`` on MTA's side).
  2. lift ``model.hard_signal_adjustments`` to a top-level
     ``hard_signal_adjustments`` list so it sits where matches carry it.
     The objects stay structured (MTA relaxed that field to objects via
     passthrough); outright nudges key on ``team`` — there is no ``a/b``
     ``side`` the way a two-team match has.

The on-disk JSON is left untouched — this transform runs only on the
wire path, so the static site generator + the Faktor contract are
unaffected. Keyed on ``outright_id`` for the outbox collapse rule,
exactly like matches key on ``match_id``.
"""

from __future__ import annotations

import copy as _copy
import logging

from desk.distribute.config import DistributeConfig
from desk.distribute.enqueue import BodyTooLarge
from desk.distribute.outbox import Outbox
from desk.publish.etag import canonical_json

log = logging.getLogger("desk.distribute.outright")

CONTENT_TYPE = "outright"


def outright_wire_payload(published: dict) -> dict:
    """Map a published outright dict onto the MTA wire shape.

    Pure + non-mutating: returns a new dict and leaves ``published``
    alone (it's the on-disk artefact). See the module docstring for the
    two transforms applied.
    """
    wire = _copy.deepcopy(published)
    wire["content_type"] = CONTENT_TYPE

    # Lift hard-signal adjustments out of the model block to the top
    # level so the wire shape matches MatchOutput. Always present (even
    # empty) for spine parity — the published dict only carries the key
    # under `model` when non-empty.
    model = wire.get("model")
    hsa: list = []
    if isinstance(model, dict):
        hsa = model.pop("hard_signal_adjustments", []) or []
    wire["hard_signal_adjustments"] = hsa
    return wire


def canonical_body_outright(published: dict) -> bytes:
    """Canonical-JSON bytes for the outright wire payload.

    Same encoder matches use (sorted keys, no whitespace) so the HMAC
    signing path in `signing.py` is identical regardless of payload type.
    """
    return canonical_json(outright_wire_payload(published)).encode("utf-8")


def enqueue_outright(
    published: dict,
    *,
    config: DistributeConfig,
    outbox: Outbox | None = None,
    body: bytes | None = None,
) -> int | None:
    """Enqueue one outright for delivery.

    Mirrors `enqueue_match`: keyed on ``outright_id``, idempotent via the
    outbox collapse rule, returns None when push is disabled (the caller
    can invoke unconditionally — the gate lives here).

    Raises BodyTooLarge when the canonical body exceeds
    ``config.max_body_bytes``. The caller catches it, logs, and continues
    — the on-disk write has already happened.
    """
    if not config.push_enabled:
        return None

    outright_id = published["outright_id"]
    body = body if body is not None else canonical_body_outright(published)
    if len(body) > config.max_body_bytes:
        raise BodyTooLarge(
            f"outright {outright_id} body {len(body)} bytes exceeds "
            f"max {config.max_body_bytes}"
        )

    updated_at = str(published.get("updated_at", ""))
    owns_outbox = outbox is None
    box = outbox if outbox is not None else Outbox(config.db_path)
    try:
        # Outbox keys on a generic text id (column name `match_id`); the
        # outright_id (`fb-wc26-winner`) shares the same namespace but
        # never collides with a real match_id — match ids always carry a
        # `-yyyymmdd` suffix an outright id lacks.
        return box.enqueue(
            match_id=outright_id,
            updated_at=updated_at,
            body=body,
        )
    finally:
        if owns_outbox:
            box.close()
