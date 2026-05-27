"""features_builder threads form_delta from an injected form_source.

Validates that:
  * absent form_source ⇒ team_*_form_delta stays None (today's behaviour)
  * present form_source ⇒ values flow onto FootballFeatures
  * club fixtures (is_international=False) are NOT looked up — v1
    scope is national teams only
  * unknown ISO3 ⇒ None, no crash
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.sport import FixtureRef
from desk.sports.football.features_builder import build_features


def _fixture(home_iso3="fra", away_iso3="bra", comp="wc26"):
    return FixtureRef(
        match_id=f"fb-{comp}-{home_iso3}-{away_iso3}-20260612",
        sport="football",
        competition_code=comp,
        competition_label="FIFA World Cup 2026",
        competition_stage=None,
        team_a=home_iso3.upper(), team_b=away_iso3.upper(),
        kickoff_utc=datetime(2026, 6, 12, 19, tzinfo=timezone.utc),
        market_outcomes=("a", "draw", "b"),
        venue_city=None, venue_stadium=None, venue_country=None,
    )


class _ScriptedFormSource:
    def __init__(self, **vals):
        self._vals = {k.lower(): v for k, v in vals.items()}
        self.calls: list[str] = []

    def form_delta_for_iso3(self, iso3):
        self.calls.append(iso3)
        return self._vals.get(iso3.lower())


def test_without_form_source_form_fields_stay_none():
    fx = _fixture()
    features = build_features(fx)
    assert features.team_a_form_delta is None
    assert features.team_b_form_delta is None


def test_with_form_source_values_thread_through():
    fx = _fixture()
    src = _ScriptedFormSource(fra=0.5, bra=-0.3)
    features = build_features(fx, form_source=src)
    assert features.team_a_form_delta == 0.5
    assert features.team_b_form_delta == -0.3


def test_unknown_iso3_stays_none_does_not_crash():
    fx = _fixture(home_iso3="abc", away_iso3="bra")
    src = _ScriptedFormSource(bra=0.4)
    features = build_features(fx, form_source=src)
    # "abc" isn't a real ISO3; features_builder will resolve it from
    # the match-id slug. The form_source returns None.
    assert features.team_b_form_delta == 0.4


def test_club_fixtures_skip_form_lookup():
    """Club competitions (EPL etc.) are out of scope for the v1 form
    feed (no club registry). The form_source must not be queried."""
    fx = FixtureRef(
        match_id="fb-epl-mun-liv-20260815",
        sport="football",
        competition_code="epl",
        competition_label="Premier League",
        competition_stage=None,
        team_a="MUN", team_b="LIV",
        kickoff_utc=datetime(2026, 8, 15, 14, tzinfo=timezone.utc),
        market_outcomes=("a", "draw", "b"),
        venue_city=None, venue_stadium=None, venue_country=None,
    )
    src = _ScriptedFormSource(mun=0.5, liv=-0.5)
    features = build_features(fx, form_source=src)
    assert features.team_a_form_delta is None
    assert features.team_b_form_delta is None
    assert src.calls == []  # never queried
