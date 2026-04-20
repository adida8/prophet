"""
Track biggest market price movements using SQLite price snapshots.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.data_store import DataStore
from core.market_normalizer import NormalizedMarket

log = logging.getLogger("prophet.movers")


async def snapshot_prices(
    store: DataStore,
    markets: list[NormalizedMarket],
) -> None:
    """Persist current prices for movers calculation later."""
    await store.save_snapshots(markets)
    log.debug("Saved %d price snapshots", len(markets))


async def get_movers(
    store: DataStore,
    hours: int = 24,
    limit: int = 10,
) -> list[dict]:
    """Return top movers from the SQLite history."""
    return await store.get_movers(hours=hours, limit=limit)


def get_movers_from_memory(
    current: list[NormalizedMarket],
    previous: list[NormalizedMarket],
    limit: int = 10,
) -> list[dict]:
    """
    Calculate movers from two in-memory snapshots (used when SQLite
    history is too thin, e.g. just after startup).
    """
    prev_map = {m.id: m for m in previous}
    results = []

    for curr in current:
        prev = prev_map.get(curr.id)
        if prev is None:
            continue
        change = curr.yes_price - prev.yes_price
        if change == 0:
            continue
        change_pct = (change / prev.yes_price * 100) if prev.yes_price else 0.0
        results.append({
            "market_id":     curr.id,
            "platform":      curr.platform,
            "title":         curr.title,
            "category":      curr.category,
            "current_price": curr.yes_price,
            "old_price":     prev.yes_price,
            "change_abs":    round(change, 4),
            "change_pct":    round(change_pct, 1),
            "volume_24h":    curr.volume_24h,
        })

    results.sort(key=lambda r: abs(r["change_abs"]), reverse=True)
    return results[:limit]
