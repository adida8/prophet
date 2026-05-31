"""Background refresh loop.

Refreshes every wallet viewed in the last 24h. Cheap to run — Polymarket's
data API is public and the refresh is idempotent.

Disabled by default 2026-05-31 via the schedules admin (loop_registry's
`ledger_refresh.default_enabled = False`). Toggle the loop on at
`/desk/ops/schedules` if you ever need it back; the tick honours the
flag on its next iteration without a restart.

Cadence is configurable via `LEDGER_REFRESH_INTERVAL_SEC` (default 1800s
= 30 min, doubled from the previous hardcoded 900s since this is now
opt-in).
"""

from __future__ import annotations

import asyncio
import logging
import os

from ledger import db, service
from loop_registry import is_enabled

log = logging.getLogger("ledger.refresh_loop")

LOOP_ID              = "ledger_refresh"
REFRESH_INTERVAL_SEC = int(os.getenv("LEDGER_REFRESH_INTERVAL_SEC", "1800"))
IDLE_POLL_SEC        = 60
RECENT_VIEW_HOURS    = 24


async def run_refresh_loop() -> None:
    await db.init_db()
    log.info("ledger refresh loop online — every %ds (honours schedules.json toggle)",
             REFRESH_INTERVAL_SEC)
    while True:
        if not is_enabled(LOOP_ID):
            await asyncio.sleep(IDLE_POLL_SEC)
            continue
        try:
            wallets = await db.list_recently_viewed_wallets(within_hours=RECENT_VIEW_HOURS)
            if wallets:
                log.info("refreshing %d wallet(s)", len(wallets))
            for addr in wallets:
                try:
                    await service.refresh_wallet(addr)
                except Exception as e:
                    log.warning("refresh failed for %s: %s", addr, e)
        except Exception:
            log.exception("ledger refresh loop tick failed")
        await asyncio.sleep(REFRESH_INTERVAL_SEC)
