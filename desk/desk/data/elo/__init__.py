"""Live Elo ingest — data-layer spec Phase 1b.

Layers a live source on top of the static `elo_seed.py`. Per the spec:
the seed is the floor; live ingest overrides it where present. Source
provenance is preserved so the verdict step can still gate Pick
decisions on whether the prior was real or stub-fallback.

Two providers in v1:
  * `national/` — World Football Elo Ratings via eloratings.net's
    public TSV export (parser-hardened per spec §1b acceptance).
  * `club/`     — api.clubelo.com (per-club CSV; the spec's tier-1
    source).

Both cache to a shared `elo.db` sqlite file. Reads on the hot path go
through `EloRuntime`, which checks the cache first and falls back to
the static seed (with source label "stub" for seed-fallback,
"clubelo"/"eloratings" for live).
"""

from desk.data.elo.cache import EloCache, EloRow
from desk.data.elo.runtime import EloRuntime, default_cache_path

__all__ = ["EloCache", "EloRow", "EloRuntime", "default_cache_path"]
