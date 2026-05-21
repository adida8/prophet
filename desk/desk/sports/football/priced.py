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
from datetime import date, datetime, timezone

from desk import config
from desk.ingest.kalshi_prices import FixtureKey, fetch_wc26_snapshots
from desk.ingest.polymarket import PolymarketSoccerEventsSource
from desk.ingest.polymarket_prices import prices_from_polymarket_event
from desk.ops.report import IngestStats, SourceFreshness, SourceStatus
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


async def _list_priced_fixtures_polymarket_with_stats() -> tuple[
    list[tuple[FixtureRef, MarketSnapshot]],
    int | None,           # raw events fetched, None on fetch failure
    SourceStatus,         # polymarket_gamma source row
]:
    """Polymarket-only fixture+price pairs + the stats the ops dashboard
    needs from this layer. Internal — the public sync entry points wrap
    this and discard the stats they don't need.
    """
    out: list[tuple[FixtureRef, MarketSnapshot]] = []
    seen: set[str] = set()
    now = datetime.now(tz=timezone.utc)

    try:
        events = await PolymarketSoccerEventsSource().fetch()
    except Exception as e:                      # noqa: BLE001 — spec §9
        log.warning("polymarket fetch failed: %s", e)
        return out, None, SourceStatus(
            id="polymarket_gamma",
            status=SourceFreshness.FAILED,
            last_ok=None,
            detail=f"fixture-of-record · fetch failed: {e}",
        )

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

    pm_status = SourceStatus(
        id="polymarket_gamma",
        status=SourceFreshness.FRESH,
        last_ok=now,
        detail=f"fixture-of-record · {len(events)} events fetched, {len(out)} priced",
    )
    return out, len(events), pm_status


async def list_priced_fixtures_polymarket() -> list[tuple[FixtureRef, MarketSnapshot]]:
    """Polymarket-only fixture+price pairs. Kept for callers that don't
    need the multi-venue merge.
    """
    pairs, _, _ = await _list_priced_fixtures_polymarket_with_stats()
    return pairs


async def list_priced_fixtures_with_stats() -> tuple[
    list[tuple[FixtureRef, MarketSnapshot]],
    IngestStats,
]:
    """Multi-venue fixture+price pairs + stats for ops telemetry.

    Failure-mode mirrors `list_priced_fixtures`: Kalshi failures degrade
    silently to Polymarket-only; a Polymarket failure returns an empty
    list. The returned `IngestStats` records the failure so the runner
    can mark the run `partial`/`fail` accordingly.
    """
    now = datetime.now(tz=timezone.utc)
    pm_pairs, raw_events, pm_status = await _list_priced_fixtures_polymarket_with_stats()
    if not pm_pairs:
        return [], IngestStats(
            raw_events=raw_events,
            after_filter=0,
            priced=0,
            kalshi_hits=None,
            sources=[pm_status],
        )

    try:
        kalshi_by_key = await fetch_wc26_snapshots()
        kalshi_status = SourceStatus(
            id="kalshi_kxwcgame",
            status=SourceFreshness.FRESH,
            last_ok=now,
            detail="",  # detail filled in after counting hits
        )
    except Exception as e:                      # noqa: BLE001
        log.warning("kalshi snapshot pull failed: %s", e)
        kalshi_by_key = {}
        kalshi_status = SourceStatus(
            id="kalshi_kxwcgame",
            status=SourceFreshness.FAILED,
            last_ok=None,
            detail=f"2nd venue · pull failed: {e}",
        )

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

    if kalshi_status.status == SourceFreshness.FRESH:
        kalshi_status = SourceStatus(
            id=kalshi_status.id,
            status=kalshi_status.status,
            last_ok=kalshi_status.last_ok,
            detail=f"2nd venue · {n_kalshi_hits} of {len(out)} matches priced",
        )

    priced_note = (
        f"{n_kalshi_hits} of {len(out)} with kalshi coverage"
        if out else None
    )
    return out, IngestStats(
        raw_events=raw_events,
        after_filter=len(pm_pairs),
        priced=len(out),
        kalshi_hits=n_kalshi_hits,
        priced_note=priced_note,
        sources=[pm_status, kalshi_status],
    )


async def list_priced_fixtures() -> list[tuple[FixtureRef, MarketSnapshot]]:
    """Multi-venue fixture+price pairs. Merges Polymarket (fixture source +
    prices) with Kalshi (prices only) into one `MarketSnapshot` per fixture.

    Failure-mode: Kalshi failures degrade silently to Polymarket-only;
    a Polymarket failure returns an empty list (no fixtures to publish).
    """
    pairs, _ = await list_priced_fixtures_with_stats()
    return pairs
