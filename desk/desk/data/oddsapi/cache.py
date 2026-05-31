"""SQLite cache for Odds-API events + per-bookmaker prices.

Two tables:

* `oddsapi_events` — one row per remote event id (Odds API's `id`),
  carrying sport_key, commence_time (kickoff_utc), home_team, away_team
  + the resolved canonical match_id (filled later by the football glue).
* `oddsapi_prices` — one row per (event_id, venue_id, side). Holds
  the raw decimal odds + last_update timestamp. Delete-then-insert
  per (event_id, venue_id) per refresh so a vanished outcome wipes
  cleanly.

Sync stdlib sqlite3 mirrors the api_football pattern. The fetcher is
a batch job out-of-band of the verdict path — async buys nothing.

Path is overridable via DESK_ODDS_API_DB_PATH so Railway can point at a
mounted volume that survives deploys.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from desk import config

Side = Literal["a", "draw", "b"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS oddsapi_events (
    event_id        TEXT PRIMARY KEY,
    sport_key       TEXT NOT NULL,
    commence_time   TEXT NOT NULL,
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    -- Filled by the football-side resolver once it maps event → FixtureRef.
    -- Empty when we've fetched the event but haven't resolved it yet
    -- (e.g. a friendly the engine doesn't track).
    resolved_match_id TEXT NOT NULL DEFAULT '',
    fetched_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oddsapi_events_commence
    ON oddsapi_events(commence_time);

CREATE TABLE IF NOT EXISTS oddsapi_prices (
    event_id        TEXT NOT NULL,
    venue_id        TEXT NOT NULL,
    side            TEXT NOT NULL,        -- "a", "draw", "b"
    decimal_odds    REAL NOT NULL,
    last_update     TEXT NOT NULL,        -- bookmaker's own last_update
    fetched_at      TEXT NOT NULL,
    PRIMARY KEY (event_id, venue_id, side)
);

CREATE INDEX IF NOT EXISTS idx_oddsapi_prices_event
    ON oddsapi_prices(event_id);

CREATE TABLE IF NOT EXISTS oddsapi_fetches (
    endpoint     TEXT PRIMARY KEY,
    last_fetched TEXT NOT NULL,
    last_status  TEXT NOT NULL,
    last_credits INTEGER
);
"""


@dataclass(frozen=True)
class EventRow:
    event_id:          str
    sport_key:         str
    commence_time:     datetime
    home_team:         str
    away_team:         str
    resolved_match_id: str
    fetched_at:        str


@dataclass(frozen=True)
class PriceRow:
    event_id:     str
    venue_id:     str
    side:         Side
    decimal_odds: float
    last_update:  str
    fetched_at:   str


def default_cache_path() -> Path:
    """Where the cache lives on disk. Honour `DESK_ODDS_API_DB_PATH` so
    Railway can point at a mounted volume; otherwise sit next to the
    other Desk sqlite caches under `desk/data/`."""
    override = os.getenv("DESK_ODDS_API_DB_PATH", "")
    if override:
        return Path(override)
    return Path(config.ROOT) / "data" / "oddsapi.db"


