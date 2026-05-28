"""Pydantic models + enums for the social subsystem.

These are pure data types. They never touch sqlite directly — the queue
in `desk.social.queue` is the only thing that talks to the DB. Keeping
the boundary clean means tests can construct payloads + slides without
opening a SocialQueue at all.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ── Enums ─────────────────────────────────────────────────────────────


class DraftKind(str, Enum):
    DAILY          = "daily"
    WEEKLY_ROUNDUP = "weekly_roundup"


class DraftStatus(str, Enum):
    PENDING        = "pending"
    APPROVED       = "approved"
    REJECTED       = "rejected"
    SKIPPED        = "skipped"
    PUBLISHED      = "published"
    PUBLISH_FAILED = "publish_failed"


# Terminal states. Once a draft lands here it never moves again.
TERMINAL_STATUSES: frozenset[DraftStatus] = frozenset({
    DraftStatus.REJECTED,
    DraftStatus.SKIPPED,
    DraftStatus.PUBLISHED,
})


# Legal state transitions. Anything not in this map → 409 invalid_state.
ALLOWED_TRANSITIONS: dict[DraftStatus, frozenset[DraftStatus]] = {
    DraftStatus.PENDING:        frozenset({DraftStatus.APPROVED,
                                           DraftStatus.REJECTED,
                                           DraftStatus.SKIPPED}),
    DraftStatus.APPROVED:       frozenset({DraftStatus.PUBLISHED,
                                           DraftStatus.PUBLISH_FAILED}),
    DraftStatus.PUBLISH_FAILED: frozenset({DraftStatus.APPROVED,
                                           DraftStatus.PUBLISHED}),
}


def can_transition(from_state: DraftStatus, to_state: DraftStatus) -> bool:
    """True iff `from_state → to_state` is a legal move."""
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


# ── Slides ────────────────────────────────────────────────────────────


class SlideAsset(BaseModel):
    """One rendered carousel slide on disk.

    `png_sha256` is the content hash — used by the bundle endpoint to
    detect a corrupted volume before serving the zip to the operator.
    """
    model_config = ConfigDict(extra="forbid")

    slide_no:   Annotated[int, Field(ge=1, le=4)]
    png_path:   Path
    png_sha256: Annotated[str, StringConstraints(min_length=64, max_length=64,
                                                  pattern=r"^[0-9a-f]+$")]


# ── Roundup payload (weekly) ──────────────────────────────────────────


class RoundupPick(BaseModel):
    """One row inside the weekly roundup — a match the engine called Pick
    inside the trailing 7-day window."""
    model_config = ConfigDict(extra="forbid")

    match_id:        Annotated[str, StringConstraints(min_length=1, max_length=120)]
    team_a:          Annotated[str, StringConstraints(min_length=1, max_length=64)]
    team_b:          Annotated[str, StringConstraints(min_length=1, max_length=64)]
    pick_side:       Annotated[str, StringConstraints(min_length=1, max_length=64)]
    edge_pp:         float
    kickoff_utc:     datetime


class ResolvedPick(BaseModel):
    """A Pick from a prior week whose result is now known. Drives both
    the hit-rate and "what we got wrong" sections."""
    model_config = ConfigDict(extra="forbid")

    match_id:   Annotated[str, StringConstraints(min_length=1, max_length=120)]
    pick_side:  Annotated[str, StringConstraints(min_length=1, max_length=64)]
    edge_pp:    float
    won:        bool


class WeeklyRoundupPayload(BaseModel):
    """The full structured input the renderer + captioner consume for the
    Sunday roundup. Frozen into `social_drafts.source_json` so a reprint
    is byte-deterministic."""
    model_config = ConfigDict(extra="forbid")

    week_starting:        date
    top_picks:            list[RoundupPick] = Field(default_factory=list, max_length=10)
    hit_rate:             Optional[float]   = None
    hit_rate_sample_size: int               = 0
    what_we_got_wrong:    Optional[ResolvedPick] = None
