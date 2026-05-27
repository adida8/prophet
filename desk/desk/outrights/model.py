"""Monte Carlo tournament simulator for outright winner markets.

Reuses the existing match model's `_probs_from_elos` primitive verbatim
(same Elo logistic, same draw curve, same constants) so the outright
model and the match model never disagree on the same fixture.

The sim takes a `TournamentStructure` (groups + initial knockout ties +
qualifier strategy) and an Elo lookup, then runs N tournaments to
produce per-team P(win). This generalisation lets the same simulator
score WC 2026 live (12 groups → R32) and WC 2022 in the backtest
(8 groups → R16) without parallel implementations.

Outputs per team:
  - `p_win` — point estimate from 10k sims
  - `p_win_lower` / `p_win_upper` — 5th / 95th percentile from a
    100-sample × 1k-sim bootstrap with ±50 Elo perturbation per sample
    (matching `desk.sports.football.model.ELO_PERTURBATION_PP` use)

The lower bound is what the verdict step uses for the Pick gate:
    pick when (p_win_lower - market_yes) >= pick_pp.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Literal

from desk.outrights.wc26_data import elo
from desk.sports.football.model import _probs_from_elos

SIMS: int = 10_000
BOOTSTRAP_SAMPLES: int = 100
BOOTSTRAP_SIMS: int = 1_000
ELO_PERTURB: float = 50.0
BASE_SEED: int = 42

# ── Knockout-tie resolution parameters ───────────────────────────────
# Three-stage resolution for KO ties: 90 minutes → extra time → pens.
# Tuned to roughly match World Cup KO outcomes 1986–2022:
#
#   ET_SETTLED_SHARE       — of post-90' draws, fraction resolved in
#                            extra time. Historical WC KO ET-resolution
#                            rate is close to 50%; the rest go to pens.
#   PENS_ELO_SENSITIVITY   — per-Elo tilt added to 0.5 for the higher
#                            -Elo side in a shootout. 0.00025 means a
#                            200-Elo gap → ~55/45 for the favourite,
#                            roughly matching empirical pens results.
#   PENS_TILT_CAP          — max deviation from 50/50 in either
#                            direction. Pens are noisy; even Brazil vs
#                            Saudi Arabia in a shootout is closer to a
#                            coin flip than the regulation gap suggests.
ET_SETTLED_SHARE:     float = 0.50
PENS_ELO_SENSITIVITY: float = 0.00025
PENS_TILT_CAP:        float = 0.10

# How qualifying teams pass from the group stage into the knockout
# bracket. WC 2026 takes top-2 of each group + the 8 best third-place
# finishers (12 × 2 + 8 = 32 → R32). WC 2022 took only top-2 (8 × 2
# = 16 → R16). Add a new value here when adding a tournament shape.
QualifierStrategy = Literal["top2_plus_8_thirds", "top2"]


@dataclass(frozen=True)
class TournamentStructure:
    """Generic tournament shape the MC sim runs against.

    `groups`            — group letter → ordered tuple of team names.
    `knockout_seeds`    — initial knockout ties as pairs of slot codes.
                          Each slot code is either `{letter}{1|2}` for
                          a group winner/runner-up, or `3RD-{n}` for an
                          n-th-best third-place team.
    `qualifier_strategy`— how slots are filled from group standings.

    The rest of the bracket (R16 → QF → SF → Final after the initial
    knockout round) is standard single-elimination — `_resolve_knockout`
    just pairs winners 0-vs-1, 2-vs-3, …
    """
    groups:             dict[str, tuple[str, ...]]
    knockout_seeds:     tuple[tuple[str, str], ...]
    qualifier_strategy: QualifierStrategy


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

    Group stage uses the full 3-outcome distribution. Knockouts use a
    separate 3-stage resolution (90' → extra time → pens) — see
    `_sample_knockout`. We keep this wrapper so callers can express
    intent via `allow_draw`.
    """
    if allow_draw:
        p_a, p_d, p_b = _probs_from_elos(elo_a, elo_b)
        r = rng.random()
        if r < p_a:           return 0
        if r < p_a + p_d:     return -1
        return 1
    return _sample_knockout(rng, elo_a, elo_b)


