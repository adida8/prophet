"""Thin async wrapper for OpenWeatherMap One Call 3.0.

Auth: `appid=<key>` query parameter. No header magic.

Error buckets mirror `desk/data/api_football/client.py` so the
verify-data-sources CLI can surface both providers uniformly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/3.0"
_DEFAULT_TIMEOUT = 15.0


class OpenWeatherError(RuntimeError):
    def __init__(self, kind: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


@dataclass(frozen=True)
class OpenWeatherResponse:
    payload: dict[str, Any]


class OpenWeatherClient:
    """Async client for OpenWeatherMap One Call 3.0.

    Use as `async with OpenWeatherClient(key) as c: ...`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = OPENWEATHER_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ):
        if not api_key:
            raise OpenWeatherError(
                "auth",
                "OPENWEATHERMAP_API_KEY is empty — set it in .env before calling openweathermap.",
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "OpenWeatherClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> OpenWeatherResponse:
        assert self._client is not None, "use `async with OpenWeatherClient(...)`"
        merged: dict[str, Any] = {"appid": self._api_key}
        if params:
            merged.update(params)

        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            resp = await self._client.get(url, params=merged)
        except httpx.HTTPError as e:
            raise OpenWeatherError("transient", f"transport error: {e}") from e

        if resp.status_code == 200:
            try:
                return OpenWeatherResponse(payload=resp.json())
            except ValueError as e:
                raise OpenWeatherError("permanent", f"non-json response: {e}") from e
        if resp.status_code in (401, 403):
            raise OpenWeatherError(
                "auth", f"HTTP {resp.status_code} — check OPENWEATHERMAP_API_KEY",
                status_code=resp.status_code,
            )
        if resp.status_code == 429:
            raise OpenWeatherError(
                "quota", "HTTP 429 — openweathermap rate limit hit",
                status_code=429,
            )
        if 500 <= resp.status_code < 600:
            raise OpenWeatherError(
                "transient", f"HTTP {resp.status_code} — provider down",
                status_code=resp.status_code,
            )
        raise OpenWeatherError(
            "permanent", f"HTTP {resp.status_code}: {resp.text[:200]}",
            status_code=resp.status_code,
        )
