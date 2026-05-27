"""Outright → signals-registry tag builder.

Mirrors `desk/sports/football/signals_glue.py::tags_for` for the
per-team-binary outright market. The tag set is the *union* over the
participating field:

  * `global`, `sport:football`, `league:wc26`
  * `country:{iso2}` per nation in the field (via `iso2_for_name`)

The resolver returns every source plausibly covering any team. The
per-team binding — *which* signal attaches to *which* team — happens
inside `desk/outrights/hard_signals.py::apply_hard_signals` against
each signal's own `team` field.
"""

from __future__ import annotations

from collections.abc import Iterable

from desk.sports.football.signals_glue import iso2_for_name


def tags_for_outright(field: Iterable[str]) -> frozenset[str]:
    tags: set[str] = {"global", "sport:football", "league:wc26"}
    for name in field:
        iso2 = iso2_for_name(name)
        if iso2:
            tags.add(f"country:{iso2}")
    return frozenset(tags)
