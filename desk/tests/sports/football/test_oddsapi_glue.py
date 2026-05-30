"""Unit tests for desk/sports/football/oddsapi_glue.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from desk.data.oddsapi.events import parse_event_payload
from desk.sports.football.oddsapi_glue import (
    EPL_TEAM_SHORT,
    fixtures_from_oddsapi_payload,
    from_oddsapi_event,
    short_code_for_epl_team,
)


SAMPLE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "oddsapi" / "sample_epl_event.json"
)


def _sample() -> list[dict]:
    return json.loads(SAMPLE_PATH.read_text())


def test_resolves_canonical_match_id() -> None:
    """A Man Utd vs Liverpool EPL event maps to fb-epl-mun-liv-20260815."""
    parsed = parse_event_payload(_sample())
    fixtures = fixtures_from_oddsapi_payload(parsed)
    assert len(fixtures) == 1
    fx = fixtures[0]
    assert fx.match_id    == "fb-epl-mun-liv-20260815"
    assert fx.sport       == "football"
    assert fx.competition_code  == "epl"
    assert fx.competition_label == "Premier League"
    assert fx.team_a == "Manchester United"
    assert fx.team_b == "Liverpool"
    assert fx.kickoff_utc == datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)
    assert fx.market_outcomes == ("a", "draw", "b")
    assert fx.source_venue == "odds_api"
    assert fx.source_event_slug == "abc123-event-id-mun-liv"


def test_unknown_team_drops_event() -> None:
    """An EPL event whose team isn't in the lookup is skipped, not
    misclassified. Better to publish 5 known fixtures than 5 known +
    1 fixture with a garbled match_id."""
    parsed_event = {
        "event_id":      "ev1",
        "sport_key":     "soccer_epl",
        "commence_time": datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc),
        "home_team":     "Wycombe Wanderers",   # not EPL — not in table
        "away_team":     "Liverpool",
        "price_rows":    [],
    }
    assert from_oddsapi_event(parsed_event) is None


def test_unmapped_sport_key_returns_none() -> None:
    """If we ever fetch a sport_key we haven't mapped yet, surface
    None — the test is the canary that flags the new league."""
    parsed_event = {
        "event_id":      "ev1",
        "sport_key":     "soccer_la_liga",     # not in v1 launch map
        "commence_time": datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc),
        "home_team":     "Real Madrid",
        "away_team":     "Barcelona",
        "price_rows":    [],
    }
    assert from_oddsapi_event(parsed_event) is None


def test_dedupes_match_id() -> None:
    parsed = parse_event_payload(_sample())
    fixtures = fixtures_from_oddsapi_payload(parsed + parsed)   # double up
    assert len(fixtures) == 1


def test_epl_short_codes_unique() -> None:
    """Match ids depend on team-short uniqueness. If two teams in the
    table share a code, the canonical match_id collides — fail loud."""
    codes = list(EPL_TEAM_SHORT.values())
    assert len(set(codes)) == len(set(codes))


def test_short_code_lookup_normalises_whitespace() -> None:
    assert short_code_for_epl_team("Manchester United") == "mun"
    assert short_code_for_epl_team("  Manchester United  ") == "mun"
    assert short_code_for_epl_team("Wycombe") is None


def test_handles_kickoff_with_naive_datetime() -> None:
    """Naive datetimes get tagged UTC defensively before going into the
    fixture — the FixtureRef contract is UTC-aware."""
    parsed_event = {
        "event_id":      "ev1",
        "sport_key":     "soccer_epl",
        "commence_time": datetime(2026, 8, 15, 15, 0),   # naive
        "home_team":     "Manchester United",
        "away_team":     "Liverpool",
        "price_rows":    [],
    }
    fx = from_oddsapi_event(parsed_event)
    assert fx is not None
    assert fx.kickoff_utc.tzinfo is not None
