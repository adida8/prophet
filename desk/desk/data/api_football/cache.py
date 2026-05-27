"""SQLite cache for api-football responses.

Three tables:

* `team_resolution` — one row per canonical ISO3 (national sides). Maps
  to api-football's numeric team_id. Rarely changes; cached forever
  unless explicitly invalidated by `resolved_at`-based TTL.
* `fixture_results` — one row per (api_football_team_id, fixture_id).
  The raw last-N fixture results for a team. Used to compute
  `form_delta` downstream.
* `form_deltas` — one row per ISO3. The derived `form_delta` value +
  sample size + when it was computed. The features-builder reads this
  table on the hot path; the fetcher rebuilds it after pulling fresh
  fixtures.

Sync stdlib `sqlite3` matches the signals cache pattern. The fetcher is
a batch job out-of-band of the verdict path — async buys nothing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS team_resolution (
    iso3                  TEXT PRIMARY KEY,
    api_football_team_id  INTEGER NOT NULL,
    resolved_at           TEXT    NOT NULL,
    source_label          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS fixture_results (
    api_football_team_id  INTEGER NOT NULL,
    fixture_id            INTEGER NOT NULL,
    played_at             TEXT    NOT NULL,
    opponent_team_id      INTEGER,
    team_goals            INTEGER,
    opponent_goals        INTEGER,
    status_short          TEXT    NOT NULL,
    PRIMARY KEY (api_football_team_id, fixture_id)
);

CREATE INDEX IF NOT EXISTS idx_fixture_results_team_played
    ON fixture_results(api_football_team_id, played_at DESC);

CREATE TABLE IF NOT EXISTS form_deltas (
    iso3         TEXT PRIMARY KEY,
    form_delta   REAL NOT NULL,
    sample_size  INTEGER NOT NULL,
    computed_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_fetches (
    endpoint     TEXT PRIMARY KEY,
    last_fetched TEXT NOT NULL,
    last_status  TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class TeamResolution:
    iso3:                 str
    api_football_team_id: int
    resolved_at:          str
    source_label:         str


@dataclass(frozen=True)
class FixtureResult:
    """One played fixture for a team. Stored from api-football's
    `/fixtures?team={team_id}&last={N}` response, filtered to status
    `FT` (Full Time) so unfinished or postponed matches don't feed
    form_delta.
    """
    api_football_team_id: int
    fixture_id:           int
    played_at:            datetime
    opponent_team_id:     int | None
    team_goals:           int | None
    opponent_goals:       int | None
    status_short:         str

    @property
    def points(self) -> int:
        """3-1-0 points scored by this team's perspective."""
        if self.team_goals is None or self.opponent_goals is None:
            return 0
        if self.team_goals > self.opponent_goals:
            return 3
        if self.team_goals == self.opponent_goals:
            return 1
        return 0


@dataclass(frozen=True)
class FormDelta:
    iso3:        str
    form_delta:  float
    sample_size: int
    computed_at: str


