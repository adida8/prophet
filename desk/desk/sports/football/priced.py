"""Football fixture+price ingest — pairs each `FixtureRef` with a
multi-venue `MarketSnapshot` covering every venue that prices the match.

Polymarket is the fixture-of-record source: only fixtures it discovers
appear here. Kalshi (and later DK/FD) only contribute extra `VenuePrice`
entries to fixtures Polymarket already identified.

The merge is keyed on `(kickoff_date, frozenset({iso3_a, iso3_b}))` —
parsed straight off `match_id`. No fuzzy team-name matching.

PR 6's scheduler will poll this every 60s for the verdict cadence.
"""

from __future__ import annotations

import logging
from datetime import date

from desk import config
from desk.ingest.kalshi_prices import FixtureKey, fetch_wc26_snapshots
from desk.ingest.polymarket import PolymarketSoccerEventsSource
from desk.ingest.polymarket_prices import prices_from_polymarket_event
from desk.sport import FixtureRef
from desk.sports.football.fixtures import from_polymarket_event
from desk.verdict.compare import MarketSnapshot

log = logging.getLogger("desk.sports.football.priced")


def _fixture_key(match_id: str) -> FixtureKey | None:
    """Parse `fb-{competition}-{home}-{away}-{yyyymmdd}` → fixture key.

    Returns None on malformed match_ids (caller logs).
    """
    parts = match_id.split("-")
    if len(parts) < 4:
        return None
    yyyymmdd = parts[-1]
    if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return None
    try:
        kickoff = date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None
    team_a = parts[-3].lower()
    team_b = parts[-2].lower()
    return (kickoff, frozenset({team_a, team_b}))


def _merge_kalshi(
    pm_snap: MarketSnapshot,
    kalshi_snap: MarketSnapshot | None,
) -> MarketSnapshot:
    if kalshi_snap is None or not kalshi_snap.prices:
        return pm_snap
    return MarketSnapshot(
        match_id=pm_snap.match_id,
        asof=pm_snap.asof,
        prices=pm_snap.prices + kalshi_snap.prices,
    )


async def list_priced_fixtures_polymarket() -> list[tuple[FixtureRef, MarketSnapshot]]:
    """Polymarket-only fixture+price pairs. Used in places that haven't
    been migrated to the multi-venue path yet (kept for backwards
    compatibility with callers in the repo)."""
    out: list[tuple[FixtureRef, MarketSnapshot]] = []
    seen: set[str] = set()

    try:
        events = await PolymarketSoccerEventsSource().fetch()
    except Exception as e:                      # noqa: BLE001 — spec §9
        log.warning("polymarket fetch failed: %s", e)
        return out

    allow = config.COMPETITION_ALLOWLIST
    n_filtered = 0
    for ev in events:
        fx = from_polymarket_event(ev)
        if fx is None or fx.match_id in seen:
            continue
        if allow is not None and fx.competition_code not in allow:
            n_filtered += 1
            continue
        seen.add(fx.match_id)
        snap = prices_from_polymarket_event(
            ev,
            match_id=fx.match_id,
            team_a=fx.team_a,
            team_b=fx.team_b,
        )
        out.append((fx, snap))

    if allow is not None:
        log.info(
            "competition allowlist %s — kept %d, filtered %d",
            sorted(allow), len(out), n_filtered,
        )
    return out


async def list_priced_fixtures() -> list[tuple[FixtureRef, MarketSnapshot]]:
    """Multi-venue fixture+price pairs. Merges Polymarket (fixture source +
    prices) with Kalshi (prices only) into one `MarketSnapshot` per fixture.

    Failure-mode: Kalshi failures degrade silently to Polymarket-only;
    a Polymarket failure returns an empty list (no fixtures to publish).
    """
    pm_pairs = await list_priced_fixtures_polymarket()
    if not pm_pairs:
        return pm_pairs

    try:
        kalshi_by_key = await fetch_wc26_snapshots()
    except Exception as e:                      # noqa: BLE001
        log.warning("kalshi snapshot pull failed: %s", e)
        kalshi_by_key = {}

    out: list[tuple[FixtureRef, MarketSnapshot]] = []
    n_kalshi_hits = 0
    for fx, pm_snap in pm_pairs:
        key = _fixture_key(fx.match_id)
        kalshi_snap = kalshi_by_key.get(key) if key else None
        merged = _merge_kalshi(pm_snap, kalshi_snap)
        if kalshi_snap is not None:
            n_kalshi_hits += 1
        out.append((fx, merged))

    log.info(
        "priced fixtures: %d total, %d with kalshi coverage",
        len(out), n_kalshi_hits,
    )
    return out