def _sample_knockout(rng: random.Random, elo_a: float, elo_b: float) -> int:
    """Resolve a knockout tie in three stages: 90 minutes → extra time
    → penalty shootout. Returns 0 if A advances, 1 if B advances.

    Why three stages instead of a single re-normalised Elo flip: the
    previous model gave the full Elo advantage to the favourite for
    *every* drawn tie, including the ~half that go to penalties.
    Empirically pens are much closer to 50/50 than the teams' general
    skill gap would predict — a coin flip with a small skill tilt.
    Modelling pens separately corrects this without changing the
    regulation-time behaviour.
    """
    p_a, p_d, p_b = _probs_from_elos(elo_a, elo_b)
    r = rng.random()
    if r < p_a:           return 0          # A wins in 90'
    if r >= p_a + p_d:    return 1          # B wins in 90'

    # Drawn at 90'. Split into ET-settled vs pens.
    if rng.random() < ET_SETTLED_SHARE:
        # Extra time — re-normalise over winning sides (favours the
        # stronger team about as much as regulation does).
        total = p_a + p_b
        if total <= 0:
            return 0 if rng.random() < 0.5 else 1
        return 0 if rng.random() < (p_a / total) else 1

    # Penalty shootout — flat 50/50 with a small Elo tilt, capped.
    elo_diff = elo_a - elo_b
    p_a_pens = 0.5 + PENS_ELO_SENSITIVITY * elo_diff
    p_a_pens = max(0.5 - PENS_TILT_CAP, min(0.5 + PENS_TILT_CAP, p_a_pens))
    return 0 if rng.random() < p_a_pens else 1


