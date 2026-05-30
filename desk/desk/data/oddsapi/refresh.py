"""Orchestrator for the Odds-API refresh tick.

`desk fetch-odds` runs this. For each sport key (v1 ships
`soccer_epl`), pulls h2h prices for `regions=uk,eu`, parses the
payload, writes events + per-(event,venue) price rows to the sqlite
cache. Football glue then resolves `event_id` → canonical match_id
in a second pass.

Cost: one Odds-API request per sport key per tick (the `/odds`
endpoint returns every event with every bookmaker's quotes in one
call). The Odds API charges credits per region asked — `regions=uk,eu`
costs 2 credits per call.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from desk.data.oddsapi.cache import OddsAPICache, default_cache_path
from desk.data.oddsapi.client import OddsAPIClient, OddsAPIError
from desk.data.oddsapi.events import (
    DEFAULT_SPORT_KEY,
    fetch_events_h2h,
    parse_event_payload,
)
from desk.data.oddsapi.venues import LAUNCH_VENUE_IDS

log = logging.getLogger("desk.data.oddsapi.refresh")


@dataclass(frozen=True)
class RefreshReport:
    """Result of a single `refresh_all` invocation. Captures what the
    operator needs to see in logs / the ops dashboard."""
    sport_keys:        tuple[str, ...]
    events_fetched:    int
    events_persisted:  int
    price_rows_written: int
    venues_seen:       tuple[str, ...]
    credits_consumed:  int | None
    error:             str | None = None

    def headline(self) -> str:
        ev = self.events_persisted
        rows = self.price_rows_written
        vs = ", ".join(self.venues_seen) or "—"
        cost = (f"{self.credits_consumed} credits"
                if self.credits_consumed is not None else "credits ?")
        if self.error:
            return f"odds-api refresh: ERROR — {self.error}"
        return (
            f"odds-api refresh: {ev} events · {rows} price rows · "
            f"venues=[{vs}] · {cost}"
        )


def _resolve_event_match_ids(parsed_events, cache) -> int:
    """For every parsed event, resolve event_id → canonical match_id
    via the football glue and stamp it on the cached event row.

    Lives here (instead of inside the football package) so the call is
    a one-liner from `refresh_all` and the football import sits behind
    the function-local scope — keeps the sport-agnostic `oddsapi`
    package free of football imports at module load.
    """
    from desk.sports.football.oddsapi_glue import from_oddsapi_event

    n = 0
    for ev in parsed_events:
        fx = from_oddsapi_event(ev)
        if fx is None:
            continue
        try:
            cache.set_event_resolution(ev["event_id"], fx.match_id)
            n += 1
        except Exception as e:                              # noqa: BLE001
            log.warning("set_event_resolution failed for %s: %s",
                        ev.get("event_id"), e)
    return n


async def refresh_all(
    *,
    api_key: str,
    sport_keys: tuple[str, ...] = (DEFAULT_SPORT_KEY,),
    cache_path = None,
    regions: str = "uk,eu",
) -> RefreshReport:
    """Pull + persist h2h prices for every sport_key.

    A failure on one sport_key doesn't block the others — best-effort,
    per-sport-key try/except mirrors the runner's spec §9 rule.
    """
    cache = OddsAPICache(cache_path or default_cache_path())
    fetched = 0
    persisted = 0
    rows_written = 0
    venues: set[str] = set()
    credits = 0
    any_error: str | None = None
    try:
        async with OddsAPIClient(api_key) as client:
            for sk in sport_keys:
                try:
                    resp = await fetch_events_h2h(
                        client, sport_key=sk, regions=regions,
                    )
                except OddsAPIError as e:
                    log.warning("odds-api %s: %s", sk, e)
                    any_error = f"{sk}: {e}"
                    cache.mark_fetch(
                        f"{sk}/h2h", "error",
                        credits=None,
                    )
                    continue

                parsed = parse_event_payload(resp.payload)
                fetched += len(parsed)

                for ev in parsed:
                    cache.upsert_event(
                        event_id=ev["event_id"],
                        sport_key=ev["sport_key"],
                        commence_time=ev["commence_time"],
                        home_team=ev["home_team"],
                        away_team=ev["away_team"],
                    )
                    persisted += 1
                    # Group price rows by venue so we can use the
                    # delete-then-insert semantics per (event, venue)
                    # pair.
                    by_venue: dict[str, list] = {}
                    for pr in ev.get("price_rows", []):
                        by_venue.setdefault(pr.venue_id, []).append(pr)
                        venues.add(pr.venue_id)
                    for venue_id, rows in by_venue.items():
                        rows_written += cache.replace_prices_for_event_venue(
                            event_id=ev["event_id"],
                            venue_id=venue_id,
                            rows=rows,
                        )

                # Resolve event_id → canonical match_id and stamp it
                # on the row so the runtime merge can find it by
                # `events_for_match_id(match_id)`.
                _resolve_event_match_ids(parsed, cache)

                if resp.rate_limit is not None and resp.rate_limit.last_call_cost is not None:
                    credits += resp.rate_limit.last_call_cost
                cache.mark_fetch(
                    f"{sk}/h2h", "ok",
                    credits=(resp.rate_limit.last_call_cost
                             if resp.rate_limit is not None else None),
                )
    finally:
        cache.close()

    # Sanity log if we got a payload but none of our launch venues
    # appeared — likely a region misconfig.
    if persisted and not (set(LAUNCH_VENUE_IDS) & venues):
        log.warning(
            "odds-api refresh: payload had no launch-venue rows; "
            "got venues=%s (regions=%s)",
            sorted(venues), regions,
        )

    return RefreshReport(
        sport_keys=tuple(sport_keys),
        events_fetched=fetched,
        events_persisted=persisted,
        price_rows_written=rows_written,
        venues_seen=tuple(sorted(venues)),
        credits_consumed=(credits if credits else None),
        error=any_error,
    )
