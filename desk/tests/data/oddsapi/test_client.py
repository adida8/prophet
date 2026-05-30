"""Unit tests for desk/desk/data/oddsapi/client.py.

Drives the client against an httpx ASGI-style transport so we don't
need a real network. Verifies header parsing, error buckets, and the
implicit `apiKey` query-string injection.
"""

from __future__ import annotations

import pytest
import httpx

from desk.data.oddsapi.client import (
    OddsAPIClient,
    OddsAPIError,
    OddsAPIRateLimit,
)


def _ok_transport(payload, *, headers=None):
    def handler(request: httpx.Request) -> httpx.Response:
        # Capture the URL for the test to inspect.
        return httpx.Response(200, json=payload, headers=headers or {})
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_empty_key_raises_at_construction() -> None:
    with pytest.raises(OddsAPIError, match="ODDS_API_KEY"):
        OddsAPIClient("")


@pytest.mark.asyncio
async def test_get_appends_api_key_to_query() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        await client.get("/v4/sports")
    assert captured["query"].get("apiKey") == "the-key"


@pytest.mark.asyncio
async def test_get_returns_payload_and_rate_limit() -> None:
    headers = {
        "x-requests-remaining": "487",
        "x-requests-used":      "13",
        "x-requests-last":      "1",
    }
    transport = _ok_transport([{"key": "soccer_epl"}], headers=headers)
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        resp = await client.get("/v4/sports")
    assert resp.payload == [{"key": "soccer_epl"}]
    assert isinstance(resp.rate_limit, OddsAPIRateLimit)
    assert resp.rate_limit.requests_remaining == 487
    assert resp.rate_limit.requests_used == 13
    assert resp.rate_limit.last_call_cost == 1


@pytest.mark.asyncio
async def test_get_404_is_permanent() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        with pytest.raises(OddsAPIError) as e:
            await client.get("/v4/sports")
        assert e.value.kind == "permanent"
        assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_get_401_is_auth() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        with pytest.raises(OddsAPIError) as e:
            await client.get("/v4/sports")
        assert e.value.kind == "auth"


@pytest.mark.asyncio
async def test_get_429_is_quota() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        with pytest.raises(OddsAPIError) as e:
            await client.get("/v4/sports")
        assert e.value.kind == "quota"


@pytest.mark.asyncio
async def test_get_5xx_is_transient() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        with pytest.raises(OddsAPIError) as e:
            await client.get("/v4/sports")
        assert e.value.kind == "transient"


@pytest.mark.asyncio
async def test_rate_limit_absent_returns_none() -> None:
    transport = _ok_transport([])   # no rate-limit headers
    async with httpx.AsyncClient(transport=transport) as raw:
        client = OddsAPIClient("the-key", client=raw)
        resp = await client.get("/v4/sports")
    assert resp.rate_limit is None
