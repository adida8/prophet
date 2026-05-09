"""Football model — Elo prior + host / home-ground / altitude adjustments.

The maths is deliberately small. The engine's edge comes from clean data
plumbing and the late-binding feature ladder, not from a clever model;
PR 3 is just a competent baseline so the verdict step has something to
compare market prices against.

Pipeline:
    1. Look up Elo for both sides (national or club, by competition).
    2. Apply at most one venue-bonus per team:
       - Host bonus (international tournaments only) when the team's
         ISO3 matches the venue country and that country is in the
         competition's host list.
       - Home-ground bonus (clubs only) when the team's registered
         ground matches the venue stadium.
       (Mutually exclusive — host fires for international, home for
       clubs.)
    3. Apply altitude bonus to whichever side is altitude-acclimatised
       when the venue is above 1000m.
    4. Convert adjusted Elo difference → expected score via the
       standard 400-pt logistic.
    5. Distribute the 1.0 probability mass across (a, draw, b) using a
       simple draw-share function that decays with |Elo diff|.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from desk.sports.football.drivers import Driver

# ── Tunable constants (locked at PR 3 defaults; threshold spec §10) ─────

HOST_BONUS_ELO:              float = 75.0
HOME_GROUND_BONUS_ELO:       float = 60.0
ALTITUDE_BONUS_ELO_PER_1000: float = 50.0
ALTITUDE_THRESHOLD_M:        float = 1000.0

# Draw-share function: peaks at DRAW_PEAK when teams are equal, decays
# linearly with |Elo diff| down to DRAW_FLOOR.
DRAW_PEAK:  float = 0.30
DRAW_FLOOR: float = 0.10
DRAW_DECAY_PER_ELO: float = 0.0006   # 100 Elo diff → −0.06 draw share


# ── Inputs / outputs ────────────────────────────────────────────────────

@dataclass(frozen=True)
class FootballFeatures:
    """Concrete feature vector the football model reads.

    `is_international` selects which bonus rule applies (host vs
    home-ground), so the two branches are mutually exclusive by
    construction. `_iso3` fields are required for international fixtures
    and ignored for clubs; `_home_ground` and `_altitude_acclimatised`
    are the inverse.
    """
    team_a_name: str
    team_b_name: str
    team_a_elo: float
    team_b_elo: float

    is_international: bool

    # International-only
    team_a_iso3: Optional[str] = None
    team_b_iso3: Optional[str] = None
    venue_host_iso3: Optional[str] = None        # winner of host_iso3_for_competition()

    # Club-only
    team_a_home_ground: Optional[str] = None
    team_b_home_ground: Optional[str] = None

    # Both
    venue_stadium:    Optional[str] = None
    venue_altitude_m: Optional[float] = None
    team_a_altitude_acclimatised: bool = False
    team_b_altitude_acclimatised: bool = False

    # PR 4.5 — provenance flag for the verdict-step's stub-Elo gate.
    # "wiki" / "clubelo" = real source; "stub" = v1 fixed-default
    # fallback. The verdict step forces Pass when either side is "stub"
    # so we don't issue confident Picks against a 1500-vs-1500 prior.
    # TODO(v1.1): once ClubElo / FBref ingestion ships, club fixtures
    # stop emitting "stub" and the verdict-step gate becomes inert.
    team_a_elo_source: str = "wiki"
    team_b_elo_source: str = "wiki"


@dataclass(frozen=True)
class ModelOutput:
    p_a:     float    # probability team_a wins
    p_draw:  float
    p_b:     float
    elo_a_adj: float
    elo_b_adj: float
    drivers: tuple[Driver, ...] = ()
    # Mirror of the input flags so callers don't have to re-thread them.
    team_a_elo_source: str = "wiki"
    team_b_elo_source: str = "wiki"
    # Confidence band — 5th/95th percentile across an Elo-jackknife grid
    # (Phase A.3 of the trustability brief). Forces the engine to be
    # honest about what it doesn't know: if the Elo prior is shaky, the
    # band widens and the verdict step's lower-bound check rejects the
    # Pick.
    p_a_lower:    float = 0.0
    p_a_upper:    float = 1.0
    p_draw_lower: float = 0.0
    p_draw_upper: float = 1.0
    p_b_lower:    float = 0.0
    p_b_upper:    float = 1.0


# ── Public entry point ──────────────────────────────────────────────────

def compute(features: FootballFeatures) -> ModelOutput:
    elo_a, elo_b = features.team_a_elo, features.team_b_elo
    drivers: list[Driver] = []

    # ── Venue bonus ────────────────────────────────────────────────
    if features.is_international:
        host = features.venue_host_iso3
        if host:
            if features.team_a_iso3 and features.team_a_iso3.lower() == host.lower():
                elo_a += HOST_BONUS_ELO
                drivers.append(Driver("host nation", HOST_BONUS_ELO, "a"))
            if features.team_b_iso3 and features.team_b_iso3.lower() == host.lower():
                elo_b += HOST_BONUS_ELO
                drivers.append(Driver("host nation", HOST_BONUS_ELO, "b"))
    else:
        stadium = (features.venue_stadium or "").strip().lower()
        if stadium:
            if features.team_a_home_ground and features.team_a_home_ground.strip().lower() == stadium:
                elo_a += HOME_GROUND_BONUS_ELO
                drivers.append(Driver("home ground", HOME_GROUND_BONUS_ELO, "a"))
            if features.team_b_home_ground and features.team_b_home_ground.strip().lower() == stadium:
                elo_b += HOME_GROUND_BONUS_ELO
                drivers.append(Driver("home ground", HOME_GROUND_BONUS_ELO, "b"))

    # ── Altitude bonus ─────────────────────────────────────────────
    alt = features.venue_altitude_m or 0.0
    if alt > ALTITUDE_THRESHOLD_M:
        bonus = ALTITUDE_BONUS_ELO_PER_1000 * (alt - ALTITUDE_THRESHOLD_M) / 1000.0
        if features.team_a_altitude_acclimatised:
            elo_a += bonus
            drivers.append(Driver("altitude (acclimatised)", bonus, "a"))
        if features.team_b_altitude_acclimatised:
            elo_b += bonus
            drivers.append(Driver("altitude (acclimatised)", bonus, "b"))

    # ── Elo → probabilities ────────────────────────────────────────
    elo_diff = elo_a - elo_b
    # Standard 400-pt logistic; expected score for team_a.
    expected_a = 1.0 / (1.0 + math.pow(10.0, -elo_diff / 400.0))

    p_draw = max(DRAW_FLOOR, DRAW_PEAK - DRAW_DECAY_PER_ELO * abs(elo_diff))
    win_share = 1.0 - p_draw
    p_a = expected_a * win_share
    p_b = (1.0 - expected_a) * win_share

    # Float drift safety net — renormalise so the trio sums to exactly 1.
    s = p_a + p_draw + p_b
    p_a, p_draw, p_b = p_a / s, p_draw / s, p_b / s

    # ── Confidence band (Phase A.3) ────────────────────────────────
    # Jackknife the Elo prior across ±50 of each side's input. We use
    # the *base* Elo (pre-adjustment) so the perturbation doesn't
    # double-count host / home / altitude bonuses, then re-apply them.
    p_a_lo, p_a_hi, pd_lo, pd_hi, p_b_lo, p_b_hi = _confidence_band(
        features=features, base_elo_a=features.team_a_elo, base_elo_b=features.team_b_elo,
        elo_a_adj=elo_a, elo_b_adj=elo_b,
    )

    return ModelOutput(
        p_a=p_a, p_draw=p_draw, p_b=p_b,
        elo_a_adj=elo_a, elo_b_adj=elo_b,
        drivers=tuple(drivers),
        team_a_elo_source=features.team_a_elo_source,
        team_b_elo_source=features.team_b_elo_source,
        p_a_lower=p_a_lo, p_a_upper=p_a_hi,
        p_draw_lower=pd_lo, p_draw_upper=pd_hi,
        p_b_lower=p_b_lo, p_b_upper=p_b_hi,
    )


# ── Confidence-band helper ─────────────────────────────────────────────

ELO_JACKKNIFE_GRID = (-50.0, -25.0, 0.0, 25.0, 50.0)


def _probs_from_elos(elo_a: float, elo_b: float) -> tuple[float, float, float]:
    """Pure-maths probability triplet for adjusted Elo, no bonuses."""
    diff = elo_a - elo_b
    expected_a = 1.0 / (1.0 + math.pow(10.0, -diff / 400.0))
    p_draw = max(DRAW_FLOOR, DRAW_PEAK - DRAW_DECAY_PER_ELO * abs(diff))
    win_share = 1.0 - p_draw
    p_a = expected_a * win_share
    p_b = (1.0 - expected_a) * win_share
    s = p_a + p_draw + p_b
    return (p_a / s, p_draw / s, p_b / s)


def _confidence_band(
    *,
    features: "FootballFeatures",
    base_elo_a: float,
    base_elo_b: float,
    elo_a_adj: float,
    elo_b_adj: float,
) -> tuple[float, float, float, float, float, float]:
    """Return (p_a_lo, p_a_hi, pd_lo, pd_hi, p_b_lo, p_b_hi).

    Method: perturb each side's *base* Elo across ±50 in 5 steps; for
    every (delta_a, delta_b) pair on the grid (25 combinations), compute
    the model's probabilities; take min/max per side.

    Perturbing the *base* Elo (not the adjusted) preserves the host /
    home / altitude bonuses — those reflect deterministic facts about
    the venue, not uncertainty in the team prior.
    """
    bonus_a = elo_a_adj - base_elo_a
    bonus_b = elo_b_adj - base_elo_b

    p_a_samples: list[float] = []
    p_d_samples: list[float] = []
    p_b_samples: list[float] = []
    for da in ELO_JACKKNIFE_GRID:
        for db in ELO_JACKKNIFE_GRID:
            pa, pd, pb = _probs_from_elos(
                base_elo_a + da + bonus_a,
                base_elo_b + db + bonus_b,
            )
            p_a_samples.append(pa)
            p_d_samples.append(pd)
            p_b_samples.append(pb)

    return (
        min(p_a_samples), max(p_a_samples),
        min(p_d_samples), max(p_d_samples),
        min(p_b_samples), max(p_b_samples),
    )
