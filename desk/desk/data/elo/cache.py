"""SQLite cache for live Elo ingest (Phase 1b).

Two tables, one for each kind of entity:
  * `national_elo` — keyed on iso3, one row per country
  * `club_elo`     — keyed on canonical club_id (`{league}-{short}`)

Both carry Citation provenance fields (source_id, source_url,
fetched_at, parser_version) per data-layer spec §3.5.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS national_elo (
    iso3              TEXT PRIMARY KEY,
    elo               REAL NOT NULL,
    fetched_at        TEXT NOT NULL,
    source_id         TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    parser_version    TEXT NOT NULL DEFAULT 'v1'
);

CREATE TABLE IF NOT EXISTS club_elo (
    club_id           TEXT PRIMARY KEY,
    elo               REAL NOT NULL,
    fetched_at        TEXT NOT NULL,
    source_id         TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    parser_version    TEXT NOT NULL DEFAULT 'v1'
);

CREATE TABLE IF NOT EXISTS elo_fetches (
    source_id    TEXT PRIMARY KEY,
    last_fetched TEXT NOT NULL,
    last_status  TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class EloRow:
    """One cached Elo value with full Citation provenance."""
    key:               str           # iso3 or club_id
    elo:               float
    fetched_at:        str
    source_id:         str
    source_url:        str
    parser_version:    str = "v1"


class EloCache:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EloCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── national ──────────────────────────────────────────────────

    def upsert_national(
        self, iso3: str, elo: float,
        *, source_id: str, source_url: str,
        fetched_at: datetime | None = None,
        parser_version: str = "v1",
    ) -> None:
        ts = (fetched_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO national_elo("
            "  iso3, elo, fetched_at, source_id, source_url, parser_version"
            ") VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(iso3) DO UPDATE SET "
            "  elo = excluded.elo, "
            "  fetched_at = excluded.fetched_at, "
            "  source_id = excluded.source_id, "
            "  source_url = excluded.source_url, "
            "  parser_version = excluded.parser_version",
            (iso3.lower(), elo, ts, source_id, source_url, parser_version),
        )

    def get_national(self, iso3: str) -> EloRow | None:
        row = self._conn.execute(
            "SELECT iso3, elo, fetched_at, source_id, source_url, parser_version "
            "FROM national_elo WHERE iso3 = ?",
            (iso3.lower(),),
        ).fetchone()
        if not row:
            return None
        return EloRow(
            key=row["iso3"], elo=float(row["elo"]),
            fetched_at=row["fetched_at"], source_id=row["source_id"],
            source_url=row["source_url"], parser_version=row["parser_version"],
        )

    def list_nationals(self) -> list[EloRow]:
        rows = self._conn.execute(
            "SELECT iso3, elo, fetched_at, source_id, source_url, parser_version "
            "FROM national_elo ORDER BY iso3"
        ).fetchall()
        return [EloRow(
            key=r["iso3"], elo=float(r["elo"]),
            fetched_at=r["fetched_at"], source_id=r["source_id"],
            source_url=r["source_url"], parser_version=r["parser_version"],
        ) for r in rows]

    # ── club ──────────────────────────────────────────────────────

    def upsert_club(
        self, club_id: str, elo: float,
        *, source_id: str, source_url: str,
        fetched_at: datetime | None = None,
        parser_version: str = "v1",
    ) -> None:
        ts = (fetched_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO club_elo("
            "  club_id, elo, fetched_at, source_id, source_url, parser_version"
            ") VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(club_id) DO UPDATE SET "
            "  elo = excluded.elo, "
            "  fetched_at = excluded.fetched_at, "
            "  source_id = excluded.source_id, "
            "  source_url = excluded.source_url, "
            "  parser_version = excluded.parser_version",
            (club_id.lower(), elo, ts, source_id, source_url, parser_version),
        )

    def get_club(self, club_id: str) -> EloRow | None:
        row = self._conn.execute(
            "SELECT club_id, elo, fetched_at, source_id, source_url, parser_version "
            "FROM club_elo WHERE club_id = ?",
            (club_id.lower(),),
        ).fetchone()
        if not row:
            return None
        return EloRow(
            key=row["club_id"], elo=float(row["elo"]),
            fetched_at=row["fetched_at"], source_id=row["source_id"],
            source_url=row["source_url"], parser_version=row["parser_version"],
        )

    def list_clubs(self) -> list[EloRow]:
        rows = self._conn.execute(
            "SELECT club_id, elo, fetched_at, source_id, source_url, parser_version "
            "FROM club_elo ORDER BY club_id"
        ).fetchall()
        return [EloRow(
            key=r["club_id"], elo=float(r["elo"]),
            fetched_at=r["fetched_at"], source_id=r["source_id"],
            source_url=r["source_url"], parser_version=r["parser_version"],
        ) for r in rows]

    # ── fetches log ───────────────────────────────────────────────

    def mark_fetch(self, source_id: str, status: str,
                   *, at: datetime | None = None) -> None:
        ts = (at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO elo_fetches(source_id, last_fetched, last_status) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(source_id) DO UPDATE SET "
            "  last_fetched = excluded.last_fetched, "
            "  last_status = excluded.last_status",
            (source_id, ts, status),
        )

    def last_fetch(self, source_id: str) -> tuple[datetime, str] | None:
        row = self._conn.execute(
            "SELECT last_fetched, last_status FROM elo_fetches WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["last_fetched"]), row["last_status"]
