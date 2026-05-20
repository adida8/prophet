"""Sport registry.

v1 ships football only. v2's admin backend introspects this registry to
let the operator enable additional sports without code changes.
"""

from __future__ import annotations

from desk.sport import Sport
from desk.sports.football.sport import FootballSport

SPORT_REGISTRY: dict[str, Sport] = {
    "football": FootballSport(),
}


def active_sports() -> list[Sport]:
    """Sports currently enabled.

    Stub for v2's per-sport `enabled` flag. v1 returns everything in
    the registry.
    """
    return list(SPORT_REGISTRY.values())
