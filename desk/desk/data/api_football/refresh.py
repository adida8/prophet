"""High-level orchestrator — walks the WC26 registry and refreshes
team_id resolution + fixture history + form_delta for every national
side. Designed to be called from the refresh loop (daily / 6h).

Step-by-step per ISO3:
  1. If we don't have an api-football team_id, hit `/teams?search=`.
  2. Hit `/fixtures?team={team_id}&last=10` to refresh recent results.
  3. Recompute form_delta from the cached fixtures.

Failure isolation:
  * Any single team's failure (auth, transient, quota, malformed
    response) is logged and skipped — the next team still runs.
  * Auth failure on the *first* team aborts the run (no point burning
    the quota probing dead keys); caller sees a single clean error.

Cost shape: one /teams call per team on first run (one-off; ~70
calls), one /fixtures call per team per run. Daily run with 70 teams
= 70 calls/day — well under api-football Pro's 7,500/day cap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballClient, APIFootballError
from desk.data.api_football.fixtures import fetch_recent_fixtures
from desk.data.api_football.form import compute_form_delta
from desk.data.api_football.sanity import (
    REASON_OK,
    check_entity_match,
    check_fixture,
    check_form_delta_range,
)
from desk.data.api_football.teams import resolve_team_id
from desk.data.api_football.wc26_registry import WC26_NATIONAL_REGISTRY

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefreshOutcome:
    iso3:        str
    status:      str    # "ok", "resolved_then_ok", "no_team_id", "fetch_failed",
                        # "no_form_data", "error"
    team_id:     int | None = None
    sample_size: int = 0
    form_delta:  float | None = None
    error:       str | None = None


async def refresh_one(
    iso3: str,
    *,
    client: APIFootballClient,
    cache:  APIFootballCache,
) -> RefreshOutcome:
    iso3 = iso3.lower()
    # 1. Resolve / fetch team_id from cache.
    resolution = await resolve_team_id(iso3, client=client, cache=cache)
    if resolution.team_id is None:
        return RefreshOutcome(iso3, "no_team_id", error=resolution.error)
    team_id = resolution.team_id

    # 2. Pull last-10 fixtures.
    try:
        fixtures = await fetch_recent_fixtures(team_id, client=client, n=10)
    except APIFootballError as e:
        return RefreshOutcome(
            iso3, "fetch_failed", team_id=team_id, error=f"{e.kind}: {e}",
        )

    # Sanity-gate every fixture before it reaches the cache. Spec §3.7:
    # fresh + cited + wrong is still wrong. Failures are logged loudly
    # — they're a source-quality signal, not a routine miss.
    sanitised: list = []
    n_dropped = 0
    for f in fixtures:
        r = check_fixture(f)
        if r != REASON_OK:
            _LOG.warning("sanity-drop fixture %d (team %d, %s): %s",
                         f.fixture_id, team_id, iso3, r)
            n_dropped += 1
            continue
        r = check_entity_match(f, team_id)
        if r != REASON_OK:
            _LOG.warning("sanity-drop fixture %d (team %d, %s): %s",
                         f.fixture_id, team_id, iso3, r)
            n_dropped += 1
            continue
        sanitised.append(f)

    cache.upsert_fixture_results(sanitised)
    cache.mark_fetch(f"/fixtures?team={team_id}&last=10", "ok")

    # 3. Compute form_delta from the cache (not the just-fetched list)
    # so we include any historical fixtures persisted by prior runs.
    cached = cache.recent_fixtures(team_id, limit=10)
    result = compute_form_delta(cached)
    if result is None:
        return RefreshOutcome(
            iso3, "no_form_data", team_id=team_id,
            error=f"only {len(cached)} FT fixtures cached "
                  "(need MIN_SAMPLE_SIZE)",
        )
    form_delta, sample_size = result

    # Range-sanity on the derived value. Out-of-range = math bug or
    # corrupt fixture set; absent the value rather than feed garbage.
    range_check = check_form_delta_range(form_delta)
    if range_check != REASON_OK:
        _LOG.warning("sanity-drop form_delta=%.3f for %s (%d): %s",
                     form_delta, iso3, team_id, range_check)
        return RefreshOutcome(
            iso3, "no_form_data", team_id=team_id,
            error=f"failed_sanity: form_delta={form_delta:.3f} outside plausible range",
        )

    now = datetime.now(tz=timezone.utc)
    cache.upsert_form_delta(
        iso3, form_delta, sample_size,
        computed_at=now,
        source_endpoint=f"/fixtures?team={team_id}&last=10",
        source_fetched_at=now,
    )

    status = "resolved_then_ok" if resolution.status == "resolved" else "ok"
    return RefreshOutcome(
        iso3, status, team_id=team_id,
        sample_size=sample_size, form_delta=form_delta,
    )


async def refresh_all(
    *,
    client: APIFootballClient,
    cache:  APIFootballCache,
    iso3s:  list[str] | None = None,
) -> list[RefreshOutcome]:
    """Refresh form_delta for every team in the WC26 registry.

    Pass `iso3s` to restrict to a subset (smoke-testing). On the first
    auth failure, aborts — no point spending the daily quota probing
    a dead key. Other error kinds skip the team and continue.
    """
    targets = iso3s or list(WC26_NATIONAL_REGISTRY)
    outcomes: list[RefreshOutcome] = []
    for iso3 in targets:
        try:
            outcome = await refresh_one(iso3, client=client, cache=cache)
        except APIFootballError as e:
            outcome = RefreshOutcome(iso3, "error", error=f"{e.kind}: {e}")
        outcomes.append(outcome)
        # Auth failures usually arrive as an error string inside a
        # ResolutionOutcome (refresh_one's resolver swallows the raise
        # to surface a structured outcome). Abort on the first auth
        # signal — no point burning the daily quota probing a dead key.
        if outcome.error and outcome.error.lower().startswith("auth:"):
            _LOG.error(
                "api-football auth failed on %s — aborting refresh: %s",
                iso3, outcome.error,
            )
            return outcomes
    return outcomes
