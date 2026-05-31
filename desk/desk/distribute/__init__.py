"""Distribute — outbound wire to external consumers (currently MTA only).

Sport-agnostic. Sits beside `publish/` rather than inside it because the
publisher writes to local disk (the canonical artefact) and the
distribute layer ships those artefacts to external consumers — different
durability stories, different failure modes, different config surface.

The contract: every match the publisher writes is byte-identical to the
payload distribute sends. The disk file IS the receipt for what we
pushed; debugging a delivery means reading the file, not reconstructing
it. See `desk/docs/adr/0001-withdrawn-verdict-state.md` for the
lifecycle story.

Public surface:
    enqueue_match(match, body_bytes)       — fire-and-forget enqueue (match)
    enqueue_outright(published, ...)        — fire-and-forget enqueue (outright)
    detect_withdrawn(prior, current, ...)  — emit withdrawn payloads
    drain_once(...)                         — single worker sweep
"""

from desk.distribute.config import DistributeConfig, load_config  # noqa: F401
from desk.distribute.enqueue import (  # noqa: F401
    BodyTooLarge,
    canonical_body,
    enqueue_match,
)
from desk.distribute.outright import (  # noqa: F401
    canonical_body_outright,
    enqueue_outright,
    outright_wire_payload,
)
from desk.distribute.outbox import Outbox, OutboxRow  # noqa: F401
from desk.distribute.signing import sign, verify  # noqa: F401
from desk.distribute.withdrawn import (  # noqa: F401
    detect_and_emit as detect_withdrawn,
    snapshot_prior_index,
)
from desk.distribute.worker import drain_once  # noqa: F401
