"""Coverage report — pre-publish team + fixture floors."""

from __future__ import annotations

import pytest

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.coverage import (
    FIXTURE_COVERAGE_FLOOR_PCT, TEAM_COVERAGE_FLOOR_PCT,
    build_coverage_report,
)
from desk.data.api_football.wc26_registry import WC26_NATIONAL_REGISTRY


@pytest.fixture
def cache(tmp_path):
    return APIFootballCache(tmp_path / "api_football.db")


def _populate_form(cache, iso3s):
    for i, iso3 in enumerate(iso3s):
        cache.upsert_form_delta(iso3, form_delta=0.0, sample_size=10)


def test_empty_cache_zero_team_coverage(cache):
    report = build_coverage_report(
        cache=cache,
        competition_code="wc26",
        priced_fixture_iso3_pairs=[],
    )
    assert report.teams_total == len(WC26_NATIONAL_REGISTRY)
    assert report.teams_covered == 0
    assert report.team_coverage_pct == 0.0
    assert not report.teams_floor_cleared


def test_full_team_coverage_clears_floor(cache):
    _populate_form(cache, WC26_NATIONAL_REGISTRY.keys())
    report = build_coverage_report(
        cache=cache, competition_code="wc26",
        priced_fixture_iso3_pairs=[],
    )
    assert report.teams_covered == report.teams_total
    assert report.team_coverage_pct == 100.0
    assert report.teams_floor_cleared


def test_team_floor_threshold_is_95pct(cache):
    """≥95% must clear the floor; just below must not."""
    n = len(WC26_NATIONAL_REGISTRY)
    n_above = int(n * 0.96)  # safely above 95%
    n_below = int(n * 0.93)  # safely below 95%

    iso_list = list(WC26_NATIONAL_REGISTRY.keys())
    _populate_form(cache, iso_list[:n_above])
    above_report = build_coverage_report(
        cache=cache, competition_code="wc26",
        priced_fixture_iso3_pairs=[],
    )
    assert above_report.teams_floor_cleared
    assert above_report.team_coverage_pct >= TEAM_COVERAGE_FLOOR_PCT

    # Reset by re-creating cache
    cache._conn.execute("DELETE FROM form_deltas")
    _populate_form(cache, iso_list[:n_below])
    below_report = build_coverage_report(
        cache=cache, competition_code="wc26",
        priced_fixture_iso3_pairs=[],
    )
    assert not below_report.teams_floor_cleared


def test_fixture_coverage_requires_both_sides(cache):
    """A fixture only counts as covered when BOTH teams have form_delta."""
    _populate_form(cache, ["fra"])  # only one side covered
    pairs = [("fb-wc26-fra-bra-20260612", "fra", "bra")]
    report = build_coverage_report(
        cache=cache, competition_code="wc26",
        priced_fixture_iso3_pairs=pairs,
    )
    assert report.fixtures_total == 1
    assert report.fixtures_covered == 0
    assert "fb-wc26-fra-bra-20260612" in report.fixtures_uncovered


def test_non_international_fixtures_excluded(cache):
    """A club fixture has no WC26-registry ISO3 codes, so it's
    excluded from the denominator — not "uncovered"."""
    pairs = [("fb-epl-mun-liv-20260815", "", "")]
    report = build_coverage_report(
        cache=cache, competition_code="epl",
        priced_fixture_iso3_pairs=pairs,
    )
    assert report.fixtures_total == 0


def test_both_floors_cleared_property(cache):
    _populate_form(cache, WC26_NATIONAL_REGISTRY.keys())
    pairs = [("fb-wc26-fra-bra-20260612", "fra", "bra")]
    report = build_coverage_report(
        cache=cache, competition_code="wc26",
        priced_fixture_iso3_pairs=pairs,
    )
    assert report.both_floors_cleared
    assert report.fixture_coverage_pct == 100.0
    assert report.fixture_coverage_pct >= FIXTURE_COVERAGE_FLOOR_PCT


def test_headline_string_format(cache):
    _populate_form(cache, WC26_NATIONAL_REGISTRY.keys())
    pairs = [("fb-wc26-fra-bra-20260612", "fra", "bra")]
    report = build_coverage_report(
        cache=cache, competition_code="wc26",
        priced_fixture_iso3_pairs=pairs,
    )
    headline = report.headline()
    assert "wc26" in headline
    assert "teams" in headline
    assert "fixtures" in headline
