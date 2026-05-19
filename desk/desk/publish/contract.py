"""Output contract — single source of truth for what Faktor consumes.

Pydantic v2 models. Generate JSON Schema once, commit
`desk/contract.schema.json`, and any consumer can validate independently.

Internals (model probabilities, drivers, raw market prices, confidence
scores) deliberately do NOT appear here. The contract is the public API;
adding a field requires an ADR (see THE_DESK_SPEC.md §6).
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


# ── Enums ─────────────────────────────────────────────────────────────

class VerdictState(str, Enum):
    PICK  = "pick"
    PASS  = "pass"
    AVOID = "avoid"


class MarketVenue(str, Enum):
    KALSHI     = "kalshi"
    POLYMARKET = "polymarket"


# ── Constraints ───────────────────────────────────────────────────────

# {sport_short}-{competition}-{...}-{yyyymmdd}
_MATCH_ID_RE = re.compile(r"^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$")
MatchId = Annotated[str, StringConstraints(pattern=_MATCH_ID_RE.pattern)]

CountryISO2 = Annotated[
    str, StringConstraints(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
]


# ── Sub-models ────────────────────────────────────────────────────────

class Competition(BaseModel):
    """League or tournament. `stage` is optional and only populated when
    meaningful (`group_d`, `semi_final`, `matchday_8`).
    """
    model_config = ConfigDict(extra="forbid")

    code:  Annotated[str, StringConstraints(min_length=2, max_length=24, pattern=r"^[a-z0-9]+$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    stage: Optional[Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")]] = None


class Venue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city:    Annotated[str, StringConstraints(min_length=1, max_length=64)]
    stadium: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    country: CountryISO2


class Verdict(BaseModel):
    """The call.

    Pick:  side / market_venue / price / edge_pp / market_url / model_p /
           market_p all populated. side is the team **name** (e.g.
           "France") or "draw" — never "team_a". market_url is the deep
           link used by the front-of-house CTA. model_p / market_p are
           the model's and market's implied probabilities for `side`,
           in [0, 1] — they let the editorial layer render
           "Model: 34% · Market: 22% · Edge: +11.1pp" without parsing
           the blurb.
    Pass:  side null, market_venue null, price null, edge_pp may be 0 or
           null, model_p / market_p null (no single side to talk about).
           market_url MAY be set so the user can still browse the market
           on the venue.
    Avoid: side null, market_venue null, price null, edge_pp set to the
           most-negative side's edge. model_p / market_p null. Per ADR
           Phase A.4 the avoid framing is fixture-wide, not side-specific
           — exposing per-side numbers would be misleading.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    state:         VerdictState
    side:          Optional[str] = None
    market_venue:  Optional[MarketVenue] = None
    price:         Optional[Annotated[str, StringConstraints(min_length=1, max_length=16)]] = None
    edge_pp:       Optional[float] = None
    market_url:    Optional[Annotated[str, StringConstraints(min_length=10, max_length=512, pattern=r"^https://")]] = None
    model_p:       Optional[Annotated[float, Field(ge=0.0, le=1.0)]] = None
    market_p:      Optional[Annotated[float, Field(ge=0.0, le=1.0)]] = None

    @model_validator(mode="after")
    def _state_invariants(self) -> "Verdict":
        if self.state == VerdictState.PICK.value or self.state == VerdictState.PICK:
            if self.side is None:
                raise ValueError("verdict.side is required when state='pick'")
            if self.market_venue is None:
                raise ValueError("verdict.market_venue is required when state='pick'")
            if self.price is None:
                raise ValueError("verdict.price is required when state='pick'")
            if self.edge_pp is None:
                raise ValueError("verdict.edge_pp is required when state='pick'")
            if self.market_url is None:
                raise ValueError("verdict.market_url is required when state='pick'")
            if self.model_p is None:
                raise ValueError("verdict.model_p is required when state='pick'")
            if self.market_p is None:
                raise ValueError("verdict.market_p is required when state='pick'")
        else:
            if self.market_venue is not None:
                raise ValueError("verdict.market_venue must be null on pass/avoid")
            if self.price is not None:
                raise ValueError("verdict.price must be null on pass/avoid")
            if self.model_p is not None:
                raise ValueError("verdict.model_p must be null on pass/avoid")
            if self.market_p is not None:
                raise ValueError("verdict.market_p must be null on pass/avoid")
            # market_url MAY pass through on Pass/Avoid — see docstring.
        return self


class Copy(BaseModel):
    """Editorial output. Voice rules enforced by explainer post-checks (PR 5).

    Citations are URLs of the sources Haiku referenced in the blurb.

    `drivers` is the structured "Why this call?" list — 3-4 short
    bullets the front-of-house renders above the CTA. Each bullet is a
    plain-language sentence, not a data dump. The list is allowed to
    be empty for fixtures the engine can't characterise (e.g. a Pass
    on a tightly-priced market with nothing further to say).
    """
    model_config = ConfigDict(extra="forbid")

    title:     Annotated[str, StringConstraints(min_length=0, max_length=120)] = ""
    summary:   Annotated[str, StringConstraints(min_length=0, max_length=400)] = ""
    blurb:     Annotated[str, StringConstraints(min_length=0, max_length=4000)] = ""
    citations: list[str] = Field(default_factory=list)
    drivers:   list[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=6)


# ── Top-level contract ────────────────────────────────────────────────

class MatchOutput(BaseModel):
    """The published JSON for one match.

    `sport` is the registry key. `market_outcomes` declares which outcome
    universe applies to this fixture — football has draws, tennis doesn't,
    so the contract carries it explicitly.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    match_id:        MatchId
    sport:           Annotated[str, StringConstraints(pattern=r"^[a-z]+$")]
    competition:     Competition
    kickoff_utc:     datetime
    team_a:          Annotated[str, StringConstraints(min_length=1, max_length=64)]
    team_b:          Annotated[str, StringConstraints(min_length=1, max_length=64)]
    venue:           Optional[Venue] = None    # populated when known; None for fresh-ingest stubs
    market_outcomes: list[Literal["a", "b", "draw"]] = Field(min_length=2, max_length=3)
    verdict:         Verdict
    copy:            Copy = Field(default_factory=Copy)
    updated_at:      datetime

    @field_validator("kickoff_utc", "updated_at")
    @classmethod
    def _utc_only(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware UTC")
        if v.utcoffset().total_seconds() != 0:
            raise ValueError("timestamps must be UTC (offset 0)")
        return v

    @model_validator(mode="after")
    def _verdict_side_in_universe(self) -> "MatchOutput":
        v = self.verdict
        side = v.side if v.side is not None else None
        if side is None:
            return self
        # `side` is the team NAME or "draw"
        valid = {self.team_a, self.team_b}
        if "draw" in self.market_outcomes:
            valid.add("draw")
        if side not in valid:
            raise ValueError(
                f"verdict.side={side!r} is not one of team_a/team_b/draw "
                f"({sorted(valid)})"
            )
        return self


# ── Index ─────────────────────────────────────────────────────────────

class MatchOutputIndexEntry(BaseModel):
    """One row of the index. The full `MatchOutput` lives in its own file."""
    model_config = ConfigDict(extra="forbid")

    match_id:    MatchId
    kickoff_utc: datetime
    updated_at:  datetime


class OutputIndex(BaseModel):
    """`index.json` published per sport, listing every match in that sport."""
    model_config = ConfigDict(extra="forbid")

    sport:      Annotated[str, StringConstraints(pattern=r"^[a-z]+$")]
    matches:    list[MatchOutputIndexEntry]
    updated_at: datetime
