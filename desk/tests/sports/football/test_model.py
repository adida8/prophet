"""Football model — frozen feature vectors per spec §4 PR 3 acceptance.

Three positive cases (international, club home, altitude) and two
explicit negative cases (Mexico at MetLife shouldn't fire host bonus;
neutral-venue UCL final shouldn't fire home-ground bonus).

Probability tolerance is ±0.5pp per the spec.
"""

from __future__ import annotations

import math

import pytest

from desk.sports.football.model import (
    ALTITUDE_BONUS_ELO_PER_1000,
    HOME_GROUND_BONUS_ELO,
    HOST_BONUS_ELO,
    FootballFeatures,
    compute,
)

PP = 0.005       # spec tolerance: ±0.5 percentage points


# ── Positive case 1 — international, host + altitude ──────────────────

def test_france_v_mexico_at_azteca_host_and_altitude_for_mexico() -> None:
    """France vs Mexico at Estadio Azteca.

    Mexico picks up host bonus (mex == venue host) and altitude bonus
    (Mexico is altitude-acclimatised; Azteca at 2240m). France is not
    acclimatised — no altitude bonus.
    """
    f = FootballFeatures(
        team_a_name="France",  team_b_name="Mexico",
        team_a_elo=2050.0,     team_b_elo=1830.0,
        is_international=True,
        team_a_iso3="fra",     team_b_iso3="mex",
        venue_host_iso3="mex",
        venue_stadium="Estadio Azteca",
        venue_altitude_m=2240.0,
        team_a_altitude_acclimatised=False,
        team_b_altitude_acclimatised=True,
    )
    out = compute(f)

    assert out.elo_a_adj == pytest.approx(2050.0)
    assert out.elo_b_adj == pytest.approx(
        1830.0 + HOST_BONUS_ELO + ALTITUDE_BONUS_ELO_PER_1000 * (2240 - 1000) / 1000
    )

    # Hand-computed expected probabilities (see model.py for the formula).
    assert out.p_a    == pytest.approx(0.463, abs=PP)
    assert out.p_draw == pytest.approx(0.250, abs=PP)
    assert out.p_b    == pytest.approx(0.287, abs=PP)
    _assert_sums_to_one(out.p_a, out.p_draw, out.p_b)

    labels = [d.label for d in out.drivers]
    assert "host nation" in labels
    assert "altitude (acclimatised)" in labels


# ── Positive case 2 — club home fixture ───────────────────────────────

def test_manchester_united_at_home_to_liverpool_home_bonus_only() -> None:
    """ManU vs Liverpool at Old Trafford. Home bonus for ManU; no host
    bonus (club football); no altitude (38m, below threshold).
    """
    f = FootballFeatures(
        team_a_name="Manchester United", team_b_name="Liverpool",
        team_a_elo=1810.0, team_b_elo=1880.0,
        is_international=False,
        team_a_home_ground="Old Trafford",
        team_b_home_ground="Anfield",
        venue_stadium="Old Trafford",
        venue_altitude_m=38.0,
    )
    out = compute(f)

    assert out.elo_a_adj == pytest.approx(1810.0 + HOME_GROUND_BONUS_ELO)
    assert out.elo_b_adj == pytest.approx(1880.0)

    assert out.p_a    == pytest.approx(0.343, abs=PP)
    assert out.p_draw == pytest.approx(0.294, abs=PP)
    assert out.p_b    == pytest.approx(0.363, abs=PP)
    _assert_sums_to_one(out.p_a, out.p_draw, out.p_b)

    labels = [d.label for d in out.drivers]
    assert "home ground" in labels
    assert "host nation" not in labels      # mutually exclusive with club football
    assert "altitude (acclimatised)" not in labels


# ── Positive case 3 — altitude (and host) ─────────────────────────────

