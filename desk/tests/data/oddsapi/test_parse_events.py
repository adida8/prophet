"""Unit tests for parsing Odds API event payloads."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.data.oddsapi.events import (
    parse_event_payload,
    venue_ids_in_events,
)
from desk.data.oddsapi.venues import LAUNCH_VENUE_IDS


SAMPLE_PATH = Path(__file__).parent / "sample_epl_event.json"


def _sample() -> list[dict]:
    return json.loads(SAMPLE_PATH.read_text())


def test_parses_canonical_event() -> None:
    parsed = parse_event_payload(_sample())
    assert len(parsed) == 1
    ev = parsed[0]
    assert ev["event_id"]      == "abc123-event-id-mun-liv"
    assert ev["sport_key"]     == "soccer_epl"
    assert ev["home_team"]     == "Manchester United"
    assert ev["away_team"]     == "Liverpool"
    assert ev["commence_time"] == datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)


def test_filters_to_launch_venue_set() -> None:
    """Unibet exists in the sample but isn't in LAUNCH_VENUE_IDS —
    every parsed price row must come from an approved venue."""
    parsed = parse_event_payload(_sample())
    venues = venue_ids_in_events(parsed)
    assert "unibet_uk" not in venues
    for v in venues:
        assert v in LAUNCH_VENUE_IDS


def test_each_launch_book_priced_all_three_sides() -> None:
    parsed = parse_event_payload(_sample())
    rows = parsed[0]["price_rows"]
    by_venue: dict[str, set[str]] = {}
    for r in rows:
        by_venue.setdefault(r.venue_id, set()).add(r.side)
    # All four launch venues that appear in the sample priced all three sides.
    for venue in ("pinnacle", "williamhill", "skybet", "betfair_ex_uk"):
        assert by_venue.get(venue) == {"a", "draw", "b"}, (
            f"{venue} did not price all three sides: {by_venue.get(venue)}"
        )


def test_outcome_side_classification() -> None:
    parsed = parse_event_payload(_sample())
    rows = parsed[0]["price_rows"]
    # Pinnacle's home / draw / away picked up correctly.
    pinnacle = {r.side: r.decimal_odds for r in rows if r.venue_id == "pinnacle"}
    assert pinnacle == {"a": 3.10, "draw": 3.40, "b": 2.40}


def test_rejects_sub_evens_prices() -> None:
    """A decimal odds of 1.00 means no payout — drop instead of caching
    an unusable row."""
    payload = _sample()
    payload[0]["bookmakers"].append({
        "key": "pinnacle",
        "title": "Pinnacle",
        "last_update": "2026-08-12T10:00:00Z",
        "markets": [{"key": "h2h", "outcomes": [
            {"name": "Manchester United", "price": 1.00},  # bad — dropped
            {"name": "Liverpool",         "price": 2.40},  # good — kept
        ]}],
    })
    parsed = parse_event_payload(payload)
    rows = parsed[0]["price_rows"]
    # Should still find Pinnacle's "b" side; the 1.00 row was dropped.
    pinnacle_sides = {r.side for r in rows if r.venue_id == "pinnacle"}
    assert "a" in pinnacle_sides  # original 3.10 row
    assert "b" in pinnacle_sides  # original 2.40 row


def test_handles_empty_payload() -> None:
    """Bad / empty payloads return empty lists, never raise."""
    assert parse_event_payload(None) == []
    assert parse_event_payload([]) == []
    assert parse_event_payload([{"id": 123}]) == []  # missing string fields
    assert parse_event_payload([{
        "id": "x", "sport_key": "soccer_epl",
        "commence_time": "garbage",
        "home_team": "A", "away_team": "B",
    }]) == []  # bad ISO timestamp


def test_unknown_outcome_name_dropped_quietly() -> None:
    """If a book quotes 'Newcastle' on a Man Utd vs Liverpool fixture,
    we drop the row rather than misclassify."""
    payload = _sample()
    payload[0]["bookmakers"][0]["markets"][0]["outcomes"].append(
        {"name": "Newcastle", "price": 50.0}
    )
    parsed = parse_event_payload(payload)
    rows = parsed[0]["price_rows"]
    # Newcastle should not appear under any side.
    assert all(r.decimal_odds != 50.0 for r in rows)
