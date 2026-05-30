"""Hot-path runtime — reads only, no api-football calls.

Used by `features_builder.build_features` to look up form_delta values
for each fixture's two teams. Designed to be opened once at the start
of `run_once` and reused across all matches, then closed.

The fetcher (`desk.data.api_football.refresh`) is what *writes* into
the underlying cache. Hot-path is read-only by contract.
"""

from __future__ import annotations

import os
from pathlib import Path

from desk import config
from desk.data.api_football.cache import APIFootballCache, InjuryRow, LineupRow


def default_cache_path() -> Path:
    """Path to the api-football cache. `DESK_API_FOOTBALL_DB_PATH` env
    override exists so Railway can mount a persistent volume — without
    it, every redeploy drops the cache and the first post-deploy tick
    publishes fixtures without form_delta."""
    raw = os.environ.get("DESK_API_FOOTBALL_DB_PATH")
    if raw:
        return Path(raw)
    return Path(config.ROOT) / "data" / "api_football.db"


class APIFootballRuntime:
    """Read-only handle over `APIFootballCache`.

    Opens the underlying sqlite file lazily so importing this module is
    cheap; the file may not exist yet on a fresh deploy.
    """

    def __init__(self, cache_path: Path | str | None = None):
        self._cache_path = Path(cache_path) if cache_path else default_cache_path()
        self._cache: APIFootballCache | None = None

    def _ensure(self) -> APIFootballCache | None:
        if self._cache is not None:
            return self._cache
        if not self._cache_path.exists():
            return None
        self._cache = APIFootballCache(self._cache_path)
        return self._cache

    def form_delta_for_iso3(self, iso3: str) -> float | None:
        """Look up the cached form_delta for a national side. Returns
        None when the cache file doesn't exist OR the team has no
        cached form_delta yet — both are "absent" per spec §3.6 and
        the model hook produces zero contribution."""
        if not iso3:
            return None
        cache = self._ensure()
        if cache is None:
            return None
        row = cache.form_delta_for_iso3(iso3)
        return row.form_delta if row else None

    def injury_penalty_for_iso3(self, iso3: str) -> float | None:
        """Cached injury Elo penalty for a national side.

        Returns a POSITIVE magnitude (Elo); the model hook subtracts
        it. None = not computed yet → zero contribution per spec §3.6.
        """
        if not iso3:
            return None
        cache = self._ensure()
        if cache is None:
            return None
        row = cache.injury_penalty_for_iso3(iso3)
        return row.elo_penalty if row else None

    def injuries_for_iso3(self, iso3: str) -> list[InjuryRow]:
        """Cached api-football InjuryRow list for a national side.

        Returns [] when the cache file doesn't exist, when the team
        hasn't been resolved to an api-football team_id yet, or when
        no injuries have been fetched. Never raises — the blurb path
        treats absent data as "no info" not "fail loud".
        """
        if not iso3:
            return []
        cache = self._ensure()
        if cache is None:
            return []
        team_id = cache.team_id_for_iso3(iso3)
        if team_id is None:
            return []
        return cache.injuries_for_team(team_id)

    def lineup_for_match_iso3(
        self, *, match_id: str, iso3: str,
    ) -> LineupRow | None:
        """Cached lineup row for `(match_id, iso3)`.

        Resolves the fixture_resolution row for `match_id` to get the
        api-football fixture_id, then reads the lineup keyed on
        (fixture_id, team_id). Returns None when:
          * the cache file doesn't exist,
          * fixture_resolution hasn't been populated for this match,
          * the team isn't resolved to a team_id,
          * no lineup row has been written for this (fixture, team).

        The hot-path builder treats None as `state="unknown"`.
        """
        if not match_id or not iso3:
            return None
        cache = self._ensure()
        if cache is None:
            return None
        team_id = cache.team_id_for_iso3(iso3)
        if team_id is None:
            return None
        resolution = cache.fixture_resolution_for(match_id)
        if resolution is None:
            # Fall back to most-recent lineup for this team — useful when
            # the T-90m loop has written lineups but the fixture_resolution
            # was written under a different match_id (e.g. slug drift).
            return cache.lineup_for_team(api_football_team_id=team_id)
        return cache.lineup_for(
            fixture_id=resolution.api_football_fixture_id,
            api_football_team_id=team_id,
        )

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()
            self._cache = None

    def __enter__(self) -> "APIFootballRuntime":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
