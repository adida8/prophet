"""Test fixtures.

`tmp_publisher` gives every test an isolated `Publisher` rooted in a
temp directory, so file writes never leak across tests or sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.publish import (
    Competition,
    Copy,
    MatchOutput,
    Publisher,
    Venue,
    Verdict,
)


@pytest.fixture
def tmp_publisher(tmp_path: Path) -> Publisher:
    return Publisher(output_dir=tmp_path / "output")


@pytest.fixture
def fra_mex_pick() -> MatchOutput:
    """A canonical Pick — France v Mexico, France called by 4.2pp."""
    return MatchOutput(
        match_id="fb-wc26-fra-mex-20260612",
        sport="football",
        competition=Competition(code="wc26", label="FIFA World Cup 2026", stage="group_d"),
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        team_a="France",
        team_b="Mexico",
        venue=Venue(city="Guadalajara", stadium="Estadio Akron", country="MX"),
        market_outcomes=["a", "draw", "b"],
        verdict=Verdict(
            state="pick",
            side="France",
            market_venue="polymarket",
            price="-180",
            edge_pp=4.2,
        ),
        copy=Copy(
            title="France v Mexico · class shows",
            summary="Two short sentences in Odds Primer voice.",
            blurb="Sixty to ninety words explaining the verdict.",
            citations=["https://lequipe.fr/example", "https://globoesporte.com/example"],
        ),
        updated_at=datetime(2026, 6, 12, 17, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def usa_can_pass() -> MatchOutput:
    """A canonical Pass — USA v Canada, model agrees with the market."""
    return MatchOutput(
        match_id="fb-wc26-usa-can-20260613",
        sport="football",
        competition=Competition(code="wc26", label="FIFA World Cup 2026", stage="group_a"),
        kickoff_utc=datetime(2026, 6, 13, 20, 0, tzinfo=timezone.utc),
        team_a="USA",
        team_b="Canada",
        venue=Venue(city="Inglewood", stadium="SoFi Stadium", country="US"),
        market_outcomes=["a", "draw", "b"],
        verdict=Verdict(state="pass"),
        updated_at=datetime(2026, 6, 13, 18, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def epl_avoid() -> MatchOutput:
    """A canonical Avoid — EPL fixture where every side is overpriced."""
    return MatchOutput(
        match_id="fb-epl-mun-liv-20260815",
        sport="football",
        competition=Competition(code="epl", label="Premier League", stage="matchday_1"),
        kickoff_utc=datetime(2026, 8, 15, 14, 30, tzinfo=timezone.utc),
        team_a="Manchester United",
        team_b="Liverpool",
        venue=Venue(city="Manchester", stadium="Old Trafford", country="GB"),
        market_outcomes=["a", "draw", "b"],
        verdict=Verdict(state="avoid"),
        updated_at=datetime(2026, 8, 15, 12, 30, tzinfo=timezone.utc),
    )
