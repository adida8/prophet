"""HTTPS client for the MTA webhook — copied verbatim from Desk.

Sum-typed `DeliverResult` so the worker dispatches on
`Ok | Retryable | Permanent` without interpreting status codes.

    200          → Ok (delivered, or idempotent no-op replay)
    400/401/413  → Permanent (configuration / contract bug, do NOT retry)
    429/5xx      → Retryable (transient overload or upstream issue)
    network errs → Retryable (timeout, DNS, conn refused)
    anything else → Permanent (conservative — surface and alert)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Union

import httpx

from stubdesk.signing import sign


@dataclass(frozen=True)
class Ok:
    status_code: int


@dataclass(frozen=True)
class Retryable:
    reason: str
    status_code: int | None = None  # None for network-level failures


@dataclass(frozen=True)
class Permanent:
    reason: str
    status_code: int | None = None


DeliverResult = Union[Ok, Retryable, Permanent]

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_PERMANENT_STATUS = {400, 401, 403, 404, 405, 410, 413, 415, 422}


class MTAClient:
    """Thin wrapper around httpx.AsyncClient with HMAC signing baked in."""

    def __init__(self, *, webhook_url: str, webhook_secret: str,
                 timeout_sec: float = 10.0,
                 client: httpx.AsyncClient | None = None) -> None:
        self.webhook_url    = webhook_url
        self.webhook_secret = webhook_secret
        self.timeout_sec    = timeout_sec
        self._client        = client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def deliver(self, body: bytes, *, now: int | None = None) -> DeliverResult:
        """POST `body` to the webhook. Returns a typed outcome."""
        ts = now if now is not None else int(time.time())
        signature = sign(ts, body, self.webhook_secret)
        headers = {
            "Content-Type":       "application/json; charset=utf-8",
            "Content-Length":     str(len(body)),
            "x-webhook-timestamp": str(ts),
            "x-webhook-signature": f"v1={signature}",
        }
        client = self._client if self._client is not None else httpx.AsyncClient(
            timeout=self.timeout_sec,
        )
        try:
            resp = await client.post(self.webhook_url, content=body, headers=headers)
        except httpx.TimeoutException as e:
            return Retryable(reason=f"timeout: {e}")
        except httpx.HTTPError as e:
            return Retryable(reason=f"network: {type(e).__name__}: {e}")
        finally:
            if self._client is None:
                await client.aclose()

        code = resp.status_code
        if code == 200:
            return Ok(status_code=200)
        if code in _RETRYABLE_STATUS:
            return Retryable(reason=f"status {code}: {_excerpt(resp)}", status_code=code)
        if code in _PERMANENT_STATUS:
            return Permanent(reason=f"status {code}: {_excerpt(resp)}", status_code=code)
        return Permanent(reason=f"unexpected status {code}: {_excerpt(resp)}",
                         status_code=code)


def _excerpt(resp: httpx.Response, limit: int = 200) -> str:
    try:
        text = resp.text
    except Exception:                          # noqa: BLE001
        return ""
    text = text.strip().replace("\n", " ")
    return text[:limit]
