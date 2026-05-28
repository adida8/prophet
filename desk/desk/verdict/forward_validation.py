"""Forward-validation harness for Phase B coupled units.

Per `THE_DESK_DATA_LAYER_SPEC.md` §5: a coupled (data, model-hook) phase
stays in **Shadow** until its forward-validation report clears the §1.4
gate (≥100 resolved fixtures, no Brier regression vs the prior phase,
sane directional behaviour). This module is what records predictions
at each bind point and scores them once the actual outcomes resolve.

Sqlite-backed (similar to signals.db). Schema:

* `predictions` — one row per (match_id, asof_iso). At each bind point
  we log BOTH the "without-residual" probabilities (what the engine
  actually published) AND the "with-residual" probabilities (what the
  model would have published if the hook had been Live). Comparing
  Brier scores across the two columns is how we measure the lever.
* `outcomes` — one row per match_id, populated by the resolution
  pipeline when the fixture's final score is known.

Storage is append-only on predictions: re-logging the same `(match_id,
asof_iso)` updates in place but is rare in practice.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    match_id              TEXT NOT NULL,
    asof_iso              TEXT NOT NULL,
    phase                 TEXT NOT NULL,
    p_a_without_residual  REAL NOT NULL,
    p_draw_without_residual REAL NOT NULL,
    p_b_without_residual  REAL NOT NULL,
    p_a_with_residual     REAL NOT NULL,
    p_draw_with_residual  REAL NOT NULL,
    p_b_with_residual     REAL NOT NULL,
    feature_set           TEXT NOT NULL,
    logged_at             TEXT NOT NULL,
    PRIMARY KEY (match_id, asof_iso, phase)
);

CREATE INDEX IF NOT EXISTS idx_predictions_match
    ON predictions(match_id);

CREATE TABLE IF NOT EXISTS outcomes (
    match_id      TEXT PRIMARY KEY,
    outcome       TEXT NOT NULL,
    resolved_at   TEXT NOT NULL
);
"""

Outcome = Literal["a", "draw", "b"]


@dataclass(frozen=True)
class PredictionRow:
    match_id:              str
    asof_iso:              str
    phase:                 str    # "B.1.form" / "B.2.weather" / "B.3.injury"
    p_a_without_residual:  float
    p_draw_without_residual: float
    p_b_without_residual:  float
    p_a_with_residual:     float
    p_draw_with_residual:  float
    p_b_with_residual:     float
    feature_set:           str    # compact JSON of which features fired
    logged_at:             str


class ForwardValidationLog:
    """Read/write façade. Use as `with ForwardValidationLog(path) as log:`."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ForwardValidationLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def log_prediction(self, row: PredictionRow) -> None:
        self._conn.execute(
            "INSERT INTO predictions("
            "  match_id, asof_iso, phase,"
            "  p_a_without_residual, p_draw_without_residual, p_b_without_residual,"
            "  p_a_with_residual, p_draw_with_residual, p_b_with_residual,"
            "  feature_set, logged_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(match_id, asof_iso, phase) DO UPDATE SET "
            "  p_a_without_residual = excluded.p_a_without_residual, "
            "  p_draw_without_residual = excluded.p_draw_without_residual, "
            "  p_b_without_residual = excluded.p_b_without_residual, "
            "  p_a_with_residual = excluded.p_a_with_residual, "
            "  p_draw_with_residual = excluded.p_draw_with_residual, "
            "  p_b_with_residual = excluded.p_b_with_residual, "
            "  feature_set = excluded.feature_set, "
            "  logged_at = excluded.logged_at",
            (
                row.match_id, row.asof_iso, row.phase,
                row.p_a_without_residual, row.p_draw_without_residual, row.p_b_without_residual,
                row.p_a_with_residual, row.p_draw_with_residual, row.p_b_with_residual,
                row.feature_set, row.logged_at,
            ),
        )

    def record_outcome(self, match_id: str, outcome: Outcome,
                       *, resolved_at: datetime | None = None) -> None:
        ts = (resolved_at or datetime.now(tz=timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO outcomes(match_id, outcome, resolved_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(match_id) DO UPDATE SET "
            "  outcome = excluded.outcome, "
            "  resolved_at = excluded.resolved_at",
            (match_id, outcome, ts),
        )

    def predictions_for(self, match_id: str) -> list[PredictionRow]:
        rows = self._conn.execute(
            "SELECT * FROM predictions WHERE match_id = ? ORDER BY asof_iso, phase",
            (match_id,),
        ).fetchall()
        return [PredictionRow(**dict(r)) for r in rows]

    def resolved_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM outcomes").fetchone()
        return int(row["c"])

    def pending_match_ids(self) -> list[str]:
        """match_ids that have at least one prediction but no outcome
        recorded yet. Outcomes-ingest CLI calls this to know what to
        ask api-football about."""
        rows = self._conn.execute(
            "SELECT DISTINCT p.match_id FROM predictions p "
            "LEFT JOIN outcomes o ON o.match_id = p.match_id "
            "WHERE o.match_id IS NULL "
            "ORDER BY p.match_id"
        ).fetchall()
        return [r["match_id"] for r in rows]

    def resolved_prediction_pairs(
        self, *, phase: str = "B.1.form",
    ) -> list[tuple[str, str, PredictionRow]]:
        """Inner join — for each resolved match in `phase`, return
        (match_id, outcome, PredictionRow). When multiple predictions
        exist per match (across asof points), the most recent asof
        wins — it's the published-tick prediction closest to the
        outcome."""
        rows = self._conn.execute(
            "SELECT o.match_id AS oid, o.outcome AS outcome, p.* "
            "FROM outcomes o "
            "JOIN predictions p ON p.match_id = o.match_id "
            "WHERE p.phase = ? "
            "ORDER BY o.match_id, p.asof_iso DESC",
            (phase,),
        ).fetchall()
        seen: set[str] = set()
        out: list[tuple[str, str, PredictionRow]] = []
        for r in rows:
            mid = r["oid"]
            if mid in seen:
                continue
            seen.add(mid)
            # Pop the join columns before kw-expanding into PredictionRow.
            data = dict(r)
            data.pop("oid")
            outcome = data.pop("outcome")
            out.append((mid, outcome, PredictionRow(**data)))
        return out


def default_log_path() -> Path:
    """Path to the forward-validation sqlite log. Honours
    `DESK_FORWARD_VALIDATION_DB_PATH` so Railway can mount a persistent
    volume; without it, every redeploy drops the accumulated sample."""
    import os
    from desk import config
    raw = os.environ.get("DESK_FORWARD_VALIDATION_DB_PATH")
    if raw:
        return Path(raw)
    return Path(config.ROOT) / "data" / "forward_validation.db"
