"""Site-QA background loop — sibling to daily_report_loop.py.

Hourly tick. When the current UTC hour matches SITE_QA_HOUR (7 by default)
and SITE_QA_ENABLED=1, fires `site_qa.run_once()` once for the day.
Idempotency lives in site_qa.py (state file at {ops_root}/site_qa/
last_sent.json), so a duplicate tick inside the hour is a no-op.

Hardened to mirror daily_report_loop.py:
  - load_config() raising (enabled but SMTP/recipient missing) is caught:
    log + exit the task, never tear down main.py via asyncio.gather.
  - SITE_QA_ENABLED=0 → log + exit.
  - Any per-tick exception is logged + swallowed; the loop keeps running
    so a transient SMTP / network blip doesn't kill the task.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from site_qa import load_config, run_once

log = logging.getLogger("site_qa.loop")

_TICK_SEC = int(os.getenv("SITE_QA_TICK_SEC", "3600") or "3600")
_INITIAL_DELAY_SEC = int(os.getenv("SITE_QA_INITIAL_DELAY_SEC", "90") or "90")


async def _safe_tick(cfg) -> None:
    try:
        result = await run_once(cfg)
        log.info("site_qa tick ok: %s", result)
    except Exception:  # noqa: BLE001
        log.exception("site_qa tick failed")


async def run_site_qa_loop() -> None:
    try:
        cfg = load_config()
    except Exception:  # noqa: BLE001
        log.exception(
            "site QA loop: load_config() failed; loop disabled. The rest of "
            "the app keeps running. Fix the missing env vars on Railway "
            "(SMTP_HOST/USER/PASS, SITE_QA_TO) or set SITE_QA_ENABLED=0."
        )
        return

    if not cfg.enabled:
        log.warning(
            "site QA loop disabled — SITE_QA_ENABLED!=1. "
            "Run python site_qa.py --once manually if needed."
        )
        return

    await asyncio.sleep(_INITIAL_DELAY_SEC)
    log.info(
        "site QA loop: starting (hour=%s UTC, tick=%ds, base=%s, to=%s)",
        cfg.qa_hour, _TICK_SEC, cfg.base_url, ",".join(cfg.mail_to),
    )

    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.hour == cfg.qa_hour:
                await _safe_tick(cfg)
        except Exception:  # noqa: BLE001
            log.exception("site QA loop: outer tick error")
        await asyncio.sleep(_TICK_SEC)
