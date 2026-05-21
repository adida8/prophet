"""Editorial track — turn cached `Signal`s into `Citation`s on a fixture.

The editorial track is the "show the local press" half of news-signals:
every claim that appears in the published blurb traces to a real,
fetchable line from a real outlet. We never paraphrase off-the-record;
the verbatim sentence rides in `Citation.quote`.

Two guardrails enforced here (the third — translation honesty — is
enforced at extraction time and just rides through):

  * Citation-is-load-bearing: only signals whose `quote` is non-empty
    (already validated at extract time to be a substring of the
    article) become Citations.

  * Plural-attribution requires consensus: "the local press said…"
    is only safe when ≥2 *independent* outlets (different parent_org)
    carry the same claim. We expose `find_consensus()` so the
    explainer can pick between "Olé reported…" (single source) and
    "the Argentine press said…" (consensus).

This module is sport-agnostic. The football glue that turns a
`FixtureRef` into the tag set lives in `desk/sports/football/`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from desk.publish.contract import Citation
from desk.signals.cache import SignalsCache
from desk.signals.models import Signal, Source
from desk.signals.registry import Registry
from desk.signals.resolve import sources_for

_LOG = logging.getLogger(__name__)

# Default editorial recency window. Older signals don't enrich a
# fixture's blurb — the "what's been said this week" framing only
# survives if the underlying coverage is recent.
DEFAULT_MAX_AGE = timedelta(days=10)
DEFAULT_MAX_CITATIONS = 6


@dataclass(frozen=True)
class ConsensusGroup:
    """Editorial signals about one team carried by ≥N independent
    parent_orgs in the recency window. Used by the explainer to decide
    between "Olé reported…" and "the Argentine press said…".

    We group by team rather than by exact claim because two outlets
    will phrase the same incident differently ("Mbappé out — calf"
    vs "Mbappé out, calf strain"). Treating their messy phrasings as
    one "the press is talking about this player" cluster is the
    framing the explainer actually needs."""

    team:    str
    signals: tuple[Signal, ...]
    sources: tuple[Source, ...]

    @property
    def independent_org_count(self) -> int:
        return len({_org_for(s) for s in self.sources})


def build_citations(
    *,
    fixture_tags: Iterable[str],
    cache: SignalsCache,
    registry: Registry,
    teams: Iterable[str] | None = None,
    now: datetime | None = None,
    max_age: timedelta | None = DEFAULT_MAX_AGE,
    max_citations: int = DEFAULT_MAX_CITATIONS,
) -> list[Citation]:
    """Build a fixture's editorial citation list.

    Pipeline:
      1. Resolve which registered sources cover this fixture via tag
         intersection.
      2. Pull each source's cached signals.
      3. Keep only signals that route to the editorial track
         (`Signal.track(source) == 'editorial'`) — the source gate
         dominates here, so an injury from a biased outlet stays
         editorial. Hard-track signals do NOT appear in citations;
         they belong on model features (PR F).
      4. If `teams` is provided, drop signals whose `team` field doesn't
         case-insensitively match one of the fixture's teams. Without
         this filter, every fixture would pull the same global pool —
         "Foden out of England squad" showing up on a Brazil v Haiti
         card. Pass `teams=None` to disable.
      5. Filter by recency.
      6. Dedupe by (canonical url + quote).
      7. Sort by source reliability desc, then `published_at` desc.
      8. Cap at `max_citations` so a single fixture doesn't trail a
         twenty-link bibliography.
    """
    now = now or datetime.now(tz=timezone.utc)
    candidates = _candidates(fixture_tags, cache, registry)

    team_set: set[str] | None = None
    if teams is not None:
        team_set = {t.strip().lower() for t in teams if t and t.strip()}

    cutoff = now - max_age if max_age else None
    rows: list[tuple[Signal, Source]] = []
    for signal, source in candidates:
        if signal.track(source) != "editorial":
            continue
        if team_set is not None:
            if signal.team.strip().lower() not in team_set:
                continue
        if cutoff and signal.published_at and signal.published_at < cutoff:
            continue
        rows.append((signal, source))

    # Stable order: most-trustworthy outlet first, then newest.
    rows.sort(key=_citation_sort_key, reverse=True)

    seen: set[tuple[str, str]] = set()
    out: list[Citation] = []
    for signal, source in rows:
        key = (signal.url, signal.quote)
        if key in seen:
            continue
        seen.add(key)
        out.append(_to_citation(signal, source))
        if len(out) >= max_citations:
            break
    return out


def find_consensus(
    *,
    fixture_tags: Iterable[str],
    cache: SignalsCache,
    registry: Registry,
    min_independent_orgs: int = 2,
    max_age: timedelta | None = DEFAULT_MAX_AGE,
    now: datetime | None = None,
) -> list[ConsensusGroup]:
    """Return claim groups with ≥ `min_independent_orgs` distinct
    parent_orgs behind them. Independence is keyed by `Source.parent_org`,
    falling back to `Source.id` when an outlet declares no parent."""
    now = now or datetime.now(tz=timezone.utc)
    cutoff = now - max_age if max_age else None
    by_team: dict[str, list[tuple[Signal, Source]]] = {}
    for signal, source in _candidates(fixture_tags, cache, registry):
        if signal.track(source) != "editorial":
            continue
        if cutoff and signal.published_at and signal.published_at < cutoff:
            continue
        team_key = signal.team.strip().lower()
        by_team.setdefault(team_key, []).append((signal, source))

    out: list[ConsensusGroup] = []
    for team, pairs in by_team.items():
        sources = tuple(s for _, s in pairs)
        orgs = {_org_for(s) for s in sources}
        if len(orgs) >= min_independent_orgs:
            out.append(ConsensusGroup(
                team=team,
                signals=tuple(sig for sig, _ in pairs),
                sources=sources,
            ))
    # Largest consensus first — useful for the explainer's top pick.
    out.sort(key=lambda g: (g.independent_org_count, len(g.signals)), reverse=True)
    return out


# ── internals ─────────────────────────────────────────────────────────

def _candidates(
    fixture_tags: Iterable[str],
    cache: SignalsCache,
    registry: Registry,
) -> Iterable[tuple[Signal, Source]]:
    sources = sources_for(fixture_tags, registry)
    if not sources:
        return
    by_id = {s.id: s for s in sources}
    for signal in cache.list_signals():
        source = by_id.get(signal.source_id)
        if source is None:
            continue
        yield signal, source


def _citation_sort_key(row: tuple[Signal, Source]) -> tuple:
    signal, source = row
    pub = signal.published_at or datetime.min.replace(tzinfo=timezone.utc)
    return (source.reliability, pub)


def _to_citation(signal: Signal, source: Source) -> Citation:
    return Citation(
        outlet=source.name,
        url=signal.url,
        quote=signal.quote,
        quote_original=signal.quote_original,
        quote_lang=signal.quote_lang,
        published_at=signal.published_at,
    )


def _org_for(source: Source) -> str:
    return source.parent_org or source.id
