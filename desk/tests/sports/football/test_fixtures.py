"""Fixture-ingest tests.

Backed by a saved Polymarket gamma response (`tests/fixtures/...`) so
nothing here hits the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from desk.publish import MatchOutput
from desk.publish.contract import Verdict, VerdictState
from desk.runner import _build_match
from desk.sport import FixtureRef
from desk.sports.football.fixtures import (
    SHORT_CODE,
    SPORT,
    fixtures_from_polymarket,
    from_polymarket_event,
    make_match_id,
)
from desk.sports.football.sport import FootballSport
from desk.sports.football.teams import (
    is_international_competition,
    map_competition,
    normalize_team,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


@pytest.fixture(scope="module")
def polymarket_soccer_events() -> list[dict]:
    return json.loads((FIXTURES_DIR / "polymarket_soccer_games.json").read_text())


# ── Sport boundary ────────────────────────────────────────────────────

def test_football_sport_metadata() -> None:
    s = FootballSport()
    assert s.code == "football"
    assert s.short_code == "fb"
    assert s.label == "Football"
    assert s.market_outcomes() == ("a", "draw", "b")


def test_sport_registry_contains_football_only() -> None:
    from desk.sports import SPORT_REGISTRY, active_sports

    assert set(SPORT_REGISTRY.keys()) == {"football"}
    assert [s.code for s in active_sports()] == ["football"]


# ── make_match_id ─────────────────────────────────────────────────────

def test_make_match_id_format() -> None:
    mid = make_match_id(
        competition="wc26", home="fra", away="mex",
        kickoff=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
    )
    assert mid == "fb-wc26-fra-mex-20260612"


def test_match_id_passes_publish_contract_regex() -> None:
    """The match_id we produce must be acceptable to MatchOutput."""
    from desk.publish.contract import _MATCH_ID_RE

    mid = make_match_id(
        competition="epl", home="epl-mun", away="epl-liv",
        kickoff=datetime(2026, 8, 15, 14, 30, tzinfo=timezone.utc),
    )
    assert _MATCH_ID_RE.match(mid)


# ── Polymarket parser correctness ─────────────────────────────────────

def test_parse_wc26_match_event() -> None:
    ev = {
        "slug":  "fifwc-mex-rsa-2026-06-11",
        "title": "Mexico vs. South Africa",
        "endDate": "2026-06-11T19:00:00Z",
        "tags": [{"slug": "games"}, {"slug": "fifa-world-cup"}, {"slug": "soccer"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is not None
    assert fx.match_id == "fb-wc26-mex-rsa-20260611"
    assert fx.sport == "football"
    assert fx.competition_code == "wc26"
    assert fx.competition_label == "FIFA World Cup 2026"
    assert fx.team_a == "Mexico"
    assert fx.team_b == "South Africa"
    assert fx.kickoff_utc == datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc)
    assert fx.market_outcomes == ("a", "draw", "b")
    assert fx.source_venue == "polymarket"
    assert fx.source_event_slug == "fifwc-mex-rsa-2026-06-11"


def test_parse_ucl_knockout_event() -> None:
    ev = {
        "slug":  "ucl-bay-psg-2026-05-06",
        "title": "FC Bayern München vs. Paris Saint-Germain FC",
        "endDate": "2026-05-06T19:00:00Z",
        "tags": [{"slug": "ucl"}, {"slug": "soccer"}, {"slug": "games"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is not None
    assert fx.match_id == "fb-ucl-bay-psg-20260506"
    assert fx.competition_code == "ucl"
    assert fx.team_a == "FC Bayern München"
    assert fx.team_b == "Paris Saint-Germain FC"


def test_parse_more_markets_suffix_collapses_to_base_match() -> None:
    ev = {
        "slug":  "fr2-fca-clf-2026-01-23-more-markets",
        "title": "FC Annecy vs. Clermont Foot 63 - More Markets",
        "endDate": "2026-01-23T19:00:00Z",
        "tags": [{"slug": "ligue-2"}, {"slug": "soccer"}, {"slug": "games"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is not None
    # Title's " - More Markets" suffix is stripped.
    assert fx.team_a == "FC Annecy"
    assert fx.team_b == "Clermont Foot 63"
    assert fx.match_id.startswith("fb-ligue2-")


def test_unparseable_slug_returns_none(caplog: pytest.LogCaptureFixture) -> None:
    ev = {
        "slug":  "not-a-match-event",
        "title": "Premier League Winner",
        "endDate": "2026-05-31T22:00:00Z",
        "tags": [{"slug": "soccer"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is None


def test_unparseable_title_returns_none() -> None:
    ev = {
        "slug":  "tur-goz-riz-2026-01-19",
        "title": "Tournament season-long market",
        "endDate": "2026-01-19T17:00:00Z",
        "tags": [{"slug": "soccer"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is None


def test_unmapped_competition_passes_through_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ev = {
        "slug":  "xyz-aaa-bbb-2026-07-01",
        "title": "Aaa FC vs. Bbb FC",
        "endDate": "2026-07-01T18:00:00Z",
        "tags": [{"slug": "soccer"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is not None
    assert fx.competition_code == "xyz"
    assert fx.competition_label == "xyz"


# ── Title-based ISO resolution (Polymarket slug codes can collide) ────

def test_polymarket_kor_resolves_to_curacao_when_title_says_curacao() -> None:
    """Polymarket uses `kor` in slugs for both Korea Republic and
    Curaçao (Papiamento "Kòrsou"). When the title gives the team name
    we prefer it for ISO resolution.
    """
    ev = {
        "slug":  "fifwc-ecu-kor-2026-06-20",
        "title": "Ecuador vs. Curaçao",
        "endDate": "2026-06-21T00:00:00Z",
        "tags": [{"slug": "fifa-world-cup"}, {"slug": "soccer"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is not None
    assert fx.team_a == "Ecuador"
    assert fx.team_b == "Curaçao"
    # The match_id must carry Curaçao's ISO3 (cuw), NOT Korea's (kor),
    # because the Elo lookup in features_builder reads from match_id.
    assert "-cuw-" in fx.match_id, f"expected cuw in {fx.match_id}"
    assert "-kor-" not in fx.match_id


def test_polymarket_kor_still_resolves_to_korea_when_title_says_korea() -> None:
    ev = {
        "slug":  "fifwc-rsa-kor-2026-06-24",
        "title": "South Africa vs. Korea Republic",
        "endDate": "2026-06-25T00:00:00Z",
        "tags": [{"slug": "fifa-world-cup"}, {"slug": "soccer"}],
    }
    fx = from_polymarket_event(ev)
    assert fx is not None
    assert fx.team_b == "Korea Republic"
    assert "-kor-" in fx.match_id


# ── Bulk parser de-dupes "more-markets" doppelgängers ─────────────────

def test_fixtures_from_polymarket_dedupes(polymarket_soccer_events: list[dict]) -> None:
    fxs = fixtures_from_polymarket(polymarket_soccer_events)
    ids = [f.match_id for f in fxs]
    assert len(ids) == len(set(ids))


# ── Bulk parser produces only valid match_ids ────────────────────────

def test_all_produced_fixtures_have_valid_match_ids(
    polymarket_soccer_events: list[dict],
) -> None:
    from desk.publish.contract import _MATCH_ID_RE

    fxs = fixtures_from_polymarket(polymarket_soccer_events)
    assert fxs, "expected at least one fixture from the saved response"
    for fx in fxs:
        assert _MATCH_ID_RE.match(fx.match_id), fx.match_id


# ── End-to-end: stub MatchOutputs validate against the published contract ─

def test_stub_match_validates_against_contract(
    polymarket_soccer_events: list[dict],
) -> None:
    fxs = fixtures_from_polymarket(polymarket_soccer_events)
    assert fxs
    now = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)
    pass_verdict = Verdict(state=VerdictState.PASS)
    for fx in fxs:
        m = _build_match(fx, verdict=pass_verdict, now=now)
        reloaded = MatchOutput.model_validate_json(m.model_dump_json())
        assert reloaded.verdict.state == "pass"
        assert reloaded.verdict.market_venue is None
        assert reloaded.match_id == fx.match_id


# ── Team-id helpers ──────────────────────────────────────────────────

def test_normalize_team_national_overrides() -> None:
    assert normalize_team("kr", is_national=True) == "kor"
    assert normalize_team("rsa", is_national=True) == "rsa"
    assert normalize_team("FRA", is_national=True) == "fra"


def test_normalize_team_clubs_pass_through_lowercased() -> None:
    assert normalize_team("BAY", is_national=False) == "bay"
    assert normalize_team("rma", is_national=False) == "rma"


def test_map_competition_known() -> None:
    assert map_competition("fifwc") == ("wc26", "FIFA World Cup 2026")
    assert map_competition("EPL") == ("epl", "Premier League")
    assert map_competition("ucl") == ("ucl", "UEFA Champions League")


def test_map_competition_unknown_returns_none() -> None:
    assert map_competition("notarealthing") is None


def test_is_international_competition() -> None:
    assert is_international_competition("wc26") is True
    assert is_international_competition("euro") is True
    assert is_international_competition("epl") is False
    assert is_international_competition("ucl") is False


# ── Runner: stub-match shape ─────────────────────────────────────────

def test_build_match_has_no_venue_when_fixture_lacks_one() -> None:
    fx = FixtureRef(
        match_id="fb-wc26-fra-mex-20260612",
        sport="football",
        competition_code="wc26",
        competition_label="FIFA World Cup 2026",
        competition_stage=None,
        team_a="France",
        team_b="Mexico",
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        market_outcomes=("a", "draw", "b"),
        venue_city=None,
        venue_stadium=None,
        venue_country=None,
    )
    m = _build_match(
        fx,
        verdict=Verdict(state=VerdictState.PASS),
        now=datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
    )
    assert m.venue is None


def test_build_match_has_venue_when_fixture_has_one() -> None:
    fx = FixtureRef(
        match_id="fb-wc26-fra-mex-20260612",
        sport="football",
        competition_code="wc26",
        competition_label="FIFA World Cup 2026",
        competition_stage="group_d",
        team_a="France",
        team_b="Mexico",
        kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        market_outcomes=("a", "draw", "b"),
        venue_city="Guadalajara",
        venue_stadium="Estadio Akron",
        venue_country="MX",
    )
    m = _build_match(
        fx,
        verdict=Verdict(state=VerdictState.PASS),
        now=datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
    )
    assert m.venue is not None
    assert m.venue.city == "Guadalajara"
    assert m.venue.country == "MX"
