"""
SQLite store for price history snapshots (used by movers_tracker).
All market data displayed in real-time is held in memory; only history
that requires time-window comparison is persisted here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

import config

log = logging.getLogger("prophet.datastore")


class DataStore:
    def __init__(self, db_path: Optional[Path] = None):
        self._path = str(db_path or config.DB_PATH)

    async def init(self) -> None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id    TEXT    NOT NULL,
                    platform     TEXT    NOT NULL,
                    title        TEXT,
                    category     TEXT,
                    yes_price    REAL    NOT NULL,
                    volume_24h   REAL,
                    captured_at  TEXT    NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snap_market_time "
                "ON price_snapshots(market_id, captured_at)"
            )
            await db.commit()
        log.info("DataStore initialised at %s", self._path)

    async def save_snapshots(self, markets: list) -> None:
        """Persist a price snapshot for each NormalizedMarket."""
        if not markets:
            return
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._path) as db:
            await db.executemany(
                "INSERT INTO price_snapshots "
                "(market_id, platform, title, category, yes_price, volume_24h, captured_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [
                    (m.id, m.platform, m.title, m.category,
                     m.yes_price, m.volume_24h, now)
                    for m in markets
                ],
            )
            await db.commit()

    async def get_movers(self, hours: int = 24, limit: int = 10) -> list[dict]:
        """
        Return markets with the largest absolute YES-price change over `hours`.
        Compares the latest snapshot against the oldest snapshot in the window.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query = """
            WITH ranked AS (
                SELECT market_id, platform, title, category, yes_price, volume_24h, captured_at,
                       ROW_NUMBER() OVER (PARTITION BY market_id ORDER BY captured_at DESC) AS rn_latest,
                       ROW_NUMBER() OVER (PARTITION BY market_id ORDER BY captured_at ASC)  AS rn_oldest
                FROM price_snapshots
                WHERE captured_at >= ?
            ),
            latest AS (SELECT * FROM ranked WHERE rn_latest = 1),
            oldest AS (SELECT market_id, yes_price AS old_price FROM ranked WHERE rn_oldest = 1)
            SELECT l.market_id, l.platform, l.title, l.category,
                   l.yes_price AS current_price,
                   o.old_price,
                   l.yes_price - o.old_price AS change_abs,
                   l.volume_24h
            FROM latest l
            JOIN oldest o ON l.market_id = o.market_id
            ORDER BY ABS(l.yes_price - o.old_price) DESC
            LIMIT ?
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                async with db.execute(query, (cutoff, limit)) as cur:
                    rows = await cur.fetchall()
            return [
                {
                    "market_id": r[0],
                    "platform":  r[1],
                    "title":     r[2],
                    "category":  r[3],
                    "current_price": round(r[4], 4),
                    "old_price":     round(r[5], 4),
                    "change_abs":    round(r[6], 4),
                    "change_pct":    round(r[6] / r[5] * 100, 1) if r[5] else 0.0,
                    "volume_24h":    r[7] or 0.0,
                }
                for r in rows
            ]
        except Exception as e:
            log.error("get_movers failed: %s", e)
            return []

    async def cleanup_old(self, keep_days: int = 7) -> None:
        """Delete snapshots older than keep_days to bound DB growth."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
        async with aiosqlite.connect(self._path) as db:
            await db.execute("DELETE FROM price_snapshots WHERE captured_at < ?", (cutoff,))
            await db.commit()
