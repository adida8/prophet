"""Sport boundary — the protocol every sport package implements.

The verdict, explainer scaffold, scheduler, and publisher are all written
against this protocol; they never import from `sports/football/` directly.
Adding tennis later = a new package implementing `Sport` + a registry
entry. Football is the only sport in v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal, Protocol, runtime_checkable

MarketSide = Literal["a", "b", "draw"]


@dataclass(frozen=True)
class FixtureRef:
    """A fixture as the engine sees it.

    `match_id` is canonical and stable; downstream steps key on it. Names
    are display-only and may be edited later. Every other piece of identity
    (competition stage, venue) lives on the same record so the publisher
    has everything it needs to write a stub `MatchOutput` without reaching
    back into a sport-specific store.
    """
    match_id:        str
    sport:           str
    competition_code:  str
    competition_label: str
    competition_stage: str | None
    team_a:          str
    team_b:          str
    kickoff_utc:     datetime
    market_outcomes: tuple[MarketSide, ...]
    venue_city:      str | None
    venue_stadium:   str | None
    venue_country:   str | None    # ISO-2

    # Source attribution — useful for ingest debugging, not in the contract.
    source_event_slug: str | None = None
    source_venue:      str | None = None  # "polymarket" / "kalshi"


@runtime_checkable
class Sport(Protocol):
    """Everything a sport package must implement.

    PR 2 added `list_fixtures`. PR 3 added the model. PR 4 adds
    `list_priced_fixtures` (fixtures paired with their current market
    snapshots) and `decide` (model output + market → verdict).
    """

    code:        str    # registry key, e.g. "football"
    short_code:  str    # match_id prefix, e.g. "fb"
    label:       str    # human-readable name, e.g. "Football"

    def list_fixtures(self) -> Iterable[FixtureRef]:
        """Return every priced fixture currently known. Should be cheap to
        call repeatedly — implementations cache and de-duplicate.
        """
        ...

    def list_priced_fixtures(self) -> Iterable[tuple[FixtureRef, "object"]]:
        """Return (fixture, MarketSnapshot) pairs. The runner uses this
        to drive the model + verdict pipeline in a single pass.
        """
        ...

    def market_outcomes(self) -> tuple[MarketSide, ...]:
        """Outcome universe for this sport. Football is 3-way; tennis 2-way."""
        ...
