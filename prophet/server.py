"""
Prophet-MVP-v1 — Market Feed Server

Serves a React frontend and proxies Kalshi market data via REST endpoints.
Caches responses to avoid hammering the API.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.client import KalshiClient

log = logging.getLogger("prophet.server")

# ── Cache ─────────────────────────────────────────────────────────────
_cache: dict = {}
CACHE_TTL = 10  # seconds


def _get_cached(key: str):
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _set_cached(key: str, data):
    _cache[key] = (time.time(), data)


# ── Shared client ─────────────────────────────────────────────────────
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = KalshiClient()
    return _client


# ── FastAPI App ───────────────────────────────────────────────────────
app = FastAPI(title="Prophet Market Feed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/feed")
async def api_feed():
    """
    Main feed: fetch markets from popular series,
    sorted by volume (highest first).
    """
    cached = _get_cached("feed")
    if cached:
        return cached

    client = _get_client()
    all_markets = []

    series_list = [
        "KXBTC", "KXETH", "KXINX", "KXSP500",
        "KXFED", "KXCPI", "KXGDP",
        "KXNBA", "KXNFL", "KXMLB",
        "KXTRUMP",
    ]

    for series in series_list:
        try:
            resp = await client._request(
                "GET", "/events",
                params={"limit": 3, "status": "open", "series_ticker": series},
            )
            events = resp.get("events", [])

            for event in events:
                et = event.get("event_ticker", "")
                if not et:
                    continue

                mresp = await client._request(
                    "GET", "/markets",
                    params={"limit": 50, "event_ticker": et, "status": "open"},
                )
                markets = mresp.get("markets", [])

                for m in markets:
                    all_markets.append({
                        "ticker": m.get("ticker", ""),
                        "title": m.get("title", ""),
                        "subtitle": m.get("yes_sub_title", ""),
                        "event_ticker": et,
                        "event_title": event.get("title", ""),
                        "series": series,
                        "yes_bid": m.get("yes_bid_dollars", "0"),
                        "yes_ask": m.get("yes_ask_dollars", "0"),
                        "no_bid": m.get("no_bid_dollars", "0"),
                        "no_ask": m.get("no_ask_dollars", "0"),
                        "last_price": m.get("last_price_dollars", "0"),
                        "volume": m.get("volume_fp", "0"),
                        "open_interest": m.get("open_interest_fp", "0"),
                        "close_time": m.get("close_time", ""),
                    })
        except Exception as e:
            log.warning("Failed to fetch series %s: %s", series, e)

    all_markets.sort(key=lambda m: float(m["volume"] or "0"), reverse=True)

    result = {"markets": all_markets, "count": len(all_markets)}
    _set_cached("feed", result)
    return result


# ── Mount static frontend (built files) ──────────────────────────────
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