def _simulate_group(
    rng: random.Random,
    teams: tuple[str, ...],
    elo_lookup: dict[str, float],
) -> list[tuple[str, int, float]]:
    """Run a group's round-robin matches. Returns teams sorted by
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
    knockout_seeds: tuple[tuple[str, str], ...],
) -> str:
    """Run initial knockout round (per `knockout_seeds`) then standard
    single-elim bracket through to the Final. Returns the champion.
    """
    next_round: list[str] = []
    for left, right in knockout_seeds:
        a, b = slots[left], slots[right]
        r = _sample_match(rng, elo_lookup[a], elo_lookup[b], allow_draw=False)
        next_round.append(a if r == 0 else b)

    current = next_round
    while len(current) > 1:
        nxt: list[str] = []
        for i in range(0, len(current), 2):
            a, b = current[i], current[i + 1]
            r = _sample_match(rng, elo_lookup[a], elo_lookup[b], allow_draw=False)
            nxt.append(a if r == 0 else b)
        current = nxt
    return current[0]


def _assign_constrained_thirds(
    qualifying_thirds: list[tuple[str, str]],
    knockout_seeds: tuple[tuple[str, str], ...],
) -> dict[str, str]:
    """Map `3RD@{groups}` slot codes to specific qualifying third-place
    team names, respecting each slot's group constraint.

    `qualifying_thirds` is `[(team_name, group_letter), ...]` ordered
    best-first (best by group-stage points, Elo tiebreak).

    The real FIFA rule (Annex C) looks up the exact assignment from a
    495-row table keyed by which 8 groups produced the qualifying
    thirds. We approximate with a greedy pass — for each `3RD@` slot
    in bracket order, take the highest-ranked unassigned third whose
    group is in the allowed set. Falls back to the highest-ranked
    unassigned third when no eligible team exists (rare edge case).

    Approximation impact on headline P(win) is sub-pp for top teams;
    encoding the full 495-scenario table is a future refinement.
    """
    assigned: dict[str, str] = {}
    remaining = list(qualifying_thirds)
    for left, right in knockout_seeds:
        for slot in (left, right):
            if not slot.startswith("3RD@"):
                continue
            if slot in assigned:
                continue
            allowed = set(slot[4:])
            pick_idx = None
            for i, (_, group) in enumerate(remaining):
                if group in allowed:
                    pick_idx = i
                    break
            if pick_idx is None and remaining:
                pick_idx = 0  # fallback — no eligible third left
            if pick_idx is None:
                continue  # no thirds at all; let the lookup raise
            team, _ = remaining.pop(pick_idx)
            assigned[slot] = team
    return assigned


def _simulate_tournament(
    rng: random.Random,
    elo_lookup: dict[str, float],
    structure: TournamentStructure,
) -> tuple[str, dict[str, list[int]]]:
    """One full tournament sim. Returns (champion, per-team position
    counters) — the latter feeds the diagnostic `p_groupwin`.
    """
    group_winners: dict[str, str] = {}
    group_runners: dict[str, str] = {}
    # (team, points, elo, group_letter) — group letter needed for the
    # constrained-third slot assignment below.
    thirds_with_pts: list[tuple[str, int, float, str]] = []

    pos_counters: dict[str, list[int]] = {}

    for letter, teams in structure.groups.items():
        ranked = _simulate_group(rng, teams, elo_lookup)
        group_winners[letter] = ranked[0][0]
        group_runners[letter] = ranked[1][0]
        if len(ranked) >= 3:
            t, pts, elo_t = ranked[2]
            thirds_with_pts.append((t, pts, elo_t, letter))
        # Diagnostic — per-team P(top of group). 4-team groups keep
        # a 4-slot counter; smaller groups would shrink it.
        for rank, (t, _, _) in enumerate(ranked):
            pos_counters.setdefault(t, [0] * len(teams))[rank] += 1

    slots: dict[str, str] = {}
    for letter in structure.groups:
        slots[f"{letter}1"] = group_winners[letter]
        slots[f"{letter}2"] = group_runners[letter]

    if structure.qualifier_strategy == "top2_plus_8_thirds":
        # Rank thirds best-first, take the top 8, then assign to
        # constraint-bearing R32 slots via greedy matching.
        thirds_with_pts.sort(key=lambda x: (-x[1], -x[2]))
        best_thirds = [(t, group) for (t, _, _, group) in thirds_with_pts[:8]]
        slots.update(_assign_constrained_thirds(
            best_thirds, structure.knockout_seeds,
        ))
        # Backward-compat: also expose the old "3RD-{n}" slot names
        # so any caller still referencing them keeps working. Today's
        # WC26 bracket is fully on the new "3RD@..." scheme.
        for i, (team, _) in enumerate(best_thirds, start=1):
            slots[f"3RD-{i}"] = team
    # `top2`: no extra slots needed.

    champion = _resolve_knockout(rng, slots, elo_lookup, structure.knockout_seeds)
    return champion, pos_counters


def _point_estimate(
    elo_lookup: dict[str, float],
    structure: TournamentStructure,
    sims: int,
    seed: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """Run `sims` tournaments at the given Elo. Returns (p_win, p_groupwin)."""
    rng = random.Random(seed)
    tally: dict[str, int] = {t: 0 for t in elo_lookup}
    group_top_tally: dict[str, int] = {t: 0 for t in elo_lookup}
    for _ in range(sims):
        champ, pos = _simulate_tournament(rng, elo_lookup, structure)
        tally[champ] += 1
        for t, counters in pos.items():
            group_top_tally[t] += counters[0]
    p_win = {t: n / sims for t, n in tally.items()}
    p_groupwin = {t: n / sims for t, n in group_top_tally.items()}
    return p_win, p_groupwin


def _bootstrap_band(
    elo_lookup: dict[str, float],
    structure: TournamentStructure,
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
            champ, _ = _simulate_tournament(rng_sim, perturbed, structure)
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


def run_sim(
    structure: TournamentStructure,
    elo_lookup: dict[str, float],
    *,
    sims: int = SIMS,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    bootstrap_sims: int = BOOTSTRAP_SIMS,
    perturb: float = ELO_PERTURB,
    seed: int = BASE_SEED,
) -> OutrightModelOutput:
    """Lower-level entry — run the point estimate + bootstrap band on
    an arbitrary tournament shape. `elo_lookup` must cover every team
    referenced by `structure.groups`.

    Used by the backtest harness (which builds its own elo_lookup from
    a frozen historical snapshot). Live runs use the `run()` wrapper.
    """
    p_win, p_groupwin = _point_estimate(elo_lookup, structure, sims, seed)
    lower, upper = _bootstrap_band(
        elo_lookup,
        structure,
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
    """Convenience wrapper for the live WC 2026 winner market.

    Builds an Elo lookup from `wc26_data.elo` (plus optional per-team
    `elo_overrides` for bounded hard-signal nudges), then delegates to
    `run_sim` with the WC26 tournament structure.

    `elo_overrides` lets the caller nudge per-team Elo before the sim —
    used by `outrights.run.run_once` to apply bounded hard-signal
    adjustments (injuries / suspensions). Unknown teams in the override
    dict are ignored. The bootstrap's ±perturb is applied on top of
    the adjusted base, so a nudged team still gets its full band.
    """
    from desk.outrights.wc26_data import wc26_structure
    overrides = elo_overrides or {}
    elo_lookup: dict[str, float] = {t: elo(t) + overrides.get(t, 0.0) for t in field}
    return run_sim(
        wc26_structure(),
        elo_lookup,
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        perturb=perturb,
        seed=seed,
    )
