"""Compute a bounded per-team Elo penalty from injury rows.

Per `THE_DESK_OPTIMIZATION_SPEC.md` §4.B.3:

    importance = (
        POSITION_WEIGHT[player.position]      # GK 1.5, CB/DM 1.2, FW 1.0, depth 0.4
        × min(player.recent_minutes_share, 1.0)  # 0–1 fraction
        × ROLE_BUMP[player.role]              # captain 1.2, starter 1.0, rotation 0.6
    )
    elo_penalty = INJURY_BASE_PENALTY * importance  # e.g. 60 Elo × importance

We're not yet wiring `recent_minutes_share` / `role` — the source audit
will tell us if api-football reliably surfaces those (paid-tier
gated). For v1 we ship the position-only path:

    penalty(player) = INJURY_BASE_PENALTY * POSITION_WEIGHT[position]

with a flat 0.5 minutes-share assumption (we'll know real shares
once the audit clears). Hard-capped at INJURY_MAX_TOTAL_ELO_PER_TEAM
so a flu outbreak can't shift a national side by 200 Elo.
"""

from __future__ import annotations

from desk.data.api_football.cache import InjuryRow
from desk.data.api_football.injuries import (
    DEFAULT_POSITION_WEIGHT, POSITION_WEIGHT,
)

# Per-player penalty magnitude before importance multipliers.
INJURY_BASE_PENALTY: float = 60.0

# Default minutes-share assumption when api-football doesn't expose
# the field. 0.5 is a "rotation-edge starter" assumption — neither
# pretends every absent player is a first-choice nor that everyone is
# squad depth.
DEFAULT_MINUTES_SHARE: float = 0.5

# Per-team cap. Multiple injuries cumulate but never below this floor
# of -X Elo. Spec §4.B.3: "no team penalised more than ~150 Elo total".
INJURY_MAX_TOTAL_ELO_PER_TEAM: float = 150.0

# Only types api-football surfaces that represent actual unavailability.
# "Missing Fixture" + "Suspended" are the unambiguous ones; "Questionable"
# is excluded (we don't penalise on uncertainty).
COUNTED_INJURY_TYPES: set[str] = {"Missing Fixture", "Suspended"}


def compute_injury_penalty(rows: list[InjuryRow]) -> tuple[float, int]:
    """Return (penalty_magnitude, n_players_counted).

    Penalty is positive (a magnitude). Caller subtracts it from Elo:
    `elo_adj = elo - penalty`.
    """
    if not rows:
        return (0.0, 0)
    total = 0.0
    n_counted = 0
    for r in rows:
        if r.type not in COUNTED_INJURY_TYPES:
            continue
        pos_weight = POSITION_WEIGHT.get(
            r.position or "", DEFAULT_POSITION_WEIGHT,
        )
        importance = pos_weight * DEFAULT_MINUTES_SHARE
        total += INJURY_BASE_PENALTY * importance
        n_counted += 1
    return (min(total, INJURY_MAX_TOTAL_ELO_PER_TEAM), n_counted)
