"""Activity-signals background loop — sibling to desk_refresh_loop.py.

Three independent asyncio tasks, each on its own cadence:
  aggregate_match_activity  every  60 s
  seed_match_activity       every  8 min   (gated by ACTIVITY_SEED_ENABLED)
  prune_old_views           every 24 h

Run from main.py via `asyncio.create_task(run_activity_loop(), ...)`. The
loop logs + sleeps through any exception so a transient Postgres blip
never tears down the rest of the server.

DATABASE_URL must be set. If absent at boot, the loop logs once and
exits — the server stays up, activity routes 500 cleanly until env is
configured.
"""

from __future__ import annotations

import asyncio
import logging
import os

from activity.db import open_pool
from activity.jobs import (
    aggregate_match_activity,
    prune_old_views,
    seed_match_activity,
)

log = logging.getLogger("activity.loop")

_AGGREGATE_INTERVAL_SEC = int(os.getenv("ACTIVITY_AGGREGATE_SEC", "60"))
_SEED_INTERVAL_SEC = int(os.getenv("ACTIVITY_SEED_SEC", "480"))
_PRUNE_INTERVAL_SEC = int(os.getenv("ACTIVITY_PRUNE_SEC", "86400"))
_INITIAL_DELAY_SEC = int(os.getenv("ACTIVITY_INITIAL_DELAY_SEC", "30"))


async def _safe_loop(name: str, interval: int, fn) -> None:
    """Run `fn` forever on `interval`, logging exceptions without dying."""
    while True:
        try:
            result = await fn()
            log.info("activity:%s ok %s", name, result)
        except Exception:  # noqa: BLE001
            log.exception("activity:%s failed; sleeping then retrying", name)
        await asyncio.sleep(interval)


async def run_activity_loop() -> None:
    if not os.getenv("DATABASE_URL"):
        log.warning(
            "activity loop disabled — DATABASE_URL not set. The activity API "
            "routes will return 500 until Postgres is wired up."
        )
        return

    # Open the pool here so the loop is self-contained; the server lifespan
    # also opens it (idempotent) so HTTP routes don't depend on this loop.
    await open_pool()
    await asyncio.sleep(_INITIAL_DELAY_SEC)

    seed_enabled = os.getenv("ACTIVITY_SEED_ENABLED", "1") == "1"

    tasks = [
        asyncio.create_task(
            _safe_loop("aggregate", _AGGREGATE_INTERVAL_SEC, aggregate_match_activity),
            name="activity:aggregate",
        ),
        asyncio.create_task(
            _safe_loop("prune", _PRUNE_INTERVAL_SEC, prune_old_views),
            name="activity:prune",
        ),
    ]
    if seed_enabled:
        tasks.append(asyncio.create_task(
            _safe_loop("seed", _SEED_INTERVAL_SEC, seed_match_activity),
            name="activity:seed",
        ))
    else:
        log.info("activity:seed disabled via ACTIVITY_SEED_ENABLED=0")

    await asyncio.gather(*tasks)
