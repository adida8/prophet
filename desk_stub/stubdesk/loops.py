"""Background async loops for the stub server.

Two independent loops, both run in-process from the FastAPI lifespan
(no subprocess juggling — the stub is one self-contained package):

  * refresh loop  — every DESK_STUB_REFRESH_SEC, run the engine
                    (re-enqueue the frozen JSON). This is the "stub
                    engine completes → calls MTAI to update" beat.
  * drain loop    — every DESK_DISTRIBUTE_TICK_SEC, drain the outbox →
                    POST to MTAI. Identical cadence/behaviour to the
                    live Desk's desk_distribute_loop.py.

Both honour DESK_AUTORUN=0 as a kill switch and exit cleanly when push
is disabled.
"""

from __future__ import annotations

import asyncio
import logging
import os

from stubdesk import engine
from stubdesk.client import MTAClient
from stubdesk.config import load_config
from stubdesk.outbox import Outbox
from stubdesk.worker import drain_once

log = logging.getLogger("stubdesk.loops")

DEFAULT_REFRESH_SEC = 3600          # re-enqueue the frozen set hourly
DEFAULT_DRAIN_TICK_SEC = 30
REFRESH_INITIAL_DELAY_SEC = int(os.getenv("DESK_STUB_REFRESH_INITIAL_DELAY_SEC", "20"))
DRAIN_INITIAL_DELAY_SEC = int(os.getenv("DESK_DISTRIBUTE_INITIAL_DELAY_SEC", "75"))


def _autorun_enabled() -> bool:
    return os.getenv("DESK_AUTORUN", "1") == "1"


async def run_refresh_loop() -> None:
    if not _autorun_enabled():
        log.info("refresh loop disabled (DESK_AUTORUN=0)")
        return
    refresh_sec = int(os.getenv("DESK_STUB_REFRESH_SEC", str(DEFAULT_REFRESH_SEC)))
    if refresh_sec < 30:
        log.warning("DESK_STUB_REFRESH_SEC=%d clamped to 30", refresh_sec)
        refresh_sec = 30

    log.info(
        "refresh loop online — re-enqueue every %ds (boot tick in %ds)",
        refresh_sec, REFRESH_INITIAL_DELAY_SEC,
    )
    await asyncio.sleep(REFRESH_INITIAL_DELAY_SEC)
    while True:
        try:
            await asyncio.to_thread(engine.run_once)
        except Exception:
            log.exception("refresh loop tick failed")
        await asyncio.sleep(refresh_sec)


async def run_drain_loop() -> None:
    if not _autorun_enabled():
        log.info("drain loop disabled (DESK_AUTORUN=0)")
        return
    try:
        cfg = load_config()
    except ValueError as e:
        # push enabled but URL/secret missing — fail loud, don't crash boot.
        log.error("drain loop config error: %s", e)
        return
    if not cfg.push_enabled:
        log.info("drain loop disabled (DESK_DISTRIBUTE_PUSH != 1)")
        return
    assert cfg.webhook_url and cfg.webhook_secret

    tick_sec = int(os.getenv("DESK_DISTRIBUTE_TICK_SEC", str(DEFAULT_DRAIN_TICK_SEC)))
    if tick_sec < 5:
        log.warning("DESK_DISTRIBUTE_TICK_SEC=%d clamped to 5", tick_sec)
        tick_sec = 5

    log.info(
        "drain loop online — tick every %ds (boot tick in %ds)",
        tick_sec, DRAIN_INITIAL_DELAY_SEC,
    )
    await asyncio.sleep(DRAIN_INITIAL_DELAY_SEC)

    client = MTAClient(webhook_url=cfg.webhook_url, webhook_secret=cfg.webhook_secret)
    box = Outbox(cfg.db_path)
    try:
        while True:
            try:
                stats = await drain_once(
                    box, client,
                    max_in_flight=cfg.max_in_flight,
                    rate_per_min=cfg.rate_per_min,
                )
                if stats.claimed:
                    log.info(
                        "drain: claimed=%d sent=%d retried=%d dead=%d errors=%s",
                        stats.claimed, stats.sent, stats.retried,
                        stats.dead, stats.errors_by_kind,
                    )
            except Exception:
                log.exception("drain loop tick failed")
            await asyncio.sleep(tick_sec)
    finally:
        await client.aclose()
        box.close()
