"""Data models for the signals subsystem.

Three primary entities:

  * `Source`     — a registered outlet or aggregator the engine may read.
  * `SourceItem` — one raw item (article / post) fetched from a source.
  * `Signal`     — a structured claim the extractor pulled out of an item.

The track a `Signal` lands on is decided by its source's `can_feed_model`
gate, not by the signal type. See package docstring for the rule.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# `none` here means "the source is in the trust registry but has no public
# feed we can fetch from". Reuters / AP / AFP / The Athletic etc. — we want
# them in the trust framework (so a future licensed-API ingest is just a
# fetcher swap) but they never come through the RSS path.
FeedType = Literal["rss", "sitemap", "api", "aggregator", "none"]
BiasFlag = Literal["none", "national", "club"]
Tier     = Literal["trusted_core", "long_tail"]

# Reliability threshold for the hard-signal track. See registry seed for
# how individual outlets are scored. Kept here (not config) because the
# gate is a design constant of the trust model, not an operational knob.
MODEL_FEED_RELIABILITY_MIN = 0.8


class SignalType(str, Enum):
    """Why we keep `confirmed_lineup` separate from `predicted_lineup`:
    only the confirmed XI (announced ~1h pre-kickoff) is a hard-track
    fact. A predicted XI four days out is editorial colour."""

    INJURY            = "injury"
    SUSPENSION        = "suspension"
    CONFIRMED_LINEUP  = "confirmed_lineup"
    PREDICTED_LINEUP  = "predicted_lineup"
    MORALE            = "morale"
    MANAGER_QUOTE     = "manager_quote"
    FORM              = "form"
    OTHER             = "other"


# Types that are model-eligible *if* the source also passes the trust
# gate. The source gate always dominates — an injury from a biased
# outlet stays editorial. See `Signal.track`.
_HARD_TRACK_TYPES = frozenset({
    SignalType.INJURY,
    SignalType.SUSPENSION,
    SignalType.CONFIRMED_LINEUP,
})


class Source(BaseModel):
    """One registered outlet or aggregator.

    `reliability` and `bias_flag` stay separate on purpose: a biased
    outlet can still be factually accurate, so it's quoted at high
    reliability while being barred from the model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id:           str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name:         str = Field(min_length=1, max_length=120)
    feed_type:    FeedType
    # `feed_ref` is the URL (rss/sitemap), query template (aggregator), or
    # API endpoint (api). For `feed_type=none` it MUST be empty — the row
    # is in the registry for trust weighting only, not fetchable.
    feed_ref:     str = ""
    language:     str = Field(min_length=2, max_length=8)
    coverage_tags: frozenset[str]
    reliability:  float = Field(ge=0.0, le=1.0)
    bias_flag:    BiasFlag = "none"
    parent_org:   str | None = None
    tier:         Tier
    enabled:      bool = True
    # Free-text editorial note on the row (verification date, why it
    # carries `feed_type=none`, etc.). Never reaches the contract.
    notes:        str | None = None

    @field_validator("coverage_tags", mode="before")
    @classmethod
    def _parse_tags(cls, value):
        """Accept three on-disk shapes:
          * JSON array literal — `["global", "sport:football"]`
          * Pipe-separated — `global|sport:football`
          * Python iterable — already a list/set
        """
        if isinstance(value, str):
            s = value.strip()
            if s.startswith("[") and s.endswith("]"):
                # CSV-stored JSON array.
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return frozenset(
                            str(t).strip() for t in parsed if str(t).strip()
                        )
                except json.JSONDecodeError:
                    pass
            return frozenset(t.strip() for t in s.split("|") if t.strip())
        return frozenset(value)

    @field_validator("coverage_tags")
    @classmethod
    def _require_at_least_one_tag(cls, value):
        if not value:
            raise ValueError("coverage_tags must contain at least one tag")
        return value

    @model_validator(mode="after")
    def _feed_ref_matches_feed_type(self) -> "Source":
        if self.feed_type == "none":
            if self.feed_ref:
                raise ValueError(
                    f"source {self.id!r}: feed_type='none' must have empty feed_ref "
                    f"(got {self.feed_ref!r})"
                )
        else:
            if not self.feed_ref:
                raise ValueError(
                    f"source {self.id!r}: feed_type={self.feed_type!r} requires "
                    f"a non-empty feed_ref"
                )
        return self

    @property
    def can_feed_model(self) -> bool:
        """Whether hard signals from this source may move model features."""
        return (
            self.reliability >= MODEL_FEED_RELIABILITY_MIN
            and self.bias_flag == "none"
            and self.tier == "trusted_core"
        )

    @property
    def editorial_only(self) -> bool:
        return not self.can_feed_model


class SourceItem(BaseModel):
    """A raw item fetched from a source. Stored pre-extraction so we can
    dedupe + cache; extraction runs once per (source, canonical url)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id:     str
    url:           str
    canonical_url: str
    title:         str
    body:          str
    published_at:  datetime | None = None
    fetched_at:    datetime
    content_hash:  str


class Signal(BaseModel):
    """A structured claim extracted from a `SourceItem`.

    `quote` is the verbatim line that supports the claim — load-bearing
    for the editorial track's citation guarantee. Translated quotes
    keep the original in `quote_original` so a reader can verify.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type:           SignalType
    team:           str
    claim:          str = Field(min_length=1)
    quote:          str = Field(min_length=1)
    quote_original: str | None = None
    quote_lang:     str | None = None
    source_id:      str
    url:            str
    published_at:   datetime | None = None
    confidence:     float = Field(ge=0.0, le=1.0)

    def track(self, source: Source) -> Literal["hard", "editorial"]:
        """The track this signal lands on. Source gate dominates type."""
        if source.id != self.source_id:
            raise ValueError(
                f"track() called with wrong source: signal.source_id="
                f"{self.source_id!r} vs source.id={source.id!r}"
            )
        if self.type in _HARD_TRACK_TYPES and source.can_feed_model:
            return "hard"
        return "editorial"
