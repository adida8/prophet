"""Read-only hot path over the Elo cache, with seed fallback.

The features-builder threads this onto every fixture. When the cache
has a live value, the live value wins (label "eloratings" or
"clubelo"). When it doesn't, we fall back to the static seed (label
"wiki" or "stub"), so the verdict step's stub-Elo gate (PR 4.5)
continues to behave as before.

This is the single point where Phase 1b changes live verdicts.
"""

from __future__ import annotations

import os
from pathlib import Path

from desk import config
from desk.data.elo.cache import EloCache
from desk.sports.football.data.elo_seed import (
    club_elo as seed_club_elo, club_elo_source as seed_club_elo_source,
    national_elo as seed_national_elo,
    national_elo_source as seed_national_elo_source,
)


def default_cache_path() -> Path:
    """Path to the live-Elo cache. `DESK_ELO_DB_PATH` env override
    exists so Railway can mount a persistent volume."""
    raw = os.environ.get("DESK_ELO_DB_PATH")
    if raw:
        return Path(raw)
    return Path(config.ROOT) / "data" / "elo.db"


class EloRuntime:
    """Live-Elo-then-seed lookup. Lazy file open."""

    def __init__(self, cache_path: Path | str | None = None):
        self._cache_path = Path(cache_path) if cache_path else default_cache_path()
        self._cache: EloCache | None = None

    def _ensure(self) -> EloCache | None:
        if self._cache is not None:
            return self._cache
        if not self._cache_path.exists():
            return None
        self._cache = EloCache(self._cache_path)
        return self._cache

    # ── national ──────────────────────────────────────────────────

    def national_elo(self, iso3: str) -> float:
        """Live value if present, otherwise the seed value."""
        cache = self._ensure()
        if cache is not None:
            row = cache.get_national(iso3)
            if row is not None:
                return row.elo
        return seed_national_elo(iso3)

    def national_elo_source(self, iso3: str) -> str:
        """Live → source_id (e.g. "eloratings"); seed-hit → "wiki";
        seed-miss → "stub". Preserves the PR 4.5 stub-Elo gate
        semantics — Picks are still suppressed on stub priors."""
        cache = self._ensure()
        if cache is not None:
            row = cache.get_national(iso3)
            if row is not None:
                return row.source_id
        return seed_national_elo_source(iso3)

    # ── club ──────────────────────────────────────────────────────

    def club_elo(self, club_id: str) -> float:
        cache = self._ensure()
        if cache is not None:
            row = cache.get_club(club_id)
            if row is not None:
                return row.elo
        return seed_club_elo(club_id)

    def club_elo_source(self, club_id: str) -> str:
        cache = self._ensure()
        if cache is not None:
            row = cache.get_club(club_id)
            if row is not None:
                return row.source_id
        return seed_club_elo_source(club_id)

    # ── lifecycle ─────────────────────────────────────────────────

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()
            self._cache = None

    def __enter__(self) -> "EloRuntime":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
