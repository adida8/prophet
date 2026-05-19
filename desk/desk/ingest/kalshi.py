"""Kalshi soccer ingest.

Read-only access to Kalshi's prediction-market prices for football matches.
The Kalshi read API is **public** — no signing or auth needed for events
and markets. That lets us pull mid-market quotes without a Desk-owned
API key.

v1 scope: WC 2026 only, via the `KXWCGAME` series. Club football and
non-WC international series can be added as separate `Source` subclasses
later — they each get their own series ticker.

Each event has a deterministic ticker shape we exploit instead of fuzzy
matching: `KXWCGAME-{YY}{MMM}{DD}{ISO3A}{ISO3B}`. Per event, exactly
three child markets, suffixed `-{ISO3A}`, `-{ISO3B}`, `-TIE`. Fixture
identity is parsed straight out of the ticker.

Spec: see the Kalshi pricing section of CLAUDE.md / the matching spec.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from desk.ingest.base import Source, register

log = logging.getLogger("desk.ingest.kalshi")

KALSHI_API_BASE = os.getenv(
    "KALSHI_API_BASE",
    "https://api.elections.kalshi.com/trade-api/v2",
)

WC26_SERIES_TICKER = "KXWCGAME"

# `KXWCGAME-26JUN11MEXRSA` → event-level ticker for one match.
_EVENT_TICKER_RE = re.compile(
    r"^(?P<series>KX[A-Z0-9]+)-"
    r"(?P<yy>\d{2})(?P<mmm>[A-Z]{3})(?P<dd>\d{2})"
    r"(?P<team_a>[A-Z]{3})(?P<team_b>[A-Z]{3})$"
)

# `KXWCGAME-26JUN11MEXRSA-MEX` (or `-TIE`) → child binary market.
_MARKET_TICKER_RE = re.compile(
    r"^(?P<event>KX[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}[A-Z]{3}[A-Z]{3})-"
    r"(?P<suffix>[A-Z]{3,4})$"
)

_MONTH_TO_NUM: dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


@dataclass(frozen=True)
class KalshiEventKey:
    """Parsed identity of one Kalshi match event.

    `team_codes` is order-independent — Kalshi orders them by their own
    convention; the fixture matcher uses a frozenset so the matching
    works regardless of which team Polymarket calls "home".
    """
    series:     str
    kickoff:    date          # date only — Kalshi tickers omit time
    team_codes: frozenset[str]  # lowercase, e.g. {"mex", "rsa"}


def parse_event_ticker(ticker: str) -> KalshiEventKey | None:
    """Return the parsed identity of an event ticker, or None if it doesn't
    match the expected shape. Caller logs unknown shapes.
    """
    m = _EVENT_TICKER_RE.match(ticker or "")
    if not m:
        return None
    mmm = m.group("mmm")
    month = _MONTH_TO_NUM.get(mmm)
    if month is None:
        return None
    try:
        kickoff = date(2000 + int(m.group("yy")), month, int(m.group("dd")))
    except ValueError:
        return None
    return KalshiEventKey(
        series=m.group("series"),
        kickoff=kickoff,
        team_codes=frozenset({m.group("team_a").lower(), m.group("team_b").lower()}),
    )


def parse_market_ticker(ticker: str) -> tuple[str, str] | None:
    """Return (event_ticker, side_suffix_lower) or None.

    Side suffix is one of the two ISO3 codes from the event ticker, or
    "tie". Caller resolves it to "a"/"b"/"draw" by comparing against the
    fixture's team codes.
    """
    m = _MARKET_TICKER_RE.match(ticker or "")
    if not m:
        return None
    return m.group("event"), m.group("suffix").lower()


class KalshiSoccerEventsSource(Source):
    """Lists every active event under the WC 2026 game series.

    Returns the raw event rows; the price layer fetches markets per event.
    """

    id    = "kalshi.soccer_events"
    label = "Kalshi — WC 2026 game events"
    sport = "football"

    def __init__(self, *, series_ticker: str = WC26_SERIES_TICKER, limit: int = 200) -> None:
        super().__init__()
        self._series = series_ticker
        self._limit  = limit

    async def fetch(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        cursor: str | None = None
        async with httpx.AsyncClient(timeout=20.0) as client:
            while True:
                params: dict[str, Any] = {"series_ticker": self._series, "limit": self._limit}
                if cursor:
                    params["cursor"] = cursor
                try:
                    r = await client.get(f"{KALSHI_API_BASE}/events", params=params)
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    log.warning("kalshi events fetch failed (cursor=%s): %s", cursor, e)
                    return events
                payload = r.json() or {}
                page = payload.get("events", []) or []
                events.extend(page)
                cursor = payload.get("cursor")
                if not cursor or not page:
                    break
        log.info("kalshi: pulled %d events for series %s", len(events), self._series)
        return events


async def fetch_markets_for_event(event_ticker: str, *, client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    """Return the raw `markets` array for one event. Empty list on error."""
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=20.0)
    try:
        try:
            r = await c.get(f"{KALSHI_API_BASE}/markets", params={"event_ticker": event_ticker})
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("kalshi markets fetch failed for %s: %s", event_ticker, e)
            return []
        return (r.json() or {}).get("markets", []) or []
    finally:
        if own_client:
            await c.aclose()


register(KalshiSoccerEventsSource())
