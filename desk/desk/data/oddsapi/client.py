"""Async httpx wrapper for The Odds API v4 (the-odds-api.com).

Auth: query-string `apiKey=…`. Reads cost quota credits per call (the
service publishes monthly + remaining counts via `X-Requests-*` headers).

Mirrors `desk/desk/data/api_football/client.py` error-bucket pattern:

    `auth`        — 401 / 403. Operator config issue.
    `quota`       — 429 OR monthly counter at zero.
    `transient`   — 5xx / network.
    `permanent`   — 4xx not in the above.

The class is intentionally thin; endpoint-specific helpers live in
sibling modules (`status.py` for /sports, future `events.py` for
/sports/{key}/odds).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)

ODDS_API_BASE_URL = "https://api.the-odds-api.com"
_DEFAULT_TIMEOUT  = 15.0


class OddsAPIError(RuntimeError):
    """Anything the client surfaces to the caller. `kind` tags the
    bucket so the caller can branch without string-matching messages."""

    def __init__(self, kind: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


@dataclass(frozen=True)
class OddsAPIRateLimit:
    """Snapshot of The Odds API's quota headers at response time.

    Three counters published on every successful response:
        x-requests-remaining — monthly quota left
        x-requests-used      — monthly quota consumed
        x-requests-last      — credits charged for THIS call
                               (h2h/1X2 reads cost 1 credit per region asked)
    """
    requests_remaining: int | None
    requests_used:      int | None
    last_call_cost:     int | None

    @classmethod
    def from_headers(cls, headers: httpx.Headers) -> "OddsAPIRateLimit | None":
        def _i(name: str) -> int | None:
            raw = headers.get(name)
            if raw is None:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
        snap = cls(
            requests_remaining=_i("x-requests-remaining"),
            requests_used=_i("x-requests-used"),
            last_call_cost=_i("x-requests-last"),
        )
        if all(v is None for v in (snap.requests_remaining,
                                   snap.requests_used,
                                   snap.last_call_cost)):
            return None
        return snap


@dataclass(frozen=True)
class OddsAPIResponse:
    payload:    Any
    rate_limit: OddsAPIRateLimit | None


class OddsAPIClient:
    """Async client for The Odds API v4.

    Use as `async with OddsAPIClient(key) as c: ...`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = ODDS_API_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ):
        if not api_key:
            raise OddsAPIError(
                "auth",
                "ODDS_API_KEY is empty — set it in .env before calling The Odds API.",
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "OddsAPIClient":
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
    ) -> OddsAPIResponse:
        """GET an endpoint. `path` is the leaf — "/v4/sports", etc.

        Always appends `apiKey=…`. Raises `OddsAPIError` on any non-200.
        """
        assert self._client is not None, "use `async with OddsAPIClient(...)`"
        # The Odds API expects the apiKey on every call. Caller-supplied
        # params override anything we pre-populate, except the apiKey
        # itself — we always set it last so a misconfigured caller can't
        # accidentally strip auth.
        q: dict[str, Any] = dict(params or {})
        q["apiKey"] = self._api_key
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            resp = await self._client.get(url, params=q)
        except httpx.HTTPError as e:
            raise OddsAPIError("transient", f"transport error: {e}") from e

        snap = OddsAPIRateLimit.from_headers(resp.headers)

        if resp.status_code == 200:
            try:
                payload = resp.json()
            except ValueError as e:
                raise OddsAPIError("permanent", f"non-json response: {e}") from e
            return OddsAPIResponse(payload=payload, rate_limit=snap)

        if resp.status_code in (401, 403):
            raise OddsAPIError(
                "auth", f"HTTP {resp.status_code} — check ODDS_API_KEY",
                status_code=resp.status_code,
            )
        if resp.status_code == 429:
            raise OddsAPIError(
                "quota", "HTTP 429 — Odds API rate limit hit",
                status_code=429,
            )
        if 500 <= resp.status_code < 600:
            raise OddsAPIError(
                "transient", f"HTTP {resp.status_code} — provider down",
                status_code=resp.status_code,
            )
        raise OddsAPIError(
            "permanent", f"HTTP {resp.status_code}: {resp.text[:200]}",
            status_code=resp.status_code,
        )
