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
    PICK      = "pick"
    PASS      = "pass"
    AVOID     = "avoid"
    # Lifecycle terminal state. Emitted exactly once when a previously-
    # published match_id leaves the live universe (cancelled, postponed
    # past slug date, de-listed by the source venue). Field semantics
    # match pass/avoid — side/price/edge_pp/model_p/market_p all null.
    # See desk/docs/adr/0001-withdrawn-verdict-state.md.
    WITHDRAWN = "withdrawn"


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
    Withdrawn: lifecycle terminal — match_id has left the live universe
           (cancelled, postponed past slug date, de-listed). All
           fields match the pass/avoid null-shape; the meaning is "we
           previously published this and have now stopped". See ADR
           0001 for detection + invariants.
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


class MarketSource(BaseModel):
    """One prediction-market / sportsbook venue we link out to for this
    fixture.

    The list carries **every venue we surface a trade CTA for**, not just
    the one the Pick rode on — so the front-of-house (and any external
    consumer) can render the full row of outgoing buttons from the
    contract alone.

    Fields:
    - `venue`        — the canonical venue key (matches `MarketVenue`).
    - `name`         — display name for the button ("Polymarket").
    - `url`          — deep link to *this fixture's* page on the venue.
                       Falls back to the venue's nearest landing page when
                       no per-event deep link exists yet (see below).
    - `picked`       — true for the single venue whose price backs the
                       Pick side. False on every venue when the verdict is
                       not a Pick (pass / avoid / withdrawn).
    - `priced_sides` — which market sides this venue actually quoted into
                       the calculation, in `a / draw / b` order. An empty
                       list means the venue is linked for convenience but
                       did **not** feed the model — e.g. a venue we don't
                       yet ingest. This is the honest "used in the
                       calculation?" signal inside an all-venues list: a
                       picked Pick venue always has a non-empty
                       `priced_sides`; a link-only venue has `[]`.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    venue:        MarketVenue
    name:         Annotated[str, StringConstraints(min_length=1, max_length=64)]
    url:          Annotated[str, StringConstraints(min_length=10, max_length=512, pattern=r"^https://")]
    picked:       bool = False
    priced_sides: list[Literal["a", "b", "draw"]] = Field(default_factory=list, max_length=3)


class Citation(BaseModel):
    """An attributed reference behind a claim in the editorial blurb.

    Carries enough for the front-of-house to render a verifiable
    quotation: the outlet's display name, the deep link, the verbatim
    sentence the article carried. `quote` is in English; for
    non-English sources `quote_original` holds the verbatim source-
    language sentence and `quote_lang` the ISO-639-1 code, so a reader
    can verify the translation.

    See `THE_DESK_NEWS_SIGNALS_SPEC.md` §8 — the citation is load-
    bearing for the editorial track. "According to local press…"
    requires a real, fetchable line behind it.
    """
    model_config = ConfigDict(extra="forbid")

    outlet:         Annotated[str, StringConstraints(min_length=1, max_length=120)]
    url:            Annotated[str, StringConstraints(min_length=1, max_length=512)]
    quote:          Annotated[str, StringConstraints(min_length=1, max_length=600)]
    quote_original: Optional[Annotated[str, StringConstraints(min_length=1, max_length=600)]] = None
    quote_lang:     Optional[Annotated[str, StringConstraints(min_length=2, max_length=8)]] = None
    published_at:   Optional[datetime] = None


class HardSignalAdjustment(BaseModel):
    """One news-signal-driven Elo nudge applied before the model ran.

    Surfaces the audit trail the engine keeps internally: which side was
    moved, by how much, from which signal, and where to verify it. Lets
    a reader answer "did this signal change the verdict?" from the
    published JSON alone, without grepping run logs.

    `side` is `"a"` or `"b"` matching the fixture's `team_a` / `team_b`
    naming; `delta_elo` is negative for a penalty (the v1 only direction).
    `capped` is true when the per-team penalty cap clipped this row —
    useful for spotting fixtures where multiple injuries piled up. The
    `signal_*` fields point back to the originating Signal so a reader
    can chase the underlying claim.
    """
    model_config = ConfigDict(extra="forbid")

    side:         Literal["a", "b"]
    team:         Annotated[str, StringConstraints(min_length=1, max_length=64)]
    delta_elo:    float
    capped:       bool = False
    reason:       Annotated[str, StringConstraints(min_length=1, max_length=240)]
    signal_type:  Annotated[str, StringConstraints(min_length=1, max_length=32)]
    signal_url:   Annotated[str, StringConstraints(min_length=1, max_length=512)]
    source_id:    Annotated[str, StringConstraints(min_length=1, max_length=64)]
    source_name:  Optional[Annotated[str, StringConstraints(min_length=1, max_length=128)]] = None
    published_at: Optional[datetime] = None


class Copy(BaseModel):
    """Editorial output. Voice rules enforced by explainer post-checks (PR 5).

    `citations` is the legacy URL-only list — populated by the explainer
    stub today; the front-of-house renders it as a row of source links.

    `editorial_citations` is the structured form added in news-signals
    PR D — each entry carries outlet name + verbatim quote + (optional)
    translation. Populated when the signals cache has editorial-track
    signals covering this fixture; empty otherwise, so this is a
    purely additive contract change.

    `drivers` is the structured "Why this call?" list — 3-4 short
    bullets the front-of-house renders above the CTA. Each bullet is a
    plain-language sentence, not a data dump. The list is allowed to
    be empty for fixtures the engine can't characterise (e.g. a Pass
    on a tightly-priced market with nothing further to say).
    """
    model_config = ConfigDict(extra="forbid")

    title:               Annotated[str, StringConstraints(min_length=0, max_length=120)] = ""
    summary:             Annotated[str, StringConstraints(min_length=0, max_length=400)] = ""
    blurb:               Annotated[str, StringConstraints(min_length=0, max_length=4000)] = ""
    citations:           list[str] = Field(default_factory=list)
    editorial_citations: list[Citation] = Field(default_factory=list, max_length=10)
    drivers:             list[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=6)


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
    market_sources:  list[MarketSource] = Field(default_factory=list, max_length=8)
    hard_signal_adjustments: list[HardSignalAdjustment] = Field(default_factory=list, max_length=20)
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
