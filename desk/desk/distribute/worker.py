"""Worker — single-sweep outbox drainer.

Designed for repeated short invocations (every 30s via the project-root
async task) rather than a long-running loop. Each call:

  1. Reads pending rows due now (claim_due).
  2. Respects a token-bucket cap so we never exceed
     `rate_per_min` requests in any rolling minute window — keeps us
     comfortably under MTA's 60-req/min/source-IP ceiling even during
     burst-publish (e.g. ~70 fixtures on a group-stage refresh).
  3. Dispatches up to `max_in_flight` concurrently.
  4. Maps the typed `DeliverResult` to outbox state transitions:
       Ok        → mark_sent (delete)
       Retryable → mark_retry with the next backoff step, or
                   mark_dead if the schedule is exhausted
       Permanent → mark_dead immediately (no retry)

Returns a `DrainStats` so the caller can log meaningful metrics. Never
raises on a per-row failure — a misbehaving row gets dead-lettered, the
sweep continues.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from desk.distribute.client import DeliverResult, MTAClient, Ok, Permanent, Retryable
from desk.distribute.config import RETRY_SCHEDULE_SEC
from desk.distribute.outbox import Outbox, OutboxRow

log = logging.getLogger("desk.distribute.worker")


@dataclass
class DrainStats:
    claimed:        int = 0
    sent:           int = 0
    retried:        int = 0
    dead:           int = 0
    errors_by_kind: dict[str, int] = field(default_factory=dict)


async def drain_once(
    outbox: Outbox,
    client: MTAClient,
    *,
    now: int | None = None,
    max_in_flight: int = 8,
    rate_per_min: int = 50,
    max_claim: int | None = None,
) -> DrainStats:
    """One sweep over the outbox. Safe to call repeatedly."""
    now = now if now is not None else int(time.time())

    # Token-bucket cap. We can dispatch at most this many requests per
    # call, regardless of in-flight concurrency. Subsequent claims wait
    # for the next sweep.
    budget = rate_per_min
    if max_claim is not None:
        budget = min(budget, max_claim)

    rows = outbox.claim_due(now=now, limit=budget)
    stats = DrainStats(claimed=len(rows))
    if not rows:
        return stats

    semaphore = asyncio.Semaphore(max_in_flight)

    async def _one(row: OutboxRow) -> None:
        async with semaphore:
            try:
                result = await client.deliver(row.body, now=now)
            except Exception as e:                          # noqa: BLE001
                # The client maps known errors itself; an exception here
                # is a bug in OUR code. Surface as retryable so we don't
                # dead-letter on a transient implementation hiccup, but
                # log loud.
                log.exception("deliver crashed for row %d (match=%s)",
                              row.id, row.match_id)
                result = Retryable(reason=f"deliver crashed: {type(e).__name__}: {e}")
            _apply(outbox, row, result, now, stats)

    await asyncio.gather(*(_one(r) for r in rows))
    return stats


def _apply(outbox: Outbox, row: OutboxRow, result: DeliverResult,
           now: int, stats: DrainStats) -> None:
    if isinstance(result, Ok):
        outbox.mark_sent(row.id)
        stats.sent += 1
        return

    if isinstance(result, Permanent):
        outbox.mark_dead(row.id, reason=f"permanent: {result.reason}")
        stats.dead += 1
        kind = f"perm_{result.status_code or 'na'}"
        stats.errors_by_kind[kind] = stats.errors_by_kind.get(kind, 0) + 1
        log.error("dead-lettered row %d (match=%s): %s",
                  row.id, row.match_id, result.reason)
        return

    # Retryable
    assert isinstance(result, Retryable)
    next_attempt_idx = row.attempts
    if next_attempt_idx >= len(RETRY_SCHEDULE_SEC):
        outbox.mark_dead(row.id, reason=f"exhausted: {result.reason}")
        stats.dead += 1
        stats.errors_by_kind["exhausted"] = stats.errors_by_kind.get("exhausted", 0) + 1
        log.error("dead-lettered row %d (match=%s): exhausted after %d attempts — %s",
                  row.id, row.match_id, row.attempts, result.reason)
        return

    backoff = RETRY_SCHEDULE_SEC[next_attempt_idx]
    outbox.mark_retry(
        row.id,
        next_attempt_at=now + backoff,
        last_error=result.reason,
    )
    stats.retried += 1
    kind = f"retry_{result.status_code or 'net'}"
    stats.errors_by_kind[kind] = stats.errors_by_kind.get(kind, 0) + 1
    log.warning("retry row %d (match=%s) attempt=%d, next in %ds — %s",
                row.id, row.match_id, row.attempts + 1, backoff, result.reason)
