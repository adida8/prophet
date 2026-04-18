"""
Prophet-MVP-v1 — Async HTTP + WebSocket Client
Wraps the Kalshi Demo v2 REST and streaming APIs.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Callable

import httpx
import websockets

import config
from core.auth import get_headers

log = logging.getLogger("prophet.client")


# ── REST Client ──────────────────────────────────────────────────────

class KalshiClient:
    """Thin async wrapper around the Kalshi v2 REST API (Demo)."""

    def __init__(self):
        self._http = httpx.AsyncClient(
            base_url=config.BASE_URL,
            timeout=30.0,
        )

    async def close(self):
        await self._http.aclose()

    # --- helpers ---

    def _api_path(self, endpoint: str) -> str:
        """Return the full path used for signing (includes /trade-api/v2)."""
        return f"/trade-api/v2{endpoint}"

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        path = self._api_path(endpoint)
        headers = get_headers(method.upper(), path)
        resp = await self._http.request(method, endpoint, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # --- public API ---

    async def get_exchange_status(self) -> dict:
        return await self._request("GET", "/exchange/status")

    async def get_markets(
        self,
        limit: int = 50,
        cursor: str | None = None,
        event_ticker: str | None = None,
        status: str = "open",
    ) -> dict:
        params: dict = {"limit": limit, "status": status}
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        return await self._request("GET", "/markets", params=params)

    async def get_market(self, ticker: str) -> dict:
        return await self._request("GET", f"/markets/{ticker}")

    async def get_event(self, event_ticker: str) -> dict:
        return await self._request("GET", f"/events/{event_ticker}")

    async def get_orderbook(self, ticker: str) -> dict:
        return await self._request("GET", f"/markets/{ticker}/orderbook")

    # --- Portfolio / Orders (live trading) ---

    async def place_order(
        self,
        ticker: str,
        side: str,              # "yes" or "no"
        contracts: int,
        price_cents: int | None = None,
        client_order_id: str | None = None,
    ) -> dict:
        """
        POST /portfolio/orders — place a market order.

        For market orders, Kalshi requires a `yes_price` or `no_price` as a
        worst-acceptable fill cap (in cents, 1-99). Passing `price_cents`
        sets that cap; otherwise the current signal price is used.
        """
        body: dict = {
            "ticker": ticker,
            "action": "buy",
            "side": side,
            "count": contracts,
            "type": "market",
        }
        if client_order_id:
            body["client_order_id"] = client_order_id
        if price_cents is not None:
            # Kalshi's market-order protection cap
            if side == "yes":
                body["yes_price"] = price_cents
            else:
                body["no_price"] = price_cents
        return await self._request("POST", "/portfolio/orders", json=body)

    async def get_order(self, order_id: str) -> dict:
        return await self._request("GET", f"/portfolio/orders/{order_id}")

    async def cancel_order(self, order_id: str) -> dict:
        return await self._request("DELETE", f"/portfolio/orders/{order_id}")

    async def get_orders(self, status: str | None = None) -> dict:
        params: dict = {}
        if status:
            params["status"] = status
        return await self._request("GET", "/portfolio/orders", params=params)

    async def get_positions(self) -> dict:
        return await self._request("GET", "/portfolio/positions")

    async def get_balance(self) -> dict:
        return await self._request("GET", "/portfolio/balance")


# ── WebSocket Stream ─────────────────────────────────────────────────

async def stream_tickers(
    tickers: list[str],
    on_tick: Callable[[dict], None] | None = None,
) -> AsyncIterator[dict]:
    """
    Connect to the Kalshi Demo WebSocket and subscribe to the
    `ticker` channel for the given market tickers.

    Yields each incoming tick message as a dict.  If `on_tick` is
    provided, it's called as a side-effect for every tick (useful for
    feeding the strategy engine without consuming the iterator).
    """
    import time, base64
    from core.auth import sign_message

    # Build auth headers for the WS handshake
    timestamp = str(int(time.time() * 1000))
    path = "/trade-api/ws/v2"
    sig = sign_message(timestamp, "GET", path)
    extra_headers = {
        "KALSHI-ACCESS-KEY": config.API_KEY,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
    }

    url = config.WS_URL
    log.info("Connecting to WebSocket: %s", url)

    async for ws in websockets.connect(url, additional_headers=extra_headers):
        try:
            # Subscribe to ticker channel
            subscribe_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["ticker"],
                    "market_tickers": tickers,
                },
            }
            await ws.send(json.dumps(subscribe_msg))
            log.info("Subscribed to tickers: %s", tickers)

            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "ticker":
                    data = msg.get("msg", {})
                    if on_tick:
                        on_tick(data)
                    yield data
                elif msg_type == "error":
                    log.error("WS error: %s", msg)
                # heartbeats and other frames are silently ignored

        except websockets.ConnectionClosed:
            log.warning("WebSocket closed — reconnecting in 5 s")
            await asyncio.sleep(5)
