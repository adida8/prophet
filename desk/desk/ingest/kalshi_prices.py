"""Kalshi → MarketSnapshot.

The flow:
  1. List WC 2026 events via `KalshiSoccerEventsSource`.
  2. For each event, GET /markets?event_ticker=… (one round trip per event,
     no orderbook calls — the markets payload already carries
     `yes_bid_dollars` / `yes_ask_dollars`).
  3. Parse the market suffix to map back to side: the suffix is one of the
     two ISO3 codes from the event ticker, or "tie".
  4. Implied probability = (yes_bid + yes_ask) / 2, taken from the dollar
     fields which are already in [0, 1].

The output is keyed on a fixture key — `(date, frozenset({iso3_a, iso3_b}))`
— so the priced-fixtures merger can look up Kalshi snapshots without
caring which team Polymarket considers "home".
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

from desk.ingest.kalshi import (
    KalshiSoccerEventsSource,
    fetch_markets_for_event,
    parse_event_ticker,
    parse_market_ticker,
)
from desk.verdict.compare import MarketSnapshot, Side, VenuePrice

log = logging.getLogger("desk.ingest.kalshi_prices")


FixtureKey = tuple[date, frozenset[str]]


def _parse_dollar(raw: Any) -> float | None:
    """Kalshi's `yes_bid_dollars` is a string like "0.6400"."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= v <= 1.0):
        return None
    return v


def _midpoint(bid: Any, ask: Any) -> float | None:
    b = _parse_dollar(bid)
    a = _parse_dollar(ask)
    if b is None and a is None:
        return None
    if b is None:
        return a
    if a is None:
        return b
    return (b + a) / 2.0


def _side_for_suffix(
    suffix: str,
    *,
    team_a_code: str,
    team_b_code: str,
) -> Side | None:
    """`suffix` is lowercase ISO3 or "tie". `team_*_code` are lowercase
    ISO3 from the event ticker (Kalshi's), in the order Kalshi declared
    them — which is what we'll mirror as side "a"/"b" inside the snapshot.
    """
    if suffix == "tie":
        return "draw"
    if suffix == team_a_code:
        return "a"
    if suffix == team_b_code:
        return "b"
    return None


def snapshots_from_event(
    *,
    event_ticker: str,
    markets: list[dict[str, Any]],
    asof: datetime | None = None,
) -> tuple[FixtureKey, MarketSnapshot] | None:
    """Build one fixture-keyed `MarketSnapshot` from a Kalshi event's markets.

    Returns None if the event ticker is unparseable. Skips individual
    markets with missing/out-of-range prices but still returns a snapshot
    for the others.
    """
    key = parse_event_ticker(event_ticker)
    if key is None:
        log.warning("unparseable kalshi event ticker: %s", event_ticker)
        return None

    asof = asof or datetime.now(tz=timezone.utc)
    teams_sorted = sorted(key.team_codes)
    # Recover Kalshi's declared order from the original ticker — the
    # frozenset loses ordering, so re-parse the suffix groups.
    # `_EVENT_TICKER_RE` already validated structure; index slice is safe.
    body = event_ticker.split("-", 1)[1]
    yy_mmm_dd_len = 2 + 3 + 2  # YY + MMM + DD
    team_a_code = body[yy_mmm_dd_len : yy_mmm_dd_len + 3].lower()
    team_b_code = body[yy_mmm_dd_len + 3 : yy_mmm_dd_len + 6].lower()

    prices: list[VenuePrice] = []
    for m in markets:
        if (m.get("status") or "").lower() != "active":
            continue
        parsed = parse_market_ticker(m.get("ticker") or "")
        if parsed is None:
            continue
        _ev, suffix = parsed
        side = _side_for_suffix(suffix, team_a_code=team_a_code, team_b_code=team_b_code)
        if side is None:
            continue
        mid = _midpoint(m.get("yes_bid_dollars"), m.get("yes_ask_dollars"))
        if mid is None:
            continue
        prices.append(VenuePrice(venue="kalshi", side=side, implied_p=mid))

    fixture_key: FixtureKey = (key.kickoff, frozenset(teams_sorted))
    snap = MarketSnapshot(
        # No native match_id at this layer; the merger replaces it with
        # the Polymarket fixture's match_id when merging.
        match_id="",
        asof=asof,
        prices=tuple(prices),
    )
    return fixture_key, snap


async def fetch_wc26_snapshots(
    *,
    asof: datetime | None = None,
) -> dict[FixtureKey, MarketSnapshot]:
    """Live pull: every WC 2026 fixture's Kalshi snapshot, keyed by
    `(kickoff_date, frozenset({iso3_a, iso3_b}))`.

    Failure-mode: returns whatever it managed to collect. A single
    failed event doesn't block the rest; an upstream events-list
    failure returns an empty dict.
    """
    asof = asof or datetime.now(tz=timezone.utc)
    out: dict[FixtureKey, MarketSnapshot] = {}

    try:
        events = await KalshiSoccerEventsSource().fetch()
    except Exception as e:                              # noqa: BLE001 — spec §9
        log.warning("kalshi events fetch raised: %s", e)
        return out

    async with httpx.AsyncClient(timeout=20.0) as client:
        async def _one(ev: dict[str, Any]) -> tuple[FixtureKey, MarketSnapshot] | None:
            ticker = ev.get("event_ticker") or ""
            try:
                markets = await fetch_markets_for_event(ticker, client=client)
            except Exception as e:                       # noqa: BLE001
                log.warning("kalshi markets fetch raised for %s: %s", ticker, e)
                return None
            return snapshots_from_event(event_ticker=ticker, markets=markets, asof=asof)

        # ~70 WC26 fixtures; gather in parallel rather than serial.
        results = await asyncio.gather(*(_one(ev) for ev in events))

    for r in results:
        if r is None:
            continue
        key, snap = r
        if snap.prices:
            out[key] = snap

    log.info("kalshi: built snapshots for %d fixtures", len(out))
    return out


def prices_for(match_id: str) -> MarketSnapshot:
    """Legacy stub kept for callers that haven't migrated to the keyed
    dict yet. Always returns an empty snapshot — production callers
    should use `fetch_wc26_snapshots()` instead.
    """
    return MarketSnapshot(
        match_id=match_id,
        asof=datetime.now(tz=timezone.utc),
        prices=(),
    )
