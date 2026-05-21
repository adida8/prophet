"""Fixture → source resolver.

Stays sport-agnostic by taking an opaque set of tags rather than a
`FixtureRef`. The sport package builds the tag set:

    # in desk/sports/football/signals_glue.py (later PR)
    def tags_for(fixture: FixtureRef) -> frozenset[str]:
        tags = {"global", "sport:football", f"league:{fixture.competition_code}"}
        if is_international(fixture.competition_code):
            tags |= {f"country:{iso2_a}", f"country:{iso2_b}"}
        else:
            tags |= {f"club:{slug_a}", f"club:{slug_b}"}
        return frozenset(tags)
"""

from __future__ import annotations

from collections.abc import Iterable

from desk.signals.models import Source
from desk.signals.registry import Registry


def sources_for(tags: Iterable[str], registry: Registry) -> list[Source]:
    """Return enabled sources whose `coverage_tags` intersect `tags`,
    sorted by reliability descending (with `id` as a stable tiebreaker
    so the order is deterministic across runs)."""
    want = frozenset(tags)
    matches = [s for s in registry.enabled() if s.coverage_tags & want]
    matches.sort(key=lambda s: (-s.reliability, s.id))
    return matches
