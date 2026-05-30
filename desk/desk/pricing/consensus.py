"""Consensus `fair_p` blend across venues.

Given per-venue `fair_p` for a single side, return ONE consensus
probability used in the "market consensus" narrative line. NOT used
for edge — see `desk/pricing/cost.py` for the price the verdict uses.

Weighting follows THE_DESK_NONUS_SPORTSBOOK_SCOPING.md §2:

    Pinnacle is the sharp anchor and carries the highest weight.
    Other consumer books contribute less.
    Exchanges sit alongside Pinnacle as sharp price discovery.

Weight is taken from a caller-supplied table keyed on venue id. A
missing venue gets weight 1.0 — i.e. counts equally with the others.
Pinnacle's higher weight is the only thing the launch table tunes.
"""

from __future__ import annotations

from typing import Mapping, Sequence


# Default sharp weights for the launch venue set. Tuned modestly: a
# Pinnacle quote counts 3× a William Hill quote in the consensus blend
# (sharps, low margin), with the exchange weighted same as Pinnacle on
# the assumption that traded back odds are also sharp.
DEFAULT_SHARP_WEIGHTS: Mapping[str, float] = {
    "pinnacle":         3.0,
    "betfair_ex_uk":    3.0,
    "betfair_ex_eu":    3.0,
    "polymarket":       2.0,
    "williamhill":      1.0,
    "skybet":           1.0,
}


def consensus_fair(
    fair_by_venue: Sequence[tuple[str, float]],
    *,
    weights: Mapping[str, float] | None = None,
) -> float:
    """Weighted blend of per-venue `fair_p` for one side.

    `fair_by_venue` is `(venue_id, fair_p)` pairs. Empty input is a
    caller bug — there's no consensus to compute from no opinions.
    """
    if not fair_by_venue:
        raise ValueError("consensus_fair: no venues supplied.")
    w = weights or DEFAULT_SHARP_WEIGHTS

    numerator   = 0.0
    denominator = 0.0
    for venue, fair_p in fair_by_venue:
        if not (0.0 <= fair_p <= 1.0):
            raise ValueError(
                f"consensus_fair: fair_p for {venue!r} out of [0,1] "
                f"(got {fair_p})."
            )
        weight = float(w.get(venue, 1.0))
        if weight < 0.0:
            raise ValueError(f"weights[{venue!r}] must be ≥ 0 (got {weight}).")
        numerator   += fair_p * weight
        denominator += weight
    if denominator == 0.0:
        raise ValueError(
            "consensus_fair: all venue weights are zero — cannot blend."
        )
    return numerator / denominator
