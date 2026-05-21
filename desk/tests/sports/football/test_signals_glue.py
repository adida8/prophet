"""Football → signals-registry tag builder."""

from __future__ import annotations

from datetime import datetime, timezone

from desk.sport import FixtureRef
from desk.sports.football.signals_glue import iso2_for_name, tags_for

_KO = datetime(2026, 6, 12, 19, 0, 0, tzinfo=timezone.utc)


def _fx(*, sport="football", code="wc26", a="France", b="Mexico",
        country="MX") -> FixtureRef:
    return FixtureRef(
        match_id=f"fb-{code}-fra-mex-20260612",
        sport=sport,
        competition_code=code,
        competition_label="Test",
        competition_stage=None,
        team_a=a, team_b=b,
        kickoff_utc=_KO,
        market_outcomes=("a", "draw", "b"),
        venue_city="Guadalajara",
        venue_stadium="Estadio Akron",
        venue_country=country,
    )


def test_iso2_for_known_nation():
    assert iso2_for_name("France") == "fr"
    assert iso2_for_name("Argentina") == "ar"


def test_iso2_for_unknown_returns_none():
    assert iso2_for_name("Atlantis") is None


def test_international_fixture_carries_country_tags_per_team():
    tags = tags_for(_fx(a="France", b="Argentina"))
    assert "country:fr" in tags
    assert "country:ar" in tags
    assert "league:wc26" in tags
    assert "global" in tags
    assert "sport:football" in tags


def test_international_fixture_skips_unknown_country():
    tags = tags_for(_fx(a="France", b="Atlantis"))
    assert "country:fr" in tags
    # 'Atlantis' resolves to no ISO-2 — no country: tag is added for it,
    # rather than producing a garbage country code.
    assert not any(t.startswith("country:atlantis") for t in tags)
    assert not any(t == "country:" for t in tags)


def test_club_fixture_carries_club_tags_and_venue_country():
    tags = tags_for(_fx(
        code="epl", a="Manchester United", b="Liverpool", country="GB",
    ))
    assert "club:manchester-united" in tags
    assert "club:liverpool"          in tags
    assert "country:gb"              in tags
    assert "league:epl"              in tags
    assert not any(t.startswith("country:gb-") for t in tags)


def test_club_slug_handles_diacritics_and_punctuation():
    tags = tags_for(_fx(code="ucl", a="Bayer Leverkusen", b="Bayern München"))
    assert "club:bayer-leverkusen" in tags
    assert "club:bayern-munchen"   in tags  # ü → u via NFD normalise


def test_club_fixture_does_not_add_country_per_team():
    # Club fixtures don't pull `country:` from team names — that path is
    # for national sides. Only the venue country tag fires.
    tags = tags_for(_fx(code="laliga", a="Real Madrid", b="Barcelona", country="ES"))
    assert "club:real-madrid" in tags
    assert "club:barcelona"   in tags
    assert "country:es"       in tags
    assert "country:fr"       not in tags  # no leakage


def test_tags_for_returns_frozenset():
    tags = tags_for(_fx())
    assert isinstance(tags, frozenset)
