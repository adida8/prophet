"""SQLite cache for fetched `SourceItem`s.

Why sync stdlib `sqlite3` (not aiosqlite): the fetcher is a batch job
that runs out-of-band of any request — async buys us nothing.

Schema:
  * `source_items` — one row per (source_id, canonical_url). Re-fetching
    the same canonical_url updates in place; the `content_hash` column
    is how we tell a true edit from a re-fetch of an identical article.
  * `source_fetches` — last-fetched-at + status per source, used by the
    fetcher to enforce a polite-rate gate.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Literal

from desk.signals.models import Signal, SourceItem

WriteResult = Literal["new", "changed", "unchanged"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_items (
    source_id     TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    published_at  TEXT,
    fetched_at    TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    PRIMARY KEY (source_id, canonical_url)
);

CREATE INDEX IF NOT EXISTS idx_source_items_source
    ON source_items(source_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS source_fetches (
    source_id       TEXT PRIMARY KEY,
    last_fetched_at TEXT NOT NULL,
    last_status     TEXT NOT NULL
);

-- One row per (item, extractor). content_hash is the item's hash at
-- extraction time; if the item gets re-fetched and its body changes,
-- the runner sees the mismatch and re-extracts.
CREATE TABLE IF NOT EXISTS signal_extractions (
    source_id     TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    extractor_id  TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    extracted_at  TEXT NOT NULL,
    signals_json  TEXT NOT NULL,
    PRIMARY KEY (source_id, canonical_url, extractor_id)
);

CREATE INDEX IF NOT EXISTS idx_signal_extractions_source
    ON signal_extractions(source_id);
"""


class SignalsCache:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SignalsCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── items ──────────────────────────────────────────────────────────

    def upsert_item(self, item: SourceItem) -> WriteResult:
        row = self._conn.execute(
            "SELECT content_hash FROM source_items "
            "WHERE source_id = ? AND canonical_url = ?",
            (item.source_id, item.canonical_url),
        ).fetchone()

        if row is None:
            self._conn.execute(
                "INSERT INTO source_items "
                "(source_id, canonical_url, url, title, body, "
                " published_at, fetched_at, content_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.source_id, item.canonical_url, item.url, item.title,
                    item.body, _iso(item.published_at), _iso(item.fetched_at),
                    item.content_hash,
                ),
            )
            return "new"

        if row["content_hash"] == item.content_hash:
            return "unchanged"

        self._conn.execute(
            "UPDATE source_items SET "
            "url = ?, title = ?, body = ?, published_at = ?, "
            "fetched_at = ?, content_hash = ? "
            "WHERE source_id = ? AND canonical_url = ?",
            (
                item.url, item.title, item.body, _iso(item.published_at),
                _iso(item.fetched_at), item.content_hash,
                item.source_id, item.canonical_url,
            ),
        )
        return "changed"

    def upsert_many(self, items: Iterable[SourceItem]) -> dict[WriteResult, int]:
        counts: dict[WriteResult, int] = {"new": 0, "changed": 0, "unchanged": 0}
        for item in items:
            counts[self.upsert_item(item)] += 1
        return counts

    def list_items(self, source_id: str | None = None) -> list[SourceItem]:
        sql = "SELECT * FROM source_items"
        params: tuple = ()
        if source_id is not None:
            sql += " WHERE source_id = ?"
            params = (source_id,)
        sql += " ORDER BY fetched_at DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_item(r) for r in rows]

    def get_item(self, source_id: str, canonical_url: str) -> SourceItem | None:
        row = self._conn.execute(
            "SELECT * FROM source_items WHERE source_id = ? AND canonical_url = ?",
            (source_id, canonical_url),
        ).fetchone()
        return _row_to_item(row) if row else None

    # ── per-source fetch metadata ──────────────────────────────────────

    def mark_fetched(self, source_id: str, at: datetime, status: str) -> None:
        self._conn.execute(
            "INSERT INTO source_fetches (source_id, last_fetched_at, last_status) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(source_id) DO UPDATE SET "
            "  last_fetched_at = excluded.last_fetched_at, "
            "  last_status     = excluded.last_status",
            (source_id, at.isoformat(), status),
        )

    def last_fetched(self, source_id: str) -> datetime | None:
        row = self._conn.execute(
            "SELECT last_fetched_at FROM source_fetches WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if row is None:
            return None
        return datetime.fromisoformat(row["last_fetched_at"])

    def last_status(self, source_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT last_status FROM source_fetches WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        return row["last_status"] if row else None


    # ── signal extractions ─────────────────────────────────────────────

    def cached_signals(
        self, *, source_id: str, canonical_url: str,
        content_hash: str, extractor_id: str,
    ) -> list[Signal] | None:
        """Return cached signals only if the cached `content_hash` matches
        the caller's. Mismatch ⇒ item changed since extraction ⇒ caller
        must re-extract."""
        row = self._conn.execute(
            "SELECT content_hash, signals_json FROM signal_extractions "
            "WHERE source_id = ? AND canonical_url = ? AND extractor_id = ?",
            (source_id, canonical_url, extractor_id),
        ).fetchone()
        if row is None or row["content_hash"] != content_hash:
            return None
        return [Signal.model_validate(s) for s in json.loads(row["signals_json"])]

    def cache_signals(
        self, *, source_id: str, canonical_url: str, content_hash: str,
        extractor_id: str, signals: Iterable[Signal], extracted_at: datetime,
    ) -> None:
        payload = json.dumps([s.model_dump(mode="json") for s in signals])
        self._conn.execute(
            "INSERT INTO signal_extractions "
            "(source_id, canonical_url, extractor_id, content_hash, "
            " extracted_at, signals_json) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(source_id, canonical_url, extractor_id) DO UPDATE SET "
            "  content_hash = excluded.content_hash, "
            "  extracted_at = excluded.extracted_at, "
            "  signals_json = excluded.signals_json",
            (source_id, canonical_url, extractor_id, content_hash,
             extracted_at.isoformat(), payload),
        )

    def list_signals(self, *, source_id: str | None = None) -> list[Signal]:
        sql = "SELECT signals_json FROM signal_extractions"
        params: tuple = ()
        if source_id is not None:
            sql += " WHERE source_id = ?"
            params = (source_id,)
        rows = self._conn.execute(sql, params).fetchall()
        out: list[Signal] = []
        for row in rows:
            for s in json.loads(row["signals_json"]):
                out.append(Signal.model_validate(s))
        return out


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _row_to_item(row) -> SourceItem:
    published = row["published_at"]
    return SourceItem(
        source_id=row["source_id"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        title=row["title"],
        body=row["body"],
        published_at=datetime.fromisoformat(published) if published else None,
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        content_hash=row["content_hash"],
    )