def test_argentina_v_bolivia_at_la_paz_altitude_and_host_for_bolivia() -> None:
    """Argentina vs Bolivia at La Paz (3640m). Bolivia has both host and
    altitude bonuses; Argentina has neither.
    """
    f = FootballFeatures(
        team_a_name="Argentina",  team_b_name="Bolivia",
        team_a_elo=2070.0,        team_b_elo=1700.0,
        is_international=True,
        team_a_iso3="arg",        team_b_iso3="bol",
        venue_host_iso3="bol",
        venue_stadium="Estadio Hernando Siles",
        venue_altitude_m=3640.0,
        team_a_altitude_acclimatised=False,
        team_b_altitude_acclimatised=True,
    )
    out = compute(f)

    expected_bol = 1700.0 + HOST_BONUS_ELO + ALTITUDE_BONUS_ELO_PER_1000 * (3640 - 1000) / 1000
    assert out.elo_b_adj == pytest.approx(expected_bol)

    assert out.p_a    == pytest.approx(0.573, abs=PP)
    assert out.p_draw == pytest.approx(0.202, abs=PP)
    assert out.p_b    == pytest.approx(0.224, abs=PP)
    _assert_sums_to_one(out.p_a, out.p_draw, out.p_b)


# ── Negative case A — host bonus does NOT fire for Mexico at MetLife ──

def test_mexico_at_metlife_host_bonus_does_not_fire_for_mexico() -> None:
    """MetLife is in USA. Mexico is in the WC 2026 host LIST but the
    team's ISO3 doesn't match the venue's country, so the bonus must
    not apply. Spec §4 PR 3 acceptance.
    """
    f = FootballFeatures(
        team_a_name="Argentina", team_b_name="Mexico",
        team_a_elo=2070.0,       team_b_elo=1830.0,
        is_international=True,
        team_a_iso3="arg",       team_b_iso3="mex",
        venue_host_iso3="usa",                    # MetLife is USA
        venue_stadium="MetLife Stadium",
        venue_altitude_m=8.0,
        team_a_altitude_acclimatised=False,
        team_b_altitude_acclimatised=True,
    )
    out = compute(f)

    # Neither team's ISO3 matches the host country — no Elo shift from host.
    assert out.elo_a_adj == pytest.approx(2070.0)
    assert out.elo_b_adj == pytest.approx(1830.0)

    # And no altitude bonus either — MetLife is at sea level.
    labels = [d.label for d in out.drivers]
    assert "host nation" not in labels
    assert "altitude (acclimatised)" not in labels


# ── Negative case B — neutral-venue UCL final, no home-ground bonus ───

def test_ucl_final_at_wembley_no_home_ground_bonus() -> None:
    """UCL final between Bayern and Real Madrid at Wembley. Neither
    team's registered ground matches Wembley, so the home-ground
    bonus must not fire for either side. Spec §4 PR 3 acceptance.
    """
    f = FootballFeatures(
        team_a_name="Bayern München", team_b_name="Real Madrid",
        team_a_elo=1990.0,            team_b_elo=2000.0,
        is_international=False,
        team_a_home_ground="Allianz Arena",
        team_b_home_ground="Santiago Bernabéu",
        venue_stadium="Wembley Stadium",
        venue_altitude_m=12.0,
    )
    out = compute(f)

    assert out.elo_a_adj == pytest.approx(1990.0)
    assert out.elo_b_adj == pytest.approx(2000.0)
    labels = [d.label for d in out.drivers]
    assert "home ground" not in labels
    assert "host nation" not in labels


# ── Sum invariant + value-range invariant ────────────────────────────

@pytest.mark.parametrize("elo_a,elo_b", [
    (1500.0, 1500.0),  (1500.0, 2200.0),  (2200.0, 1500.0),
    (1700.0, 1750.0),  (1900.0, 1500.0),
])
def test_probabilities_always_sum_to_one_and_are_in_range(elo_a, elo_b) -> None:
    f = FootballFeatures(
        team_a_name="A", team_b_name="B",
        team_a_elo=elo_a, team_b_elo=elo_b,
        is_international=False,
    )
    out = compute(f)
    _assert_sums_to_one(out.p_a, out.p_draw, out.p_b)
    for p in (out.p_a, out.p_draw, out.p_b):
        assert 0.0 < p < 1.0


# ── helper ────────────────────────────────────────────────────────────

def _assert_sums_to_one(p_a: float, p_draw: float, p_b: float) -> None:
    assert math.isclose(p_a + p_draw + p_b, 1.0, abs_tol=1e-9)
