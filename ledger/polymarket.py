"""Thin async client for the public Polymarket Data API.

No auth. Rate-limit etiquette: we keep one shared httpx.AsyncClient and a
short timeout per call.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

log = logging.getLogger("ledger.polymarket")

DATA_API = "https://data-api.polymarket.com"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def is_valid_address(address: str) -> bool:
    return bool(_ADDRESS_RE.match(address or ""))


class PolymarketClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=DATA_API, timeout=DEFAULT_TIMEOUT, headers={"Accept": "application/json"}
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            r = await self._client.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            log.warning("polymarket %s failed: %s", path, e)
            raise

    async def positions(self, address: str, limit: int = 500) -> list[dict[str, Any]]:
        return await self._get("/positions", {"user": address, "limit": limit})

    async def value(self, address: str) -> float:
        data = await self._get("/value", {"user": address})
        if isinstance(data, list) and data:
            return float(data[0].get("value", 0) or 0)
        return 0.0

    async def activity(
        self, address: str, *, limit: int = 200, kind: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"user": address, "limit": limit}
        if kind:
            params["type"] = kind
        return await self._get("/activity", params)


_singleton: PolymarketClient | None = None


def get_client() -> PolymarketClient:
    global _singleton
    if _singleton is None:
        _singleton = PolymarketClient()
    return _singleton
