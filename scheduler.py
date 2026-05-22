"""
Background scheduler — fetches market data from Kalshi + Polymarket on a
fixed interval, runs comparison/arbitrage/movers logic, and broadcasts
updates to connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import config
from core.client import KalshiClient
from core.polymarket_client import PolymarketClient
from core.market_normalizer import normalize_kalshi, normalize_polymarket, NormalizedMarket
from core.data_store import DataStore
from services.odds_comparator import build_compared_markets, ComparedMarket
from services.arbitrage_detector import detect_arbitrage, ArbitrageOpportunity
from services.movers_tracker import snapshot_prices, get_movers, get_movers_from_memory
from services.market_aggregator import compute_stats, compute_platform_stats, build_ticker_items

log = logging.getLogger("prophet.scheduler")


def _redact(msg: str) -> str:
    """Drop the message entirely if it contains a PEM block.

    Defends against a misconfigured KALSHI_PRIVATE_KEY_PATH (set to the
    PEM contents instead of a path): the resulting FileNotFoundError's
    `str(e)` includes the failed "filename" — i.e. the whole key —
    verbatim. We'd rather lose the diagnostic than leak a key.
    """
    if "-----BEGIN" in msg:
        return "<redacted: error message contained a PEM block>"
    return msg


class Scheduler:
    def __init__(self, broadcast_fn: Optional[Callable] = None):
        self._kalshi      = KalshiClient()
        self._polymarket  = PolymarketClient()
        self._store       = DataStore()
        self._broadcast   = broadcast_fn  # injected by server after startup

        # In-memory state (read by server endpoints)
        self.kalshi_markets:   list[NormalizedMarket]    = []
        self.poly_markets:     list[NormalizedMarket]    = []
        self.all_markets:      list[NormalizedMarket]    = []
        self.compared:         list[ComparedMarket]      = []
        self.arb_opps:         list[ArbitrageOpportunity] = []
        self.movers_24h:       list[dict]                = []
        self.movers_1h:        list[dict]                = []
        self.stats:            dict                      = {}
        self.platform_stats:   dict                      = {}
        self.ticker_items:     list[dict]                = []
        self.last_updated:     Optional[datetime]        = None

        self._prev_markets:    list[NormalizedMarket]    = []
        self._tick            = 0

    def set_broadcast(self, fn: Callable) -> None:
        self._broadcast = fn

    # ── Main loop ─────────────────────────────────────────────────────

    async def run(self) -> None:
        await self._store.init()
        log.info("Scheduler starting — fetch interval %ds", config.FETCH_INTERVAL_SEC)

        while True:
            try:
                await self._fetch_and_process()
            except Exception as e:
                log.error("Scheduler cycle failed: %s", e, exc_info=True)

            self._tick += 1
            await asyncio.sleep(config.FETCH_INTERVAL_SEC)

    # ── Fetch + process ───────────────────────────────────────────────

    async def _fetch_and_process(self) -> None:
        kalshi_raw, poly_raw = await asyncio.gather(
            self._fetch_kalshi(),
            self._fetch_polymarket(),
            return_exceptions=True,
        )

        # Normalize (handle gather exceptions gracefully)
        k_markets: list[NormalizedMarket] = []
        if isinstance(kalshi_raw, list):
            for m in kalshi_raw:
                nm = normalize_kalshi(m)
                if nm:
                    k_markets.append(nm)

        p_markets: list[NormalizedMarket] = []
        if isinstance(poly_raw, list):
            for m in poly_raw:
                nm = normalize_polymarket(m)
                if nm and nm.title:
                    p_markets.append(nm)

        self.kalshi_markets  = k_markets
        self.poly_markets    = p_markets
        self.all_markets     = k_markets + p_markets

        # Comparison + arb
        self.compared  = build_compared_markets(k_markets, p_markets)
        self.arb_opps  = detect_arbitrage(self.compared)

        # Movers: use memory diff between current and previous snapshot
        if self._prev_markets:
            self.movers_24h = get_movers_from_memory(self.all_markets, self._prev_markets)
            self.movers_1h  = get_movers_from_memory(self.all_markets, self._prev_markets)

        # Persist snapshot every MOVERS_SNAPSHOT_INTERVAL_SEC
        if self._tick % max(1, config.MOVERS_SNAPSHOT_INTERVAL_SEC // config.FETCH_INTERVAL_SEC) == 0:
            await snapshot_prices(self._store, self.all_markets)
            db_movers = await get_movers(self._store, hours=24, limit=10)
            if db_movers:
                self.movers_24h = db_movers
            db_movers_1h = await get_movers(self._store, hours=1, limit=10)
            if db_movers_1h:
                self.movers_1h = db_movers_1h

        self._prev_markets   = list(self.all_markets)
        self.stats           = compute_stats(self.all_markets, self.arb_opps, self.movers_24h)
        self.platform_stats  = compute_platform_stats(self.all_markets)
        self.ticker_items    = build_ticker_items(self.compared)
        self.last_updated    = datetime.now(timezone.utc)

        k_count = len(k_markets)
        p_count = len(p_markets)
        log.info(
            "Cycle %d | Kalshi=%d Poly=%d matched=%d arb=%d",
            self._tick, k_count, p_count,
            sum(1 for c in self.compared if len(c.platforms) > 1),
            len(self.arb_opps),
        )

        if self._broadcast:
            try:
                await self._broadcast(self._snapshot_payload("update"))
            except Exception as e:
                log.warning("Broadcast failed: %s", e)

    def snapshot(self) -> dict:
        return self._snapshot_payload("init")

    def _snapshot_payload(self, msg_type: str) -> dict:
        return {
            "type": msg_type,
            "data": {
                "markets":       [m.to_dict() for m in self.all_markets],
                "compared":      [c.to_dict() for c in self.compared],
                "arbitrage":     [a.to_dict() for a in self.arb_opps],
                "movers": {
                    "h24": self.movers_24h,
                    "h1":  self.movers_1h,
                },
                "stats":         self.stats,
                "platforms":     self.platform_stats,
                "ticker":        self.ticker_items,
                "last_updated":  self.last_updated.isoformat() if self.last_updated else None,
            },
        }

    # ── Platform fetchers ─────────────────────────────────────────────

    async def _fetch_kalshi(self) -> list[dict]:
        if not config.API_KEY:
            log.debug("No Kalshi API key — skipping")
            return []
        client = self._kalshi
        try:
            markets: list[dict] = []
            cursor = None
            for _ in range(4):   # max 4 pages × 100 = 400 markets
                resp = await client.get_markets(limit=100, cursor=cursor, status="open")
                page = resp.get("markets", [])
                markets.extend(page)
                cursor = resp.get("cursor")
                if not cursor or len(page) < 100:
                    break
            return markets
        except Exception as e:
            log.warning("Kalshi fetch error: %s", _redact(str(e)))
            return []

    async def _fetch_polymarket(self) -> list[dict]:
        try:
            return await self._polymarket.get_markets(limit=100)
        except Exception as e:
            log.warning("Polymarket fetch error: %s", e)
            return []
