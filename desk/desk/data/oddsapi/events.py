"""Odds API event ingest — fetch + transform.

One call returns every event for a sport key, with embedded bookmaker
quotes. We filter to the launch venue set and the `h2h` market, and
emit canonical (`event_id`, `venue_id`, `side`, decimal odds) rows
ready for cache storage.

Outcome → side mapping uses the standard 1X2 convention:
    outcome.name == event.home_team        → "a"
    outcome.name == event.away_team        → "b"
    outcome.name in {"Draw", "Tie", ...}   → "draw"

Anything else is silently dropped (logged at DEBUG) — saves the cache
from rows we can't reason about.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from desk.data.oddsapi.cache import PriceRow, Side
from desk.data.oddsapi.client import OddsAPIClient, OddsAPIResponse
from desk.data.oddsapi.venues import LAUNCH_VENUE_IDS

_LOG = logging.getLogger("desk.data.oddsapi.events")

# Bookmaker `outcome.name` values we treat as the draw. The Odds API
# normalises to "Draw" for football, but we add a few common aliases
# defensively — silently dropping a draw price is a worse failure mode
# than accepting an unexpected value.
_DRAW_ALIASES: frozenset[str] = frozenset({"draw", "tie", "x"})

# The launch sport_key. WC26 is the headline surface on the site
# (matches the default `DESK_COMPETITIONS=wc26` filter), so it goes
# first. EPL was the original v1 launch surface and stays as a
# secondary sport_key the operator can flip on.
DEFAULT_SPORT_KEY = "soccer_fifa_world_cup"

# Default tuple of sport_keys the refresh loop fetches per tick. WC26
# is the only one ON by default; the operator overrides with
# `DESK_ODDS_SPORT_KEYS=soccer_fifa_world_cup,soccer_epl,...` to add
# leagues. Each comma-separated entry is one sport_key per The Odds
# API's catalogue (https://the-odds-api.com/sports-odds-data/soccer.html).
DEFAULT_SPORT_KEYS = ("soccer_fifa_world_cup",)


async def fetch_events_h2h(
    client: OddsAPIClient,
    *,
    sport_key: str = DEFAULT_SPORT_KEY,
    regions: str = "uk,eu",
) -> OddsAPIResponse:
    """GET /v4/sports/{sport_key}/odds with `markets=h2h, oddsFormat=decimal`.

    Returns the raw response so the caller can read both the events and
    the rate-limit headers. Caller handles persistence.
    """
    return await client.get(
        f"/v4/sports/{sport_key}/odds",
        params={
            "regions":      regions,
            "markets":      "h2h",
            "oddsFormat":   "decimal",
            "dateFormat":   "iso",
        },
    )


def parse_event_payload(events_payload: Any, *, fetched_at: datetime | None = None) -> list[dict[str, Any]]:
    """Turn raw API output into a list of normalised event dicts.

    Each dict carries:
        event_id, sport_key, commence_time, home_team, away_team,
        price_rows: list[PriceRow]   # filtered to LAUNCH_VENUE_IDS + h2h

    Out-of-spec rows (bad timestamps, unknown outcomes) are silently
    skipped; we'd rather publish a sparse cache than choke on one bad
    event.
    """
    fetched_at = fetched_at or datetime.now(tz=timezone.utc)
    fetched_iso = fetched_at.isoformat()
    out: list[dict[str, Any]] = []

    if not isinstance(events_payload, list):
        return out

    for ev in events_payload:
        if not isinstance(ev, dict):
            continue
        event_id      = ev.get("id")
        sport_key     = ev.get("sport_key")
        commence_raw  = ev.get("commence_time")
        home_team     = ev.get("home_team")
        away_team     = ev.get("away_team")
        if not (isinstance(event_id, str) and isinstance(sport_key, str)
                and isinstance(home_team, str) and isinstance(away_team, str)
                and isinstance(commence_raw, str)):
            continue
        try:
            commence_time = _parse_iso(commence_raw)
        except ValueError:
            continue

        price_rows: list[PriceRow] = []
        for bk in ev.get("bookmakers", []) or []:
            if not isinstance(bk, dict):
                continue
            venue_id = bk.get("key")
            if venue_id not in LAUNCH_VENUE_IDS:
                continue
            last_update = bk.get("last_update") or fetched_iso
            for mk in bk.get("markets", []) or []:
                if not isinstance(mk, dict):
                    continue
                if mk.get("key") != "h2h":
                    continue
                for o in mk.get("outcomes", []) or []:
                    side = _classify_outcome(
                        o, home=home_team, away=away_team,
                    )
                    if side is None:
                        continue
                    try:
                        decimal_odds = float(o.get("price"))
                    except (TypeError, ValueError):
                        continue
                    if decimal_odds <= 1.0:
                        # Sub-evens is a contract violation by the
                        # provider — clearer to drop than to publish a
                        # negative-payout price.
                        continue
                    price_rows.append(PriceRow(
                        event_id=event_id,
                        venue_id=venue_id,
                        side=side,
                        decimal_odds=decimal_odds,
                        last_update=last_update,
                        fetched_at=fetched_iso,
                    ))

        out.append({
            "event_id":      event_id,
            "sport_key":     sport_key,
            "commence_time": commence_time,
            "home_team":     home_team,
            "away_team":     away_team,
            "price_rows":    price_rows,
        })
    return out


def _parse_iso(raw: str) -> datetime:
    """The Odds API uses ISO-8601 with `Z` suffix; fromisoformat in 3.9
    rejects Z, so normalise to +00:00 first."""
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _classify_outcome(o: dict[str, Any], *, home: str, away: str) -> Side | None:
    name = (o.get("name") or "").strip()
    if not name:
        return None
    name_lower = name.lower()
    if name_lower in _DRAW_ALIASES:
        return "draw"
    if name == home:
        return "a"
    if name == away:
        return "b"
    # The Odds API mostly uses exact team names that match
    # event.home_team / event.away_team. Fall back to a case-insensitive
    # compare to absorb stray title-casing differences.
    if name_lower == home.lower():
        return "a"
    if name_lower == away.lower():
        return "b"
    _LOG.debug("dropping unknown outcome %r (home=%r, away=%r)", name, home, away)
    return None


def venue_ids_in_events(parsed_events: Iterable[dict[str, Any]]) -> list[str]:
    """Convenience: unique venue ids seen across the parsed batch.
    Useful for the CLI to report "saw quotes from pinnacle, williamhill"."""
    seen: set[str] = set()
    for ev in parsed_events:
        for pr in ev.get("price_rows", []):
            seen.add(pr.venue_id)
    return sorted(seen)