class OddsAPICache:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_cache_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "OddsAPICache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── Events ──────────────────────────────────────────────────────

    def upsert_event(
        self,
        *,
        event_id: str,
        sport_key: str,
        commence_time: datetime,
        home_team: str,
        away_team: str,
        resolved_match_id: str = "",
        fetched_at: datetime | None = None,
    ) -> None:
        ts = (fetched_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO oddsapi_events("
            "  event_id, sport_key, commence_time, home_team, away_team, "
            "  resolved_match_id, fetched_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(event_id) DO UPDATE SET "
            "  sport_key = excluded.sport_key, "
            "  commence_time = excluded.commence_time, "
            "  home_team = excluded.home_team, "
            "  away_team = excluded.away_team, "
            "  resolved_match_id = excluded.resolved_match_id, "
            "  fetched_at = excluded.fetched_at",
            (
                event_id, sport_key, commence_time.isoformat(),
                home_team, away_team, resolved_match_id, ts,
            ),
        )

    def event_for(self, event_id: str) -> EventRow | None:
        row = self._conn.execute(
            "SELECT event_id, sport_key, commence_time, home_team, "
            "       away_team, resolved_match_id, fetched_at "
            "FROM oddsapi_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if not row:
            return None
        return EventRow(
            event_id=row["event_id"],
            sport_key=row["sport_key"],
            commence_time=datetime.fromisoformat(row["commence_time"]),
            home_team=row["home_team"],
            away_team=row["away_team"],
            resolved_match_id=row["resolved_match_id"] or "",
            fetched_at=row["fetched_at"],
        )

    def set_event_resolution(self, event_id: str, resolved_match_id: str) -> None:
        self._conn.execute(
            "UPDATE oddsapi_events SET resolved_match_id = ? WHERE event_id = ?",
            (resolved_match_id, event_id),
        )

    def events_for_match_id(self, match_id: str) -> list[EventRow]:
        rows = self._conn.execute(
            "SELECT event_id, sport_key, commence_time, home_team, "
            "       away_team, resolved_match_id, fetched_at "
            "FROM oddsapi_events WHERE resolved_match_id = ?",
            (match_id,),
        ).fetchall()
        return [
            EventRow(
                event_id=r["event_id"],
                sport_key=r["sport_key"],
                commence_time=datetime.fromisoformat(r["commence_time"]),
                home_team=r["home_team"],
                away_team=r["away_team"],
                resolved_match_id=r["resolved_match_id"] or "",
                fetched_at=r["fetched_at"],
            )
            for r in rows
        ]

    # ── Prices ──────────────────────────────────────────────────────

    def replace_prices_for_event_venue(
        self,
        *,
        event_id: str,
        venue_id: str,
        rows: Iterable[PriceRow],
    ) -> int:
        """Delete-then-insert all rows for one (event, venue) pair.

        Empty `rows` means the venue stopped quoting this event — every
        previous row is wiped. The cache never silently keeps stale
        prices.
        """
        self._conn.execute(
            "DELETE FROM oddsapi_prices "
            "WHERE event_id = ? AND venue_id = ?",
            (event_id, venue_id),
        )
        n = 0
        for r in rows:
            self._conn.execute(
                "INSERT INTO oddsapi_prices("
                "  event_id, venue_id, side, decimal_odds, last_update, "
                "  fetched_at"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    r.event_id, r.venue_id, r.side, r.decimal_odds,
                    r.last_update, r.fetched_at,
                ),
            )
            n += 1
        return n

    def prices_for_event(self, event_id: str) -> list[PriceRow]:
        rows = self._conn.execute(
            "SELECT event_id, venue_id, side, decimal_odds, last_update, "
            "       fetched_at "
            "FROM oddsapi_prices WHERE event_id = ? "
            "ORDER BY venue_id, side",
            (event_id,),
        ).fetchall()
        return [
            PriceRow(
                event_id=r["event_id"],
                venue_id=r["venue_id"],
                side=r["side"],   # type: ignore[arg-type]
                decimal_odds=float(r["decimal_odds"]),
                last_update=r["last_update"],
                fetched_at=r["fetched_at"],
            )
            for r in rows
        ]

    # ── Fetches log ─────────────────────────────────────────────────

    def mark_fetch(
        self,
        endpoint: str,
        status: str,
        *,
        credits: int | None = None,
        at: datetime | None = None,
    ) -> None:
        ts = (at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO oddsapi_fetches(endpoint, last_fetched, last_status, last_credits) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "  last_fetched = excluded.last_fetched, "
            "  last_status = excluded.last_status, "
            "  last_credits = excluded.last_credits",
            (endpoint, ts, status, credits),
        )

    def last_fetch(self, endpoint: str) -> tuple[datetime, str, int | None] | None:
        row = self._conn.execute(
            "SELECT last_fetched, last_status, last_credits "
            "FROM oddsapi_fetches WHERE endpoint = ?",
            (endpoint,),
        ).fetchone()
        if not row:
            return None
        return (
            datetime.fromisoformat(row["last_fetched"]),
            row["last_status"],
            (int(row["last_credits"]) if row["last_credits"] is not None else None),
        )
