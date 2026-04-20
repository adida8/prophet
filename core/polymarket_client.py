"""
Polymarket Gamma API client — public REST, no auth required.
Fetches active markets with prices and volume from gamma-api.polymarket.com.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

import config

log = logging.getLogger("prophet.polymarket")


class PolymarketClient:
    def __init__(self):
        self._http = httpx.AsyncClient(
            base_url=config.POLYMARKET_GAMMA_URL,
            timeout=20.0,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )

    async def close(self):
        await self._http.aclose()

    async def get_markets(self, limit: int = 100) -> list[dict]:
        """Return active markets sorted by 24h volume (descending)."""
        try:
            resp = await self._http.get(
                "/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("markets", [])
        except Exception as e:
            log.error("Polymarket markets fetch failed: %s", e)
            return []

    async def get_market(self, market_id: str) -> Optional[dict]:
        try:
            resp = await self._http.get(f"/markets/{market_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("Polymarket market %s fetch failed: %s", market_id, e)
            return None
