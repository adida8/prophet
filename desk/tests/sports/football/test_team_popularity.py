"""Tests for team_popularity — tier lookup, fallbacks, multipliers, name variants."""

from __future__ import annotations

import math

import pytest

from desk.sports.football.data.team_popularity import (
    match_popularity_multiplier,
    tier_for_team,
)


# --- tier_for_team -----------------------------------------------------------


@pytest.mark.parametrize("name", ["Argentina", "Brazil", "France", "Spain", "England"])
def test_tier_for_team_tier1(name: str) -> None:
    assert tier_for_team(name) == 1


@pytest.mark.parametrize("name", ["USA", "Mexico", "Croatia", "Côte d'Ivoire"])
def test_tier_for_team_tier2(name: str) -> None:
    assert tier_for_team(name) == 2


@pytest.mark.parametrize("name", ["Haiti", "Iran", "Curaçao", "Saudi Arabia",
                                  "El Salvador", "Trinidad and Tobago"])
def test_tier_for_team_tier4(name: str) -> None:
    assert tier_for_team(name) == 4


@pytest.mark.parametrize("name", ["Canada", "Norway", "Atlantis", "", "   "])
def test_tier_for_team_default_is_tier3(name: str) -> None:
    """Anything not explicitly listed — including unknown names and hosts that
    aren't in the popularity dict (Canada) — falls to Tier 3."""
    assert tier_for_team(name) == 3


# --- name-variant round-tripping through iso3_for_name -----------------------


def test_name_variants_resolve_to_same_tier() -> None:
    """Display variants must hit the same tier via iso3 normalisation."""
    assert tier_for_team("Côte d'Ivoire") == tier_for_team("Ivory Coast") == 2
    assert tier_for_team("Korea Republic") == tier_for_team("South Korea") == 2
    assert tier_for_team("Curaçao") == tier_for_team("Curacao") == 4
    assert tier_for_team("USA") == tier_for_team("United States") == 2
    assert tier_for_team("Cape Verde") == tier_for_team("Cabo Verde") == 4


# --- match_popularity_multiplier ---------------------------------------------


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9)


def test_max_of_two_rule_picks_higher_tier() -> None:
    """Combined multiplier is driven by the more popular team."""
    # Curaçao (T4 = 0.4×) vs Côte d'Ivoire (T2 = 2.0×) → 2.0×, no blockbuster.
    assert _close(match_popularity_multiplier("Curaçao", "Côte d'Ivoire"), 2.0)


def test_blockbuster_bonus_when_both_tier_1_or_2() -> None:
    # Argentina (T1) × Austria (T2) → max(4, 2) × 1.25 = 5.0.
    assert _close(match_popularity_multiplier("Argentina", "Austria"), 5.0)
    # Argentina × Brazil (both T1) → max(4, 4) × 1.25 = 5.0.
    assert _close(match_popularity_multiplier("Argentina", "Brazil"), 5.0)


def test_no_blockbuster_when_tier3_or_4_involved() -> None:
    # Argentina (T1) × Haiti (T4) → max(4, 0.4) = 4.0, no 1.25 bonus.
    assert _close(match_popularity_multiplier("Argentina", "Haiti"), 4.0)
    # Spain (T1) × Canada (T3 by default) — would be blockbuster if Canada were T2,
    # but Canada is unmapped → Tier 3 → no blockbuster. Host bonus still fires.
    # max(4, 1) = 4 × 1.5 host = 6.0.
    assert _close(match_popularity_multiplier("Spain", "Canada"), 6.0)


def test_host_bonus_fires_for_each_host() -> None:
    # All three WC26 hosts (USA, Canada, Mexico) trigger the ×1.5 bonus when
    # either side. Argentina (T1) baseline = 4.0.
    for host in ("USA", "Canada", "Mexico"):
        got = match_popularity_multiplier(host, "Argentina")
        # USA + Mexico are Tier 2 so blockbuster also fires (×1.25).
        # Canada is Tier 3 so only host bonus fires.
        expected = 4.0 * 1.5 * (1.25 if host in {"USA", "Mexico"} else 1.0)
        assert _close(got, expected), f"{host} v Argentina expected {expected}, got {got}"


def test_blockbuster_and_host_stack_for_usa_argentina() -> None:
    # USA (T2) × Argentina (T1) → max(2, 4) × 1.25 blockbuster × 1.5 host = 7.5.
    assert _close(match_popularity_multiplier("USA", "Argentina"), 7.5)
    # Order-independent.
    assert _close(match_popularity_multiplier("Argentina", "USA"), 7.5)


def test_two_niche_teams_get_smallest_multiplier() -> None:
    # Haiti × Iran (both T4) → max(0.4, 0.4) = 0.4, no bonuses.
    assert _close(match_popularity_multiplier("Haiti", "Iran"), 0.4)


def test_unknown_partner_falls_to_tier3_no_bonus() -> None:
    # Argentina (T1) × "Atlantis" (unknown → T3) → max(4, 1) = 4.0, no bonuses.
    assert _close(match_popularity_multiplier("Argentina", "Atlantis"), 4.0)
