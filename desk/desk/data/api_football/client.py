"""Thin async httpx wrapper for api-football.com (api-sports.io direct).

Auth: header `x-apisports-key: <key>`. The RapidAPI marketplace mirror
needs `x-rapidapi-key` + `x-rapidapi-host` — we go direct so the key
the operator paid for matches the header we send.

Errors fall into three buckets, mirroring the distribute wire pattern:
  - `Auth`        — 401 / 403 with no quota header. Operator config issue.
  - `Quota`       — 429 OR daily/minute counter at zero. Wait and retry.
  - `Transient`   — 5xx / network. Let the caller decide.
  - `Permanent`   — 4xx not in the above. Bug or bad request.

Every response carries provider rate-limit headers (`x-ratelimit-*`)
which the cache layer reads to keep the budget honest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
_DEFAULT_TIMEOUT = 15.0


class APIFootballError(RuntimeError):
    """Anything the client surfaces to the caller — auth / quota /
    transport. Carries a `kind` so the caller can branch without
    string-matching the message."""

    def __init__(self, kind: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


@dataclass(frozen=True)
class APIFootballResponse:
    """Successful response from api-football. `payload` is the parsed
    JSON, `rate_limit` carries the provider's quota counters at the
    time of the call (or None when the response didn't include them)."""
    payload: dict[str, Any]
    rate_limit: "RateLimitSnapshot | None"


@dataclass(frozen=True)
class RateLimitSnapshot:
    """Snapshot of api-football's quota headers at response time.

    api-football publishes per-minute AND per-day counters. The cache /
    runtime layer reads these to back off before a 429.
    """
    requests_remaining: int | None       # x-ratelimit-requests-remaining (per-day)
    requests_limit:     int | None       # x-ratelimit-requests-limit
    minute_remaining:   int | None       # X-RateLimit-Remaining (per-minute)
    minute_limit:       int | None       # X-RateLimit-Limit

    @classmethod
    def from_headers(cls, headers: httpx.Headers) -> "RateLimitSnapshot | None":
        def _i(name: str) -> int | None:
            raw = headers.get(name)
            if raw is None:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        snap = cls(
            requests_remaining=_i("x-ratelimit-requests-remaining"),
            requests_limit=_i("x-ratelimit-requests-limit"),
            minute_remaining=_i("X-RateLimit-Remaining"),
            minute_limit=_i("X-RateLimit-Limit"),
        )
        # If every counter is None, the response carried no rate-limit
        # headers — likely an error path, surface None.
        if all(v is None for v in (snap.requests_remaining, snap.requests_limit,
                                   snap.minute_remaining, snap.minute_limit)):
            return None
        return snap


class APIFootballClient:
    """Async client for the api-football v3 direct endpoint.

    Use as `async with APIFootballClient(key) as c: ...` so the
    underlying httpx pool is closed on exit. The class is intentionally
    thin — endpoint-specific helpers live in sibling modules
    (`status.py`, future `teams.py`, `fixtures.py`).
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = API_FOOTBALL_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ):
        if not api_key:
            raise APIFootballError(
                "auth",
                "API_FOOTBALL_KEY is empty — set it in .env before calling api-football.",
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "APIFootballClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"x-apisports-key": self._api_key},
            )
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
    ) -> APIFootballResponse:
        """GET an endpoint. `path` is the leaf — "/status", "/teams", etc.

        Raises `APIFootballError` on any non-200 with a `kind` tag.
        """
        assert self._client is not None, "use `async with APIFootballClient(...)`"
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as e:
            raise APIFootballError("transient", f"transport error: {e}") from e

        snap = RateLimitSnapshot.from_headers(resp.headers)

        if resp.status_code == 200:
            try:
                payload = resp.json()
            except ValueError as e:
                raise APIFootballError("permanent", f"non-json response: {e}") from e

            # api-football returns 200 with `errors` populated when the
            # request shape is wrong OR the key is invalid. Treat that
            # as the same class as a 4xx so the caller sees one error
            # surface, not two.
            errors = payload.get("errors")
            if errors and isinstance(errors, dict):
                # Auth failures show up here as `errors.token` set.
                if "token" in errors:
                    raise APIFootballError(
                        "auth", f"api-football auth error: {errors['token']}",
                        status_code=200,
                    )
                # Generic 200-with-errors — surface as permanent.
                raise APIFootballError(
                    "permanent", f"api-football errors: {errors}",
                    status_code=200,
                )

            return APIFootballResponse(payload=payload, rate_limit=snap)

        if resp.status_code in (401, 403):
            raise APIFootballError(
                "auth", f"HTTP {resp.status_code} — check API_FOOTBALL_KEY",
                status_code=resp.status_code,
            )
        if resp.status_code == 429:
            raise APIFootballError(
                "quota", "HTTP 429 — api-football rate limit hit",
                status_code=429,
            )
        if 500 <= resp.status_code < 600:
            raise APIFootballError(
                "transient", f"HTTP {resp.status_code} — provider down",
                status_code=resp.status_code,
            )
        raise APIFootballError(
            "permanent", f"HTTP {resp.status_code}",
            status_code=resp.status_code,
        )
