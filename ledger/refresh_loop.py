"""Background refresh loop.

Every 15 minutes, refresh every wallet that's been viewed in the last 24h.
Cheap to run — Polymarket's data API is public and the refresh is idempotent.
"""

from __future__ import annotations

import asyncio
import logging

from ledger import db, service

log = logging.getLogger("ledger.refresh_loop")

REFRESH_INTERVAL_SEC = 15 * 60
RECENT_VIEW_HOURS    = 24


async def run_refresh_loop() -> None:
    await db.init_db()
    log.info("ledger refresh loop online — every %ds", REFRESH_INTERVAL_SEC)
    while True:
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
