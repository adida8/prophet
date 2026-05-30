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
from datetime import datetime, timedelta, timezone
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
    iso3              TEXT PRIMARY KEY,
    form_delta        REAL NOT NULL,
    sample_size       INTEGER NOT NULL,
    computed_at       TEXT NOT NULL,
    -- Lineage / Citation per data-layer spec §3.5: every derived
    -- feature carries the source(s) + transform it was computed from.
    -- For form_delta: source is api-football's /fixtures endpoint for
    -- this team_id; transform is `compute_form_delta`.
    source_id         TEXT NOT NULL DEFAULT 'api_football',
    source_endpoint   TEXT NOT NULL DEFAULT '',
    source_fetched_at TEXT NOT NULL DEFAULT '',
    transform         TEXT NOT NULL DEFAULT 'compute_form_delta'
);

CREATE TABLE IF NOT EXISTS api_fetches (
    endpoint     TEXT PRIMARY KEY,
    last_fetched TEXT NOT NULL,
    last_status  TEXT NOT NULL
);

-- Phase B.3 injuries — one row per (team, player). Delete-then-insert
-- per team per fetch so an absent player on refresh = recovered.
CREATE TABLE IF NOT EXISTS injuries (
    api_football_team_id  INTEGER NOT NULL,
    player_id             INTEGER NOT NULL,
    player_name           TEXT    NOT NULL,
    type                  TEXT    NOT NULL,
    reason                TEXT    NOT NULL,
    position              TEXT,
    fetched_at            TEXT    NOT NULL,
    PRIMARY KEY (api_football_team_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_injuries_team
    ON injuries(api_football_team_id);

-- Derived per-team total Elo penalty for the hot path.
CREATE TABLE IF NOT EXISTS injury_penalties (
    iso3            TEXT PRIMARY KEY,
    elo_penalty     REAL NOT NULL,
    n_players       INTEGER NOT NULL,
    computed_at     TEXT NOT NULL,
    source_endpoint TEXT NOT NULL DEFAULT '',
    transform       TEXT NOT NULL DEFAULT 'compute_injury_penalty'
);

-- Slice B / N3 lineups — one row per (fixture_id, api_football_team_id).
-- Holds the confirmed (or pre-confirmed) starting XI + formation + coach
-- + 'state' marker that distinguishes a fully announced XI from an
-- expected one. Match-id resolution comes from `fixture_resolution`
-- below; lineups land ~1h pre-kickoff, so the T-90m loop is the main
-- writer once it ships.
CREATE TABLE IF NOT EXISTS lineups (
    fixture_id            INTEGER NOT NULL,
    api_football_team_id  INTEGER NOT NULL,
    state                 TEXT    NOT NULL,   -- "confirmed" / "predicted"
    formation             TEXT,                -- "4-3-3" / "3-5-2" / etc.
    coach_name            TEXT,
    starters              TEXT    NOT NULL,   -- JSON array of starter names
    substitutes           TEXT    NOT NULL,   -- JSON array of sub names
    fetched_at            TEXT    NOT NULL,
    announced_at          TEXT,                -- ISO-8601 when api-football flagged the row
    PRIMARY KEY (fixture_id, api_football_team_id)
);

CREATE INDEX IF NOT EXISTS idx_lineups_team
    ON lineups(api_football_team_id);

-- One row per (home_team_id, away_team_id, kickoff_date). Maps the
-- engine's FixtureRef (canonical match_id) to the api-football fixture_id
-- needed by the /fixtures/lineups endpoint. Populated by `resolve_fixture_id`
-- on first lookup; reused by every subsequent fetch.
CREATE TABLE IF NOT EXISTS fixture_resolution (
    match_id              TEXT PRIMARY KEY,
    api_football_fixture_id INTEGER NOT NULL,
    home_team_id          INTEGER NOT NULL,
    away_team_id          INTEGER NOT NULL,
    kickoff_utc           TEXT    NOT NULL,
    resolved_at           TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fixture_resolution_kickoff
    ON fixture_resolution(kickoff_utc);
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
class LineupRow:
    """One team's lineup for a single fixture.

    `state` distinguishes 'confirmed' (api-football marks the row as
    the official XI announced pre-kickoff) from 'predicted' (any
    earlier read). The state is computed by the fetcher from the
    response shape — see lineups.py.
    """
    fixture_id:           int
    api_football_team_id: int
    state:                str        # "confirmed" / "predicted"
    formation:            str | None
    coach_name:           str | None
    starters:             tuple[str, ...]   # 11 names in lineup order
    substitutes:          tuple[str, ...]
    fetched_at:           str
    announced_at:         str | None = None


@dataclass(frozen=True)
class FixtureResolution:
    """match_id ↔ api-football fixture_id mapping, cached after first
    resolution so subsequent lineup fetches don't re-query /fixtures."""
    match_id:                str
    api_football_fixture_id: int
    home_team_id:            int
    away_team_id:            int
    kickoff_utc:             str
    resolved_at:             str


@dataclass(frozen=True)
class InjuryRow:
    api_football_team_id: int
    player_id:            int
    player_name:          str
    type:                 str
    reason:               str
    position:             str | None
    fetched_at:           str


@dataclass(frozen=True)
class InjuryPenalty:
    iso3:            str
    elo_penalty:     float
    n_players:       int
    computed_at:     str
    source_endpoint: str
    transform:       str


@dataclass(frozen=True)
class FormDelta:
    iso3:        str
    form_delta:  float
    sample_size: int
    computed_at: str
    # Citation / lineage — every externally-derived datum carries
    # source provenance per data-layer spec §3.5. The transform is
    # the function that computed the value from the source(s).
    source_id:         str = "api_football"
    source_endpoint:   str = ""
    source_fetched_at: str = ""
    transform:         str = "compute_form_delta"


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
        *,
        computed_at:       datetime | None = None,
        source_endpoint:   str = "",
        source_fetched_at: datetime | str | None = None,
    ) -> None:
        ts = (computed_at or datetime.now(tz=timezone.utc)).isoformat()
        fetched_at = source_fetched_at
        if isinstance(fetched_at, datetime):
            fetched_at = fetched_at.isoformat()
        fetched_at = fetched_at or ""
        self._conn.execute(
            "INSERT INTO form_deltas("
            "  iso3, form_delta, sample_size, computed_at, "
            "  source_id, source_endpoint, source_fetched_at, transform"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(iso3) DO UPDATE SET "
            "  form_delta = excluded.form_delta, "
            "  sample_size = excluded.sample_size, "
            "  computed_at = excluded.computed_at, "
            "  source_endpoint = excluded.source_endpoint, "
            "  source_fetched_at = excluded.source_fetched_at",
            (
                iso3.lower(), form_delta, sample_size, ts,
                "api_football", source_endpoint, fetched_at, "compute_form_delta",
            ),
        )

    def form_delta_for_iso3(self, iso3: str) -> FormDelta | None:
        row = self._conn.execute(
            "SELECT iso3, form_delta, sample_size, computed_at, "
            "       source_id, source_endpoint, source_fetched_at, transform "
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
            source_id=row["source_id"] or "api_football",
            source_endpoint=row["source_endpoint"] or "",
            source_fetched_at=row["source_fetched_at"] or "",
            transform=row["transform"] or "compute_form_delta",
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

    # ── B.3 injuries ──────────────────────────────────────────────

    def replace_injuries_for_team(
        self,
        api_football_team_id: int,
        rows: list[InjuryRow],
    ) -> int:
        """Delete-then-insert all rows for a team. Empty `rows` means
        the team has no current injuries (every previous row is
        wiped — players have recovered)."""
        self._conn.execute(
            "DELETE FROM injuries WHERE api_football_team_id = ?",
            (api_football_team_id,),
        )
        for r in rows:
            self._conn.execute(
                "INSERT INTO injuries("
                "  api_football_team_id, player_id, player_name, type, reason, "
                "  position, fetched_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    r.api_football_team_id, r.player_id, r.player_name,
                    r.type, r.reason, r.position, r.fetched_at,
                ),
            )
        return len(rows)

    def injuries_for_team(
        self, api_football_team_id: int,
    ) -> list[InjuryRow]:
        rows = self._conn.execute(
            "SELECT api_football_team_id, player_id, player_name, type, "
            "       reason, position, fetched_at "
            "FROM injuries WHERE api_football_team_id = ? "
            "ORDER BY player_id",
            (api_football_team_id,),
        ).fetchall()
        return [InjuryRow(
            api_football_team_id=int(r["api_football_team_id"]),
            player_id=int(r["player_id"]),
            player_name=r["player_name"], type=r["type"],
            reason=r["reason"], position=r["position"],
            fetched_at=r["fetched_at"],
        ) for r in rows]

    def upsert_injury_penalty(
        self, iso3: str, elo_penalty: float, n_players: int,
        *, computed_at: datetime | None = None,
        source_endpoint: str = "",
    ) -> None:
        ts = (computed_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO injury_penalties("
            "  iso3, elo_penalty, n_players, computed_at, "
            "  source_endpoint, transform"
            ") VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(iso3) DO UPDATE SET "
            "  elo_penalty = excluded.elo_penalty, "
            "  n_players = excluded.n_players, "
            "  computed_at = excluded.computed_at, "
            "  source_endpoint = excluded.source_endpoint",
            (iso3.lower(), elo_penalty, n_players, ts,
             source_endpoint, "compute_injury_penalty"),
        )

    def injury_penalty_for_iso3(self, iso3: str) -> InjuryPenalty | None:
        row = self._conn.execute(
            "SELECT iso3, elo_penalty, n_players, computed_at, "
            "       source_endpoint, transform "
            "FROM injury_penalties WHERE iso3 = ?",
            (iso3.lower(),),
        ).fetchone()
        if not row:
            return None
        return InjuryPenalty(
            iso3=row["iso3"],
            elo_penalty=float(row["elo_penalty"]),
            n_players=int(row["n_players"]),
            computed_at=row["computed_at"],
            source_endpoint=row["source_endpoint"] or "",
            transform=row["transform"] or "compute_injury_penalty",
        )

    # ── B-Slice lineups ──────────────────────────────────────────

    def upsert_lineup(self, row: LineupRow) -> None:
        """Insert or replace one team's lineup for a fixture."""
        import json as _json
        self._conn.execute(
            "INSERT INTO lineups("
            "  fixture_id, api_football_team_id, state, formation, "
            "  coach_name, starters, substitutes, fetched_at, announced_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(fixture_id, api_football_team_id) DO UPDATE SET "
            "  state = excluded.state, "
            "  formation = excluded.formation, "
            "  coach_name = excluded.coach_name, "
            "  starters = excluded.starters, "
            "  substitutes = excluded.substitutes, "
            "  fetched_at = excluded.fetched_at, "
            "  announced_at = excluded.announced_at",
            (
                row.fixture_id, row.api_football_team_id, row.state,
                row.formation, row.coach_name,
                _json.dumps(list(row.starters)),
                _json.dumps(list(row.substitutes)),
                row.fetched_at, row.announced_at,
            ),
        )

    def lineup_for(
        self, *, fixture_id: int, api_football_team_id: int,
    ) -> LineupRow | None:
        import json as _json
        row = self._conn.execute(
            "SELECT fixture_id, api_football_team_id, state, formation, "
            "       coach_name, starters, substitutes, fetched_at, announced_at "
            "FROM lineups WHERE fixture_id = ? AND api_football_team_id = ?",
            (fixture_id, api_football_team_id),
        ).fetchone()
        if not row:
            return None
        try:
            starters = tuple(_json.loads(row["starters"] or "[]"))
            subs = tuple(_json.loads(row["substitutes"] or "[]"))
        except (TypeError, ValueError):
            starters, subs = (), ()
        return LineupRow(
            fixture_id=int(row["fixture_id"]),
            api_football_team_id=int(row["api_football_team_id"]),
            state=row["state"],
            formation=row["formation"],
            coach_name=row["coach_name"],
            starters=starters,
            substitutes=subs,
            fetched_at=row["fetched_at"],
            announced_at=row["announced_at"],
        )

    def lineup_for_team(
        self, *, api_football_team_id: int,
    ) -> LineupRow | None:
        """Most-recent lineup for this team across any fixture. Used by
        the hot path when the runtime doesn't know the fixture_id yet —
        the lineup table only carries upcoming fixtures, so the latest
        row is the relevant one for the next match.
        """
        import json as _json
        row = self._conn.execute(
            "SELECT fixture_id, api_football_team_id, state, formation, "
            "       coach_name, starters, substitutes, fetched_at, announced_at "
            "FROM lineups WHERE api_football_team_id = ? "
            "ORDER BY fetched_at DESC LIMIT 1",
            (api_football_team_id,),
        ).fetchone()
        if not row:
            return None
        try:
            starters = tuple(_json.loads(row["starters"] or "[]"))
            subs = tuple(_json.loads(row["substitutes"] or "[]"))
        except (TypeError, ValueError):
            starters, subs = (), ()
        return LineupRow(
            fixture_id=int(row["fixture_id"]),
            api_football_team_id=int(row["api_football_team_id"]),
            state=row["state"],
            formation=row["formation"],
            coach_name=row["coach_name"],
            starters=starters,
            substitutes=subs,
            fetched_at=row["fetched_at"],
            announced_at=row["announced_at"],
        )

    # ── Fixture resolution (match_id ↔ api-football fixture_id) ──

    def upsert_fixture_resolution(
        self, *, match_id: str, api_football_fixture_id: int,
        home_team_id: int, away_team_id: int,
        kickoff_utc: datetime | str,
        resolved_at: datetime | None = None,
    ) -> None:
        if isinstance(kickoff_utc, datetime):
            kickoff_utc = kickoff_utc.isoformat()
        ts = (resolved_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO fixture_resolution("
            "  match_id, api_football_fixture_id, home_team_id, away_team_id, "
            "  kickoff_utc, resolved_at"
            ") VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(match_id) DO UPDATE SET "
            "  api_football_fixture_id = excluded.api_football_fixture_id, "
            "  home_team_id = excluded.home_team_id, "
            "  away_team_id = excluded.away_team_id, "
            "  kickoff_utc = excluded.kickoff_utc, "
            "  resolved_at = excluded.resolved_at",
            (
                match_id, api_football_fixture_id, home_team_id, away_team_id,
                kickoff_utc, ts,
            ),
        )

    def fixture_resolution_for(self, match_id: str) -> FixtureResolution | None:
        row = self._conn.execute(
            "SELECT match_id, api_football_fixture_id, home_team_id, "
            "       away_team_id, kickoff_utc, resolved_at "
            "FROM fixture_resolution WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        if not row:
            return None
        return FixtureResolution(
            match_id=row["match_id"],
            api_football_fixture_id=int(row["api_football_fixture_id"]),
            home_team_id=int(row["home_team_id"]),
            away_team_id=int(row["away_team_id"]),
            kickoff_utc=row["kickoff_utc"],
            resolved_at=row["resolved_at"],
        )

    def list_fixture_resolutions_in_window(
        self, *, now: datetime, window_hours: float,
    ) -> list[FixtureResolution]:
        """Resolutions whose kickoff lands inside [now, now+window].
        Used by the T-90m loop to pick fixtures to refresh lineups for.
        """
        upper = (now + timedelta(hours=window_hours)).isoformat()
        lower = now.isoformat()
        rows = self._conn.execute(
            "SELECT match_id, api_football_fixture_id, home_team_id, "
            "       away_team_id, kickoff_utc, resolved_at "
            "FROM fixture_resolution "
            "WHERE kickoff_utc >= ? AND kickoff_utc <= ? "
            "ORDER BY kickoff_utc",
            (lower, upper),
        ).fetchall()
        return [FixtureResolution(
            match_id=r["match_id"],
            api_football_fixture_id=int(r["api_football_fixture_id"]),
            home_team_id=int(r["home_team_id"]),
            away_team_id=int(r["away_team_id"]),
            kickoff_utc=r["kickoff_utc"],
            resolved_at=r["resolved_at"],
        ) for r in rows]
