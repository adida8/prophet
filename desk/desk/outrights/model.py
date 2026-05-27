"""Monte Carlo tournament simulator for the WC 2026 winner market.

Reuses the existing match model's `_probs_from_elos` primitive verbatim
(same Elo logistic, same draw curve, same constants) so the outright
model and the match model never disagree on the same fixture.

Outputs per team:
  - `p_win` — point estimate from 10k sims
  - `p_win_lower` / `p_win_upper` — 5th / 95th percentile from a
    100-sample × 1k-sim bootstrap with ±50 Elo perturbation per sample
    (matching `desk.sports.football.model.ELO_PERTURBATION_PP` use)

The lower bound is what the verdict step uses for the Pick gate:
    pick when (p_win_lower - market_yes) >= pick_pp.

This is a pre-tournament, frozen-input sim. Live mid-tournament
re-conditioning is out of scope per the spec.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from desk.sports.football.model import _probs_from_elos
from desk.outrights.wc26_data import GROUPS, R32_TIES, elo

SIMS: int = 10_000
BOOTSTRAP_SAMPLES: int = 100
BOOTSTRAP_SIMS: int = 1_000
ELO_PERTURB: float = 50.0
BASE_SEED: int = 42


@dataclass(frozen=True)
class OutrightModelOutput:
    """Per-team probabilities + bootstrap band, plus a couple of
    diagnostics the publisher / explainer want to surface.
    """
    p_win:        dict[str, float]
    p_win_lower:  dict[str, float]
    p_win_upper:  dict[str, float]
    p_groupwin:   dict[str, float]   # diagnostic — P(top of group)
    sims:         int
    seed:         int


def _sample_match(rng: random.Random, elo_a: float, elo_b: float, *, allow_draw: bool) -> int:
    """Return 0 if A wins, 1 if B wins, -1 if draw (group stage only).

    For knockouts, we redistribute the draw mass proportionally to the
    two winning sides (Elo-weighted coin flip — stronger side wins
    extra-time / penalties more often than 50/50, which roughly matches
    historical results).
    """
    p_a, p_d, p_b = _probs_from_elos(elo_a, elo_b)
    if allow_draw:
        r = rng.random()
        if r < p_a:           return 0
        if r < p_a + p_d:     return -1
        return 1

    # Knockout — re-normalise over the two winning sides.
    total = p_a + p_b
    if total <= 0:
        return 0 if rng.random() < 0.5 else 1
    return 0 if rng.random() < (p_a / total) else 1


def _simulate_group(
    rng: random.Random,
    teams: tuple[str, ...],
    elo_lookup: dict[str, float],
) -> list[tuple[str, int, float]]:
    """Run a group's 6 round-robin matches. Returns teams sorted by
    standings — (team, points, elo_tiebreak).

    Points: 3 W / 1 D / 0 L. Tiebreaks: points, then Elo (a stand-in
    for goal-differential; the match model doesn't produce a goals
    output, and "score the favourite higher on GD" is a fair proxy).
    """
    pts: dict[str, int] = {t: 0 for t in teams}
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            a, b = teams[i], teams[j]
            r = _sample_match(rng, elo_lookup[a], elo_lookup[b], allow_draw=True)
            if r == 0:
                pts[a] += 3
            elif r == 1:
                pts[b] += 3
            else:
                pts[a] += 1
                pts[b] += 1
    ranked = sorted(teams, key=lambda t: (-pts[t], -elo_lookup[t]))
    return [(t, pts[t], elo_lookup[t]) for t in ranked]


def _resolve_knockout(
    rng: random.Random,
    slots: dict[str, str],
    elo_lookup: dict[str, float],
) -> str:
    """Run R32 → R16 → QF → SF → Final on the resolved slot map. Returns
    the champion team name.
    """
    # R32
    r16_winners: list[str] = []
    for left, right in R32_TIES:
        a, b = slots[left], slots[right]
        r = _sample_match(rng, elo_lookup[a], elo_lookup[b], allow_draw=False)
        r16_winners.append(a if r == 0 else b)

    # R16 → QF → SF → Final. Standard bracket pairing: tie 0 vs 1, 2 vs 3, ...
    current = r16_winners
    while len(current) > 1:
        nxt: list[str] = []
        for i in range(0, len(current), 2):
            a, b = current[i], current[i + 1]
            r = _sample_match(rng, elo_lookup[a], elo_lookup[b], allow_draw=False)
            nxt.append(a if r == 0 else b)
        current = nxt
    return current[0]


def _simulate_tournament(
    rng: random.Random,
    elo_lookup: dict[str, float],
) -> tuple[str, dict[str, list[int]]]:
    """One full tournament sim. Returns (champion, per-team position
    counters) — the latter feeds the diagnostic `p_groupwin`.
    """
    group_winners: dict[str, str] = {}
    group_runners: dict[str, str] = {}
    thirds_with_pts: list[tuple[str, int, float]] = []

    pos_counters: dict[str, list[int]] = {}

    for letter, teams in GROUPS.items():
        ranked = _simulate_group(rng, teams, elo_lookup)
        group_winners[letter] = ranked[0][0]
        group_runners[letter] = ranked[1][0]
        # Track 3rd-place — (team, pts, elo) — for cross-group ranking
        third = ranked[2]
        thirds_with_pts.append(third)
        # Diagnostic — per-team P(top of group)
        for rank, (t, _, _) in enumerate(ranked):
            pos_counters.setdefault(t, [0, 0, 0, 0])[rank] += 1

    # Best 8 of 12 third-placed teams advance, ranked by points then Elo.
    thirds_with_pts.sort(key=lambda x: (-x[1], -x[2]))
    best_thirds = [t for (t, _, _) in thirds_with_pts[:8]]

    slots: dict[str, str] = {}
    for letter in GROUPS:
        slots[f"{letter}1"] = group_winners[letter]
        slots[f"{letter}2"] = group_runners[letter]
    for i, t in enumerate(best_thirds, start=1):
        slots[f"3RD-{i}"] = t

    champion = _resolve_knockout(rng, slots, elo_lookup)
    return champion, pos_counters


def _point_estimate(
    elo_lookup: dict[str, float],
    sims: int,
    seed: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """Run `sims` tournaments at the given Elo. Returns (p_win, p_groupwin)."""
    rng = random.Random(seed)
    tally: dict[str, int] = {t: 0 for t in elo_lookup}
    group_top_tally: dict[str, int] = {t: 0 for t in elo_lookup}
    for _ in range(sims):
        champ, pos = _simulate_tournament(rng, elo_lookup)
        tally[champ] += 1
        for t, counters in pos.items():
            group_top_tally[t] += counters[0]
    p_win = {t: n / sims for t, n in tally.items()}
    p_groupwin = {t: n / sims for t, n in group_top_tally.items()}
    return p_win, p_groupwin


def _bootstrap_band(
    elo_lookup: dict[str, float],
    samples: int,
    sims_per_sample: int,
    perturb: float,
    seed: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """Bootstrap a 90% CI per team. Each sample perturbs every team's
    Elo by uniform(±perturb) and runs `sims_per_sample` tournaments.
    Returns (p_win_lower, p_win_upper) at the 5th / 95th percentile.
    """
    per_team: dict[str, list[float]] = {t: [] for t in elo_lookup}
    for s in range(samples):
        rng_perturb = random.Random(seed * 1000 + s)
        perturbed = {
            t: e + rng_perturb.uniform(-perturb, perturb)
            for t, e in elo_lookup.items()
        }
        rng_sim = random.Random(seed * 1000 + s + 7)
        tally: dict[str, int] = {t: 0 for t in elo_lookup}
        for _ in range(sims_per_sample):
            champ, _ = _simulate_tournament(rng_sim, perturbed)
            tally[champ] += 1
        for t, n in tally.items():
            per_team[t].append(n / sims_per_sample)

    lower: dict[str, float] = {}
    upper: dict[str, float] = {}
    for t, draws in per_team.items():
        draws.sort()
        # 5th / 95th percentile — with samples=100, that's draws[5] / draws[94].
        # General-case: nearest-rank.
        n = len(draws)
        lo_idx = max(0, int(round(0.05 * (n - 1))))
        hi_idx = min(n - 1, int(round(0.95 * (n - 1))))
        lower[t] = draws[lo_idx]
        upper[t] = draws[hi_idx]
    return lower, upper


def run(
    field: Iterable[str],
    *,
    sims: int = SIMS,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    bootstrap_sims: int = BOOTSTRAP_SIMS,
    perturb: float = ELO_PERTURB,
    seed: int = BASE_SEED,
    elo_overrides: dict[str, float] | None = None,
) -> OutrightModelOutput:
    """Run the point estimate + the bootstrap band. Returns one
    `OutrightModelOutput` covering every team in the field.

    `elo_overrides` lets the caller nudge per-team Elo before the sim —
    used by `run.run_once` to apply bounded hard-signal adjustments
    (injuries / suspensions). Unknown teams in the override dict are
    ignored. The bootstrap's ±perturb is applied on top of the adjusted
    base, so a nudged team still gets its full uncertainty band.
    """
    overrides = elo_overrides or {}
    elo_lookup: dict[str, float] = {t: elo(t) + overrides.get(t, 0.0) for t in field}

    p_win, p_groupwin = _point_estimate(elo_lookup, sims, seed)
    lower, upper = _bootstrap_band(
        elo_lookup,
        samples=bootstrap_samples,
        sims_per_sample=bootstrap_sims,
        perturb=perturb,
        seed=seed,
    )
    return OutrightModelOutput(
        p_win=p_win,
        p_win_lower=lower,
        p_win_upper=upper,
        p_groupwin=p_groupwin,
        sims=sims,
        seed=seed,
    )
