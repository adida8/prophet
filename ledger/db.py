"""SQLite store for the Ledger.

We persist every snapshot — this is the source of truth for the cumulative
P&L chart and future analytics. Closed positions are derived by diffing each
incoming refresh against what we last saw on disk.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

import config

DB_PATH: Path = config.DATA_DIR / "ledger.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS wallets (
    address           TEXT PRIMARY KEY,
    first_seen_at     TEXT NOT NULL,
    last_refreshed_at TEXT,
    last_viewed_at    TEXT,
    label             TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address      TEXT NOT NULL,
    snapshot_at         TEXT NOT NULL,
    total_value_usd     REAL NOT NULL,
    realized_pnl_usd    REAL NOT NULL,
    unrealized_pnl_usd  REAL NOT NULL,
    raw_positions_json  TEXT NOT NULL,
    raw_activity_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_wallet_time
    ON snapshots(wallet_address, snapshot_at);

CREATE TABLE IF NOT EXISTS positions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address      TEXT NOT NULL,
    condition_id        TEXT NOT NULL,
    asset               TEXT NOT NULL,
    market_question     TEXT NOT NULL,
    event_slug          TEXT,
    icon_url            TEXT,
    outcome             TEXT NOT NULL,
    shares              REAL NOT NULL,
    avg_entry_price     REAL NOT NULL,
    current_price       REAL NOT NULL,
    initial_value_usd   REAL NOT NULL,
    value_usd           REAL NOT NULL,
    unrealized_pnl_usd  REAL NOT NULL,
    realized_pnl_usd    REAL NOT NULL,
    end_date            TEXT,
    opened_at           TEXT NOT NULL,
    closed_at           TEXT,
    last_seen_at        TEXT NOT NULL,
    UNIQUE(wallet_address, asset)
);
CREATE INDEX IF NOT EXISTS idx_positions_wallet
    ON positions(wallet_address, closed_at);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    """Create tables if they don't exist. Safe to call repeatedly."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def upsert_wallet(address: str, *, viewed: bool = False) -> None:
    address = address.lower()
    now = _utc_now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO wallets (address, first_seen_at, last_viewed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                last_viewed_at = CASE WHEN ? THEN ? ELSE last_viewed_at END
            """,
            (address, now, now if viewed else None, viewed, now),
        )
        await db.commit()


async def mark_refreshed(address: str) -> None:
    address = address.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE wallets SET last_refreshed_at = ? WHERE address = ?",
            (_utc_now_iso(), address),
        )
        await db.commit()


async def get_wallet(address: str) -> dict[str, Any] | None:
    address = address.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM wallets WHERE address = ?", (address,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_recently_viewed_wallets(within_hours: int = 24) -> list[str]:
    cutoff = datetime.now(timezone.utc).timestamp() - within_hours * 3600
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT address FROM wallets WHERE last_viewed_at >= ?",
            (cutoff_iso,),
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def insert_snapshot(
    *,
    address: str,
    total_value_usd: float,
    realized_pnl_usd: float,
    unrealized_pnl_usd: float,
    raw_positions: list[dict[str, Any]],
    raw_activity: list[dict[str, Any]],
) -> str:
    address = address.lower()
    snapshot_at = _utc_now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO snapshots
                (wallet_address, snapshot_at, total_value_usd,
                 realized_pnl_usd, unrealized_pnl_usd,
                 raw_positions_json, raw_activity_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                address,
                snapshot_at,
                total_value_usd,
                realized_pnl_usd,
                unrealized_pnl_usd,
                json.dumps(raw_positions),
                json.dumps(raw_activity),
            ),
        )
        await db.commit()
    return snapshot_at


async def get_snapshot_history(address: str) -> list[dict[str, Any]]:
    address = address.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT snapshot_at, total_value_usd, realized_pnl_usd, unrealized_pnl_usd
            FROM snapshots
            WHERE wallet_address = ?
            ORDER BY snapshot_at ASC
            """,
            (address,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_latest_snapshot(address: str) -> dict[str, Any] | None:
    address = address.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM snapshots
            WHERE wallet_address = ?
            ORDER BY snapshot_at DESC
            LIMIT 1
            """,
            (address,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_positions(
    *,
    address: str,
    positions: Iterable[dict[str, Any]],
    seen_at: str,
) -> None:
    """Insert or update each open position. Does NOT close missing ones —
    that's done in close_missing_positions().
    """
    address = address.lower()
    rows = []
    for p in positions:
        rows.append(
            (
                address,
                p["condition_id"],
                p["asset"],
                p["market_question"],
                p.get("event_slug"),
                p.get("icon_url"),
                p["outcome"],
                p["shares"],
                p["avg_entry_price"],
                p["current_price"],
                p["initial_value_usd"],
                p["value_usd"],
                p["unrealized_pnl_usd"],
                p["realized_pnl_usd"],
                p.get("end_date"),
                p.get("opened_at") or seen_at,
                seen_at,
            )
        )
    if not rows:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            INSERT INTO positions (
                wallet_address, condition_id, asset, market_question,
                event_slug, icon_url, outcome, shares, avg_entry_price,
                current_price, initial_value_usd, value_usd,
                unrealized_pnl_usd, realized_pnl_usd, end_date,
                opened_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet_address, asset) DO UPDATE SET
                shares             = excluded.shares,
                avg_entry_price    = excluded.avg_entry_price,
                current_price      = excluded.current_price,
                initial_value_usd  = excluded.initial_value_usd,
                value_usd          = excluded.value_usd,
                unrealized_pnl_usd = excluded.unrealized_pnl_usd,
                realized_pnl_usd   = excluded.realized_pnl_usd,
                end_date           = excluded.end_date,
                last_seen_at       = excluded.last_seen_at,
                closed_at          = NULL
            """,
            rows,
        )
        await db.commit()


async def close_missing_positions(
    *, address: str, current_assets: set[str], closed_at: str
) -> None:
    """Mark every open position not in current_assets as closed."""
    address = address.lower()
    async with aiosqlite.connect(DB_PATH) as db:
        if current_assets:
            placeholders = ",".join("?" * len(current_assets))
            await db.execute(
                f"""
                UPDATE positions
                SET closed_at = ?
                WHERE wallet_address = ?
                  AND closed_at IS NULL
                  AND asset NOT IN ({placeholders})
                """,
                (closed_at, address, *current_assets),
            )
        else:
            await db.execute(
                """
                UPDATE positions
                SET closed_at = ?
                WHERE wallet_address = ? AND closed_at IS NULL
                """,
                (closed_at, address),
            )
        await db.commit()


async def get_positions(address: str, *, only_open: bool = False) -> list[dict[str, Any]]:
    address = address.lower()
    sql = "SELECT * FROM positions WHERE wallet_address = ?"
    if only_open:
        sql += " AND closed_at IS NULL"
    sql += " ORDER BY value_usd DESC"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, (address,)) as cur:
            return [dict(r) for r in await cur.fetchall()]
