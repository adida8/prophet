"""Ops telemetry — persisted run log + recorder.

Sport-agnostic. The runner builds a `RunReport` per pass; `Recorder`
persists it to `data/output/ops/runs/{run_id}.json` and maintains an
`index.json` manifest. The dashboard (PR 4–5) reads this log; the diff
engine (PR 3) compares consecutive snapshots.
"""

from desk.ops.report import (
    FixtureRow,
    ForcedPassCounts,
    IngestStats,
    RunReport,
    RunStatus,
    RunTrigger,
    SourceStatus,
    StageCount,
    VerdictCounts,
    fixture_row_from_match,
)
from desk.ops.recorder import Recorder
from desk.ops.diff import MatchChange, diff_snapshots

__all__ = [
    "FixtureRow",
    "ForcedPassCounts",
    "IngestStats",
    "MatchChange",
    "Recorder",
    "RunReport",
    "RunStatus",
    "RunTrigger",
    "SourceStatus",
    "StageCount",
    "VerdictCounts",
    "diff_snapshots",
    "fixture_row_from_match",
]
