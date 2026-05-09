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
    6. Phase A.1 — bootstrap a 90% confidence band around the triplet
       by perturbing the Elo prior, host bonus, and altitude bonus
       across the spec's uncertainty ranges. Forces the verdict step
       to be honest about what it doesn't know.
"""

from __future__ import annotations

import hashlib
import math
import random
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


# ── Phase A.1 bootstrap parameters (THE_DESK_OPTIMIZATION_SPEC §3) ─────
#
# Uniform half-widths applied independently per sample. Home-ground
# bonus uses the same ±15 as host: they're the international / club
# analogues of the same venue uplift.
#
# ELO_PERTURBATION raised from 20 → 50 vs the spec's first cut: the
# v1 Elo prior IS uncertain at this magnitude — a tournament can shift
# a national side ±30, transfer windows shift clubs ±30, recent form
# swings ±20–50. ±20 was visibly too tight on the WC 2022 backtest
# (77% Pick rate at the lower-bound gate). ±50 reflects what the prior
# actually doesn't know and brings selection back inside the 5–20%
# editorial target without changing the verdict ladder.
BOOTSTRAP_N:                  int   = 100
ELO_PERTURBATION:             float = 50.0
HOST_BONUS_PERTURBATION:      float = 15.0
HOME_BONUS_PERTURBATION:      float = 15.0
ALTITUDE_BONUS_PERTURBATION:  float = 10.0


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
    # 90% confidence band (5th/95th percentile across a 100-sample
    # bootstrap of Elo ±20, host bonus ±15, altitude bonus ±10).
    # Phase A.2 of the optimization spec uses the lower bound as the
    # honest-uncertainty gate on Pick verdicts.
    p_a_lower:    float = 0.0
    p_a_upper:    float = 1.0
    p_draw_lower: float = 0.0
    p_draw_upper: float = 1.0
    p_b_lower:    float = 0.0
    p_b_upper:    float = 1.0


# ── Public entry point ──────────────────────────────────────────────────

def compute(features: FootballFeatures) -> ModelOutput:
    drivers: list[Driver] = []
    elo_a, elo_b = _adjusted_elos(
        features,
        base_elo_a=features.team_a_elo,
        base_elo_b=features.team_b_elo,
        record_drivers=drivers,
    )

    p_a, p_draw, p_b = _probs_from_elos(elo_a, elo_b)

    # ── Confidence band (Phase A.1) ────────────────────────────────
    p_a_lo, p_a_hi, pd_lo, pd_hi, p_b_lo, p_b_hi = _confidence_band(features)

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


# ── Bonus + probability helpers ────────────────────────────────────────

def _adjusted_elos(
    features: FootballFeatures,
    *,
    base_elo_a: float,
    base_elo_b: float,
    host_bonus: float = HOST_BONUS_ELO,
    home_bonus: float = HOME_GROUND_BONUS_ELO,
    altitude_per_1000: float = ALTITUDE_BONUS_ELO_PER_1000,
    record_drivers: list[Driver] | None = None,
) -> tuple[float, float]:
    """Apply venue + altitude bonuses on top of base Elo.

    Pulled out so the bootstrap can re-run the bonus logic with
    perturbed constants. `record_drivers` is the live-pipeline output;
    the bootstrap path passes None and ignores driver attribution.
    """
    elo_a, elo_b = base_elo_a, base_elo_b

    if features.is_international:
        host = features.venue_host_iso3
        if host:
            if features.team_a_iso3 and features.team_a_iso3.lower() == host.lower():
                elo_a += host_bonus
                if record_drivers is not None:
                    record_drivers.append(Driver("host nation", host_bonus, "a"))
            if features.team_b_iso3 and features.team_b_iso3.lower() == host.lower():
                elo_b += host_bonus
                if record_drivers is not None:
                    record_drivers.append(Driver("host nation", host_bonus, "b"))
    else:
        stadium = (features.venue_stadium or "").strip().lower()
        if stadium:
            if features.team_a_home_ground and features.team_a_home_ground.strip().lower() == stadium:
                elo_a += home_bonus
                if record_drivers is not None:
                    record_drivers.append(Driver("home ground", home_bonus, "a"))
            if features.team_b_home_ground and features.team_b_home_ground.strip().lower() == stadium:
                elo_b += home_bonus
                if record_drivers is not None:
                    record_drivers.append(Driver("home ground", home_bonus, "b"))

    alt = features.venue_altitude_m or 0.0
    if alt > ALTITUDE_THRESHOLD_M:
        bonus = altitude_per_1000 * (alt - ALTITUDE_THRESHOLD_M) / 1000.0
        if features.team_a_altitude_acclimatised:
            elo_a += bonus
            if record_drivers is not None:
                record_drivers.append(Driver("altitude (acclimatised)", bonus, "a"))
        if features.team_b_altitude_acclimatised:
            elo_b += bonus
            if record_drivers is not None:
                record_drivers.append(Driver("altitude (acclimatised)", bonus, "b"))

    return elo_a, elo_b


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


# ── Confidence-band bootstrap (Phase A.1) ──────────────────────────────

def _seed_for_features(features: FootballFeatures) -> int:
    """Deterministic per-match seed so the band is reproducible.

    Two runs of the same fixture yield identical bounds, which keeps
    the verdict step deterministic and the backtest's xlsx output
    diffable across regenerations.
    """
    key = "|".join(str(x) for x in (
        features.team_a_name, features.team_b_name,
        features.team_a_elo, features.team_b_elo,
        features.team_a_iso3, features.team_b_iso3,
        features.venue_host_iso3, features.venue_stadium,
        features.venue_altitude_m,
        features.team_a_home_ground, features.team_b_home_ground,
        features.team_a_altitude_acclimatised, features.team_b_altitude_acclimatised,
        features.is_international,
    ))
    digest = hashlib.md5(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile. `q` in [0, 100]."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    idx = (q / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def _confidence_band(
    features: FootballFeatures,
) -> tuple[float, float, float, float, float, float]:
    """Return (p_a_lo, p_a_hi, pd_lo, pd_hi, p_b_lo, p_b_hi).

    Bootstrap the model BOOTSTRAP_N times. Each sample independently
    perturbs:

      - Elo prior on each side by uniform(±ELO_PERTURBATION)
      - host bonus magnitude by uniform(±HOST_BONUS_PERTURBATION)
        (also home-ground bonus by ±HOME_BONUS_PERTURBATION; the two
        are international/club analogues of the same venue uplift)
      - altitude-bonus rate by uniform(±ALTITUDE_BONUS_PERTURBATION)

    Lower / upper bounds are the 5th / 95th percentile of the resulting
    p_a, p_draw, p_b distributions. Per-match seeding keeps the band
    reproducible across runs.
    """
    rng = random.Random(_seed_for_features(features))

    p_a_samples: list[float] = []
    p_d_samples: list[float] = []
    p_b_samples: list[float] = []

    for _ in range(BOOTSTRAP_N):
        d_elo_a = rng.uniform(-ELO_PERTURBATION, ELO_PERTURBATION)
        d_elo_b = rng.uniform(-ELO_PERTURBATION, ELO_PERTURBATION)
        host_b  = HOST_BONUS_ELO + rng.uniform(
            -HOST_BONUS_PERTURBATION, HOST_BONUS_PERTURBATION
        )
        home_b  = HOME_GROUND_BONUS_ELO + rng.uniform(
            -HOME_BONUS_PERTURBATION, HOME_BONUS_PERTURBATION
        )
        alt_b   = ALTITUDE_BONUS_ELO_PER_1000 + rng.uniform(
            -ALTITUDE_BONUS_PERTURBATION, ALTITUDE_BONUS_PERTURBATION
        )

        elo_a_adj, elo_b_adj = _adjusted_elos(
            features,
            base_elo_a=features.team_a_elo + d_elo_a,
            base_elo_b=features.team_b_elo + d_elo_b,
            host_bonus=host_b,
            home_bonus=home_b,
            altitude_per_1000=alt_b,
        )
        pa, pd, pb = _probs_from_elos(elo_a_adj, elo_b_adj)
        p_a_samples.append(pa)
        p_d_samples.append(pd)
        p_b_samples.append(pb)

    p_a_samples.sort()
    p_d_samples.sort()
    p_b_samples.sort()

    return (
        _percentile(p_a_samples, 5.0),  _percentile(p_a_samples, 95.0),
        _percentile(p_d_samples, 5.0),  _percentile(p_d_samples, 95.0),
        _percentile(p_b_samples, 5.0),  _percentile(p_b_samples, 95.0),
    )
