"""RunReport — the persisted record of one `run_once()` pass.

This module is sport-agnostic. It never imports from `desk/sports/` —
counts and per-fixture rows are handed in by the runner, which calls
into each sport. See `THE_DESK_OPS_DASHBOARD_SPEC.md` §3–§6.

PR 1 scope: data model + helpers for assembling a `RunReport`. The
`forced_pass` counters carry zeros until PR 2 wires `DecisionMeta` out
of `decide()`; the `changes` field stays empty until PR 3 lands the
diff engine. The shape is forward-compatible so neither PR has to
re-cut the file format.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from desk.publish.contract import MatchOutput

RUN_ID_RE = re.compile(r"^run-\d{8}T\d{6}Z$")
RunId = Annotated[str, StringConstraints(pattern=RUN_ID_RE.pattern)]


def run_id_for(ts: datetime) -> str:
    """`run-YYYYMMDDTHHMMSSZ` — UTC, second precision."""
    if ts.tzinfo is None or ts.utcoffset().total_seconds() != 0:
        raise ValueError("run_id timestamps must be UTC")
    return ts.strftime("run-%Y%m%dT%H%M%SZ")


class RunStatus(str, Enum):
    OK      = "ok"
    PARTIAL = "partial"
    FAIL    = "fail"


class RunTrigger(str, Enum):
    MANUAL    = "manual"
    SCHEDULED = "scheduled"   # set by PR 6 once the scheduler lands


class SourceFreshness(str, Enum):
    FRESH  = "fresh"
    STALE  = "stale"
    FAILED = "failed"
    FROZEN = "frozen"     # e.g. seed Elo until live Elo lands
    STATIC = "static"     # never-changes (e.g. WC26 venues)


class ErrorLevel(str, Enum):
    WARN  = "warn"
    ERROR = "error"


# ── Funnel ────────────────────────────────────────────────────────────

class StageCount(BaseModel):
    """One row of the pipeline funnel.

    Per-stage `note` is a human-readable annotation surfaced verbatim
    in the dashboard (e.g. "N with kalshi coverage" on `priced_fixtures`).
    """
    model_config = ConfigDict(extra="forbid")

    stage: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    n:     int = Field(ge=0)
    note:  Optional[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = None


class ForcedPassCounts(BaseModel):
    """Counters for fixtures the verdict step forced to Pass.

    Populated by PR 2 once `decide()` returns a `DecisionMeta`. PR 1
    leaves both at zero — the verdict_eligible stage of the funnel
    therefore equals `priced_fixtures` until PR 2 lands.
    """
    model_config = ConfigDict(extra="forbid")

    illiquid: int = Field(default=0, ge=0)
    stub_elo: int = Field(default=0, ge=0)

    def total(self) -> int:
        return self.illiquid + self.stub_elo


class VerdictCounts(BaseModel):
    """Pick/Pass/Avoid split for one run.

    `pass` is a Python keyword, so the field is `pass_` with a JSON
    alias of `pass`. Construct in Python with `pass_=…`; the dashboard
    reads `verdicts.pass` because we dump `by_alias=True`.
    """
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    pick:  int = Field(default=0, ge=0)
    pass_: int = Field(default=0, ge=0, alias="pass")
    avoid: int = Field(default=0, ge=0)

    def total(self) -> int:
        return self.pick + self.pass_ + self.avoid


# ── Sources ───────────────────────────────────────────────────────────

class SourceStatus(BaseModel):
    """One row of the "Sources read" panel.

    `id` is a stable string (e.g. `polymarket_gamma`, `elo_seed`) — the
    dashboard keys off it. `last_ok` is the most recent successful pull
    seen on *this* run; `null` when the source hasn't been touched.
    """
    model_config = ConfigDict(extra="forbid")

    id:      Annotated[str, StringConstraints(min_length=1, max_length=64)]
    status:  SourceFreshness
    last_ok: Optional[datetime] = None
    detail:  Annotated[str, StringConstraints(min_length=0, max_length=200)] = ""


# ── Errors ────────────────────────────────────────────────────────────

class ErrorEntry(BaseModel):
    """A structured copy of something the runner already logged.

    The bare logger keeps its output — this list is the dashboard-side
    surface for the same events.
    """
    model_config = ConfigDict(extra="forbid")

    level:   ErrorLevel
    stage:   Annotated[str, StringConstraints(min_length=1, max_length=64)]
    message: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


# ── Per-fixture snapshot (basis for the PR 3 diff) ────────────────────

class FixtureRow(BaseModel):
    """One match's verdict-shape on this run.

    The snapshot list of these rows is the input to the diff engine in
    PR 3: a `FixtureRow` from run N-1 compared to the same `match_id`
    on run N yields the typed change events.

    `copy_hash` is sha256 over `title|summary|blurb` — present so the
    diff engine can detect editorial changes without storing the prose.
    `venues` is the sorted set of venues the match's `MarketSnapshot`
    carried prices for; the diff engine uses set-diff on it.
    """
    model_config = ConfigDict(extra="forbid")

    match_id:      Annotated[str, StringConstraints(min_length=1, max_length=128)]
    verdict_state: Annotated[str, StringConstraints(pattern=r"^(pick|pass|avoid)$")]
    pick_side:     Optional[str] = None
    edge_pp:       Optional[float] = None
    venues:        list[str] = Field(default_factory=list)
    copy_hash:     Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


def fixture_row_from_match(match: MatchOutput, *, venues: list[str]) -> FixtureRow:
    """Build a `FixtureRow` from a `MatchOutput` + the venue set used.

    Venue list is passed in (rather than inferred) because the
    `MatchOutput` contract deliberately omits raw market prices —
    the runner is the only place that holds both pieces.
    """
    v = match.verdict
    state = v.state if isinstance(v.state, str) else v.state.value
    c = match.copy
    h = hashlib.sha256(f"{c.title}|{c.summary}|{c.blurb}".encode("utf-8")).hexdigest()
    return FixtureRow(
        match_id=match.match_id,
        verdict_state=state,
        pick_side=v.side,
        edge_pp=v.edge_pp,
        venues=sorted(set(venues)),
        copy_hash=h,
    )


# ── News-signals impact (per-outlet status + per-run contribution) ────

class SignalImpactRow(BaseModel):
    """One news outlet's status + impact on this run.

    Combines two operator views in one row:
      - *status* — fresh / stale / failed / frozen, last-successful-fetch
        timestamp, and total cached items + extracted signals.
      - *this-run contribution* — citations contributed, hard-track Elo
        adjustments driven, distinct fixtures touched.

    Aggregated by `SignalsRuntime.impact()` and threaded through the
    runner into `RunReport.signal_impact`. Lives alongside (not inside)
    the existing `sources` list so the ops dashboard can render news
    outlets in a richer panel without bloating the engine-source row
    set.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    source_id:         Annotated[str, StringConstraints(min_length=1, max_length=64)]
    name:              Annotated[str, StringConstraints(min_length=1, max_length=128)]
    status:            SourceFreshness
    last_ok:           Optional[datetime] = None
    cached_items:      int = Field(default=0, ge=0)
    extracted_signals: int = Field(default=0, ge=0)
    citations:         int = Field(default=0, ge=0)
    hard_adjustments:  int = Field(default=0, ge=0)
    fixtures_touched:  int = Field(default=0, ge=0)


