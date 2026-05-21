"""Hard-track signal selection — sport-agnostic.

Given a fixture's tag set, walk the signals cache and return the
`(Signal, Source)` pairs that route to the model track. Three gates
apply, in this order:

  1. Source covers the fixture (tag intersection via `sources_for`).
  2. The source's trust gate admits the signal to the hard track
     (`Signal.track(source) == "hard"`).
  3. The signal is recent enough that the underlying fact is plausibly
     still true (a 30-day-old "injury" is probably stale).

Late-binding (only-within-N-days-of-kickoff) is **not** applied here.
That's the sport's call — it's about how close to kickoff we'll let
soft information move the number, not whether a signal exists. See
`desk/sports/football/hard_signals.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from desk.signals.cache import SignalsCache
from desk.signals.models import Signal, Source
from desk.signals.registry import Registry
from desk.signals.resolve import sources_for

_LOG = logging.getLogger(__name__)

# Hard signals expire faster than editorial colour. A confirmed-XI is
# meaningless after kickoff; an injury report a fortnight old usually
# means the player has recovered. Tight default; sport adjusts.
DEFAULT_MAX_AGE = timedelta(days=7)


def hard_signals_for(
    *,
    fixture_tags: Iterable[str],
    cache: SignalsCache,
    registry: Registry,
    now: datetime | None = None,
    max_age: timedelta | None = DEFAULT_MAX_AGE,
) -> list[tuple[Signal, Source]]:
    """Return hard-track `(signal, source)` pairs covering the fixture.

    Ordered most-recent-first so adjusters can prefer fresher reports
    when the same player appears in multiple signals.
    """
    now = now or datetime.now(tz=timezone.utc)
    sources = sources_for(fixture_tags, registry)
    if not sources:
        return []
    by_id = {s.id: s for s in sources}

    cutoff = now - max_age if max_age else None
    rows: list[tuple[Signal, Source]] = []
    for signal in cache.list_signals():
        source = by_id.get(signal.source_id)
        if source is None:
            continue
        if signal.track(source) != "hard":
            continue
        if cutoff and signal.published_at and signal.published_at < cutoff:
            continue
        rows.append((signal, source))

    # Newest first; tie-break by source reliability so a stale tier-1
    # signal still loses to a fresh tier-1 one.
    rows.sort(
        key=lambda row: (
            row[0].published_at or datetime.min.replace(tzinfo=timezone.utc),
            row[1].reliability,
        ),
        reverse=True,
    )
    return rows
