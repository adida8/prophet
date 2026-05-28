"""Phase 1b live Elo bridge for the outrights sim.

Per-team Elo deltas (live − outright seed) are returned as additional
`elo_overrides` for `outrights.model.run`. Merged with the existing
hard-signal overrides at the orchestrator level.

Byte-identical-when-cache-absent guarantee: when `EloRuntime.national_elo_source(iso3)`
returns anything other than the live-source label ("eloratings"), we
skip the override for that team. So a fresh deploy with no live cache
runs the outright sim with exactly the seed values it did before
Phase 1b landed.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from desk.data.elo.runtime import EloRuntime
from desk.outrights.wc26_data import elo as outright_seed_elo
from desk.sports.football.teams import iso3_for_name

_LOG = logging.getLogger(__name__)

LIVE_SOURCE_ID: str = "eloratings"


def live_elo_overrides_for_field(
    field: Iterable[str],
    *,
    runtime: EloRuntime,
) -> dict[str, float]:
    """Build per-team Elo deltas applied on top of the outright seed.

    For each team in `field`:
      1. Resolve display name → ISO3 (skip if unknown to the registry).
      2. Ask the runtime for the source label of this team's Elo;
         only proceed when it's `eloratings` (real live ingest, not
         the seed-fallback layer underneath the runtime).
      3. `delta = live − outright_seed` — when delta is ~0 (live and
         seed agree), we omit it to keep the override dict tight.

    Returns a `{team_display_name: delta_elo}` dict suitable for
    merging with hard-signal overrides via dict-sum.
    """
    deltas: dict[str, float] = {}
    for team in field:
        iso3 = iso3_for_name(team)
        if not iso3:
            continue
        try:
            source_id = runtime.national_elo_source(iso3)
        except Exception as e:                              # noqa: BLE001
            _LOG.warning("live-elo source lookup failed for %s: %s", team, e)
            continue
        if source_id != LIVE_SOURCE_ID:
            # Cache absent for this iso3 OR runtime falling through to
            # the per-match seed (a different table). Either way, we
            # leave the outright seed in charge.
            continue
        try:
            live = runtime.national_elo(iso3)
        except Exception as e:                              # noqa: BLE001
            _LOG.warning("live-elo value lookup failed for %s: %s", team, e)
            continue
        delta = live - outright_seed_elo(team)
        if abs(delta) < 0.5:
            # Live value within rounding distance of the seed — not
            # worth the override clutter.
            continue
        deltas[team] = delta
    return deltas


def merge_elo_overrides(*sources: dict[str, float]) -> dict[str, float]:
    """Sum overrides across multiple sources (live Elo + hard signals).

    Keys are team display names; values are the cumulative Elo delta
    to apply on top of the seed. A team appearing in two sources has
    its deltas summed — hard-signal nudges stack on top of the
    live-vs-seed correction.
    """
    out: dict[str, float] = {}
    for src in sources:
        for team, delta in src.items():
            out[team] = out.get(team, 0.0) + delta
    return out