# ── Ingest stats (handed up from a sport's priced-ingest layer) ───────

class IngestStats(BaseModel):
    """Counts + source signals surfaced by `Sport.last_ingest_stats()`.

    The runner consumes these to build the top of the funnel and the
    `sources` panel. Optional fields are `None` when a sport's ingest
    layer doesn't track that count (the dashboard hides them in that
    case).
    """
    model_config = ConfigDict(extra="forbid")

    raw_events:        Optional[int]   = Field(default=None, ge=0)
    after_filter:      Optional[int]   = Field(default=None, ge=0)
    priced:            int             = Field(ge=0)
    kalshi_hits:       Optional[int]   = Field(default=None, ge=0)
    filtered_note:     Optional[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = None
    priced_note:       Optional[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = None
    sources:           list[SourceStatus] = Field(default_factory=list)


# ── The report ────────────────────────────────────────────────────────

class RunReport(BaseModel):
    """One run's persisted record. One JSON document per run.

    Stored at `data/output/ops/runs/{run_id}.json` and surfaced read-only
    via `/api/desk/ops/*` once PR 4 ships.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    run_id:       RunId
    started_at:   datetime
    finished_at:  datetime
    duration_s:   float = Field(ge=0.0)
    trigger:      RunTrigger
    status:       RunStatus
    competitions: list[str] = Field(default_factory=list)

    funnel:       list[StageCount] = Field(default_factory=list)
    forced_pass:  ForcedPassCounts = Field(default_factory=ForcedPassCounts)
    verdicts:     VerdictCounts    = Field(default_factory=VerdictCounts)

    sources:       list[SourceStatus]    = Field(default_factory=list)
    errors:        list[ErrorEntry]      = Field(default_factory=list)
    changes:       list[dict]            = Field(default_factory=list)   # populated by PR 3
    snapshot:      list[FixtureRow]      = Field(default_factory=list)
    signal_impact: list[SignalImpactRow] = Field(default_factory=list)

    @field_validator("started_at", "finished_at")
    @classmethod
    def _utc_only(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset().total_seconds() != 0:
            raise ValueError("run timestamps must be UTC")
        return v


# ── Manifest row (one per persisted run) ──────────────────────────────

class RunManifestEntry(BaseModel):
    """Compact row served by `/api/desk/ops/runs?limit=N`.

    Derived from a `RunReport`; the dashboard renders the manifest first
    and only fetches the full report when the operator clicks a row.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    run_id:        RunId
    finished_at:   datetime
    trigger:       RunTrigger
    status:        RunStatus
    published:     int = Field(ge=0)
    picks:         int = Field(ge=0)
    change_count:  int = Field(ge=0)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs:       list[RunManifestEntry] = Field(default_factory=list)
    updated_at: datetime


def manifest_entry_from_report(report: RunReport) -> RunManifestEntry:
    published = next(
        (s.n for s in report.funnel if s.stage == "published"),
        0,
    )
    return RunManifestEntry(
        run_id=report.run_id,
        finished_at=report.finished_at,
        trigger=report.trigger,
        status=report.status,
        published=published,
        picks=report.verdicts.pick,
        change_count=len(report.changes),
    )