class APIFootballCache:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "APIFootballCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── Team resolution ───────────────────────────────────────────

    def upsert_team_resolution(
        self, iso3: str, api_football_team_id: int, *,
        source_label: str, resolved_at: datetime | None = None,
    ) -> None:
        ts = (resolved_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO team_resolution(iso3, api_football_team_id, "
            "resolved_at, source_label) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(iso3) DO UPDATE SET "
            "  api_football_team_id = excluded.api_football_team_id, "
            "  resolved_at = excluded.resolved_at, "
            "  source_label = excluded.source_label",
            (iso3.lower(), api_football_team_id, ts, source_label),
        )

    def team_id_for_iso3(self, iso3: str) -> int | None:
        row = self._conn.execute(
            "SELECT api_football_team_id FROM team_resolution WHERE iso3 = ?",
            (iso3.lower(),),
        ).fetchone()
        return int(row["api_football_team_id"]) if row else None

    def list_resolutions(self) -> list[TeamResolution]:
        rows = self._conn.execute(
            "SELECT iso3, api_football_team_id, resolved_at, source_label "
            "FROM team_resolution ORDER BY iso3"
        ).fetchall()
        return [TeamResolution(
            iso3=r["iso3"],
            api_football_team_id=int(r["api_football_team_id"]),
            resolved_at=r["resolved_at"],
            source_label=r["source_label"],
        ) for r in rows]

    # ── Fixture results ───────────────────────────────────────────

    def upsert_fixture_results(self, results: list[FixtureResult]) -> int:
        n = 0
        for r in results:
            self._conn.execute(
                "INSERT INTO fixture_results("
                "  api_football_team_id, fixture_id, played_at, "
                "  opponent_team_id, team_goals, opponent_goals, status_short"
                ") VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(api_football_team_id, fixture_id) DO UPDATE SET "
                "  played_at = excluded.played_at, "
                "  opponent_team_id = excluded.opponent_team_id, "
                "  team_goals = excluded.team_goals, "
                "  opponent_goals = excluded.opponent_goals, "
                "  status_short = excluded.status_short",
                (
                    r.api_football_team_id, r.fixture_id,
                    r.played_at.isoformat(),
                    r.opponent_team_id, r.team_goals, r.opponent_goals,
                    r.status_short,
                ),
            )
            n += 1
        return n

    def recent_fixtures(
        self, api_football_team_id: int, *, limit: int = 10,
    ) -> list[FixtureResult]:
        rows = self._conn.execute(
            "SELECT api_football_team_id, fixture_id, played_at, "
            "       opponent_team_id, team_goals, opponent_goals, status_short "
            "FROM fixture_results "
            "WHERE api_football_team_id = ? AND status_short = 'FT' "
            "ORDER BY played_at DESC LIMIT ?",
            (api_football_team_id, limit),
        ).fetchall()
        out: list[FixtureResult] = []
        for r in rows:
            out.append(FixtureResult(
                api_football_team_id=int(r["api_football_team_id"]),
                fixture_id=int(r["fixture_id"]),
                played_at=datetime.fromisoformat(r["played_at"]),
                opponent_team_id=(int(r["opponent_team_id"])
                                  if r["opponent_team_id"] is not None else None),
                team_goals=(int(r["team_goals"]) if r["team_goals"] is not None else None),
                opponent_goals=(int(r["opponent_goals"])
                                if r["opponent_goals"] is not None else None),
                status_short=r["status_short"],
            ))
        return out

    # ── form_delta ─────────────────────────────────────────────

    def upsert_form_delta(
        self, iso3: str, form_delta: float, sample_size: int,
        *, computed_at: datetime | None = None,
    ) -> None:
        ts = (computed_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO form_deltas(iso3, form_delta, sample_size, computed_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(iso3) DO UPDATE SET "
            "  form_delta = excluded.form_delta, "
            "  sample_size = excluded.sample_size, "
            "  computed_at = excluded.computed_at",
            (iso3.lower(), form_delta, sample_size, ts),
        )

    def form_delta_for_iso3(self, iso3: str) -> FormDelta | None:
        row = self._conn.execute(
            "SELECT iso3, form_delta, sample_size, computed_at "
            "FROM form_deltas WHERE iso3 = ?",
            (iso3.lower(),),
        ).fetchone()
        if not row:
            return None
        return FormDelta(
            iso3=row["iso3"],
            form_delta=float(row["form_delta"]),
            sample_size=int(row["sample_size"]),
            computed_at=row["computed_at"],
        )

    # ── fetches log (so the loop can rate-limit on its own clock) ─

    def mark_fetch(self, endpoint: str, status: str, *,
                   at: datetime | None = None) -> None:
        ts = (at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO api_fetches(endpoint, last_fetched, last_status) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "  last_fetched = excluded.last_fetched, "
            "  last_status = excluded.last_status",
            (endpoint, ts, status),
        )

    def last_fetch(self, endpoint: str) -> tuple[datetime, str] | None:
        row = self._conn.execute(
            "SELECT last_fetched, last_status FROM api_fetches WHERE endpoint = ?",
            (endpoint,),
        ).fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["last_fetched"]), row["last_status"]
