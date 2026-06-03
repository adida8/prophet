"""SQLite-backed durable outbox for the MTA push wire.

Copied verbatim from the live Desk (`desk/desk/distribute/outbox.py`).
Sync stdlib sqlite3: the worker is a batch process called once per tick;
DB ops are sub-millisecond and single-row.

Invariant: at most one PENDING row per id (match_id or outright_id). A
new enqueue while a row is still pending OVERWRITES it — resending the
older body is wasted work. Dead rows accumulate as an audit trail.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = 1

Status = Literal["pending", "dead"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS push_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    body            BLOB NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at INTEGER NOT NULL,
    last_error      TEXT,
    created_at      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_push_queue_due
    ON push_queue (status, next_attempt_at);

CREATE INDEX IF NOT EXISTS idx_push_queue_match_pending
    ON push_queue (match_id) WHERE status = 'pending';
"""


@dataclass(frozen=True)
class OutboxRow:
    id:              int
    match_id:        str
    updated_at:      str
    body:            bytes
    attempts:        int
    next_attempt_at: int
    last_error:      str | None
    created_at:      int
    status:          Status


class Outbox:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cur = self._conn.execute("PRAGMA user_version").fetchone()
        existing = cur[0] if cur else 0
        if existing == SCHEMA_VERSION:
            return
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Outbox":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── enqueue ────────────────────────────────────────────────────────

    def enqueue(self, *, match_id: str, updated_at: str, body: bytes,
                now: int | None = None) -> int:
        """Insert or replace the pending row for `match_id`.

        Collapse rule: one pending row per id. Returns the row id.
        """
        now = now if now is not None else int(time.time())
        existing = self._conn.execute(
            "SELECT id FROM push_queue WHERE match_id = ? AND status = 'pending'",
            (match_id,),
        ).fetchone()
        if existing is not None:
            self._conn.execute(
                "UPDATE push_queue SET "
                "  updated_at = ?, body = ?, attempts = 0, "
                "  next_attempt_at = ?, last_error = NULL "
                "WHERE id = ?",
                (updated_at, body, now, existing["id"]),
            )
            return int(existing["id"])
        cur = self._conn.execute(
            "INSERT INTO push_queue "
            "(match_id, updated_at, body, attempts, next_attempt_at, created_at, status) "
            "VALUES (?, ?, ?, 0, ?, ?, 'pending')",
            (match_id, updated_at, body, now, now),
        )
        return int(cur.lastrowid)

    # ── claim due rows ─────────────────────────────────────────────────

    def claim_due(self, *, now: int, limit: int) -> list[OutboxRow]:
        """Up to `limit` pending rows whose next_attempt_at <= now, oldest first."""
        rows = self._conn.execute(
            "SELECT * FROM push_queue "
            "WHERE status = 'pending' AND next_attempt_at <= ? "
            "ORDER BY next_attempt_at ASC, id ASC "
            "LIMIT ?",
            (now, limit),
        ).fetchall()
        return [_row_to_obj(r) for r in rows]

    # ── outcome ───────────────────────────────────────────────────────

    def mark_sent(self, row_id: int) -> None:
        self._conn.execute("DELETE FROM push_queue WHERE id = ?", (row_id,))

    def mark_retry(self, row_id: int, *, next_attempt_at: int,
                   last_error: str) -> None:
        self._conn.execute(
            "UPDATE push_queue SET "
            "  attempts = attempts + 1, "
            "  next_attempt_at = ?, "
            "  last_error = ? "
            "WHERE id = ?",
            (next_attempt_at, last_error, row_id),
        )

    def mark_dead(self, row_id: int, *, reason: str) -> None:
        self._conn.execute(
            "UPDATE push_queue SET "
            "  status = 'dead', "
            "  last_error = ?, "
            "  attempts = attempts + 1 "
            "WHERE id = ?",
            (reason, row_id),
        )

    # ── read-side helpers (ops / tests) ────────────────────────────────

    def get(self, row_id: int) -> OutboxRow | None:
        row = self._conn.execute(
            "SELECT * FROM push_queue WHERE id = ?",
            (row_id,),
        ).fetchone()
        return _row_to_obj(row) if row else None

    def pending_count(self) -> int:
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM push_queue WHERE status = 'pending'"
        ).fetchone()[0])

    def dead_count(self) -> int:
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM push_queue WHERE status = 'dead'"
        ).fetchone()[0])

    def list_dead(self, *, limit: int = 50) -> list[OutboxRow]:
        rows = self._conn.execute(
            "SELECT * FROM push_queue WHERE status = 'dead' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_obj(r) for r in rows]

    def retry_dead_letters(
        self,
        *,
        match_ids: list[str] | None = None,
        now: int | None = None,
    ) -> int:
        """Move dead rows back to pending so the next drain sweep picks them up."""
        ts_now = now if now is not None else int(time.time())
        if match_ids is not None:
            if not match_ids:
                return 0
            placeholders = ",".join("?" * len(match_ids))
            cur = self._conn.execute(
                f"UPDATE push_queue SET "
                "  status = 'pending', "
                "  attempts = 0, "
                "  next_attempt_at = ? "
                f"WHERE status = 'dead' AND match_id IN ({placeholders})",
                (ts_now, *match_ids),
            )
        else:
            cur = self._conn.execute(
                "UPDATE push_queue SET "
                "  status = 'pending', "
                "  attempts = 0, "
                "  next_attempt_at = ? "
                "WHERE status = 'dead'",
                (ts_now,),
            )
        return cur.rowcount or 0


def _row_to_obj(row: sqlite3.Row) -> OutboxRow:
    return OutboxRow(
        id              = int(row["id"]),
        match_id        = row["match_id"],
        updated_at      = row["updated_at"],
        body            = row["body"],
        attempts        = int(row["attempts"]),
        next_attempt_at = int(row["next_attempt_at"]),
        last_error      = row["last_error"],
        created_at      = int(row["created_at"]),
        status          = row["status"],
    )
