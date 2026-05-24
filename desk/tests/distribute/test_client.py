"""MTAClient HTTP delivery — status mapping + header shape.

Uses httpx.MockTransport so we never touch the network. Asserts both
the outcome (Ok/Retryable/Permanent) and the wire shape (headers,
signature format) — the wire shape is what MTA validates on the other
side.
"""

from __future__ import annotations

import pytest
import httpx

from desk.distribute.client import MTAClient, Ok, Permanent, Retryable
from desk.distribute.signing import verify


WEBHOOK = "https://markettipsai.example/api/webhooks/desk/publish"
SECRET  = "test-secret-001"


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_200_returns_ok() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, text='{"ok":true}')

    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        result = await client.deliver(b'{"x":1}', now=1735689600)

    assert isinstance(result, Ok)
    assert result.status_code == 200


async def test_request_carries_signing_headers() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200)

    body = b'{"match_id":"m1"}'
    ts = 1735689600
    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        await client.deliver(body, now=ts)

    req = seen["request"]
    assert req.method == "POST"
    assert req.headers["content-type"] == "application/json; charset=utf-8"
    assert req.headers["content-length"] == str(len(body))
    assert req.headers["x-webhook-timestamp"] == str(ts)
    sig_header = req.headers["x-webhook-signature"]
    assert sig_header.startswith("v1=")
    sig_hex = sig_header[len("v1="):]
    # Receiver-side verifier reproduces the same hex.
    assert verify(ts, body, SECRET, sig_hex) is True
    assert bytes(req.content) == body


@pytest.mark.parametrize("code", [400, 401, 403, 404, 405, 410, 413, 415, 422])
async def test_permanent_status_returns_permanent(code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, text="nope")

    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        result = await client.deliver(b'{"x":1}', now=1)

    assert isinstance(result, Permanent)
    assert result.status_code == code


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
async def test_retryable_status_returns_retryable(code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, text="try again")

    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        result = await client.deliver(b'{"x":1}', now=1)

    assert isinstance(result, Retryable)
    assert result.status_code == code


async def test_network_timeout_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        result = await client.deliver(b'{"x":1}', now=1)

    assert isinstance(result, Retryable)
    assert result.status_code is None
    assert "timeout" in result.reason.lower()


async def test_network_connect_error_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns boom", request=request)

    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        result = await client.deliver(b'{"x":1}', now=1)

    assert isinstance(result, Retryable)


async def test_unexpected_status_is_permanent() -> None:
    """A code outside known retry/permanent sets is conservatively
    marked permanent so we don't quietly retry into the void."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, text="I'm a teapot")

    async with _mock_client(handler) as ac:
        client = MTAClient(webhook_url=WEBHOOK, webhook_secret=SECRET, client=ac)
        result = await client.deliver(b'{"x":1}', now=1)

    assert isinstance(result, Permanent)
    assert result.status_code == 418
