"""Daily-report background loop — sibling to activity_refresh_loop.py.

Hourly tick. When the current UTC hour matches DAILY_REPORT_HOUR (8 by
default) and DAILY_REPORT_ENABLED=1, fires `daily_report.run_once()`
once for yesterday's UTC day. Idempotency lives in daily_report.py
(state file at {ops_root}/daily_report/last_sent.json), so a duplicate
tick inside the hour is a no-op.

Hardened to mirror activity_refresh_loop.py:
  - DAILY_REPORT_ENABLED=0 → log + exit (the loop is the only place
    that fires the send; the standalone CLI still works).
  - Any exception in a tick is logged + swallowed; the loop keeps
    running so a transient SMTP / Postgres blip doesn't tear down
    main.py via asyncio.gather.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from daily_report import load_config, run_once
from loop_registry import is_enabled

log = logging.getLogger("daily_report.loop")

LOOP_ID = "daily_report"
_TICK_SEC = int(os.getenv("DAILY_REPORT_TICK_SEC", "3600") or "3600")
_INITIAL_DELAY_SEC = int(os.getenv("DAILY_REPORT_INITIAL_DELAY_SEC", "60") or "60")


async def _safe_tick(cfg) -> None:
    try:
        result = await run_once(cfg)
        log.info("daily_report tick ok: %s", result)
    except Exception:  # noqa: BLE001
        log.exception("daily_report tick failed")


async def run_daily_report_loop() -> None:
    # load_config() raises hard when DAILY_REPORT_ENABLED=1 but SMTP/recipient
    # vars are missing. The loop is gathered alongside the FastAPI server, so a
    # naked raise here propagates through asyncio.gather and brings the whole
    # site down. Catch it: log + exit the task. The server (and every other
    # loop) keeps running.
    try:
        cfg = load_config()
    except Exception:  # noqa: BLE001
        log.exception(
            "daily report loop: load_config() failed; loop disabled. The rest "
            "of the app keeps running. Fix the missing env vars on Railway "
            "(SMTP_HOST/USER/PASS, DAILY_REPORT_TO) or set "
            "DAILY_REPORT_ENABLED=0 to silence this."
        )
        return

    if not cfg.enabled:
        log.warning(
            "daily report loop disabled — DAILY_REPORT_ENABLED!=1. "
            "Run python daily_report.py --once manually if needed."
        )
        return

    await asyncio.sleep(_INITIAL_DELAY_SEC)
    log.info(
        "daily report loop: starting (hour=%s UTC, tick=%ds, to=%s)",
        cfg.daily_report_hour, _TICK_SEC, ",".join(cfg.mail_to),
    )

    while True:
        if not is_enabled(LOOP_ID):
            await asyncio.sleep(min(_TICK_SEC, 60))
            continue
        try:
            now = datetime.now(timezone.utc)
            if now.hour == cfg.daily_report_hour:
                await _safe_tick(cfg)
        except Exception:  # noqa: BLE001
            log.exception("daily report loop: outer tick error")
        await asyncio.sleep(_TICK_SEC)
