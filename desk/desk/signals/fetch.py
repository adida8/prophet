"""High-level fetch orchestrator.

Per source: HTTP GET → parse → upsert into cache → mark fetched.
Skips a source when its last successful fetch was within `min_interval`
so we stay polite on tier-1 outlets that re-publish often.

Aggregators (`feed_type=aggregator`, e.g. GDELT) are skipped here — PR E
adds their own path. APIs and sitemaps are likewise out of scope until
their respective PRs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from desk.signals.cache import SignalsCache
from desk.signals.models import Source
from desk.signals.registry import Registry

_LOG = logging.getLogger(__name__)

# Polite default — don't hit the same outlet more than once every 10
# minutes. The bias is towards politeness; tier-1 outlets don't break
# stories minute-to-minute, and the cost of being rate-limited (or
# IP-banned) is much higher than the cost of an extra few minutes' lag.
DEFAULT_MIN_INTERVAL = timedelta(minutes=10)
_USER_AGENT = "TheDeskBot/0.1 (+https://oddsprimer.com)"
_HTTP_TIMEOUT = 15.0


@dataclass(frozen=True)
class FetchOutcome:
    source_id: str
    status:    str    # ok / skipped / unsupported / http_error / parse_error
    new:       int = 0
    changed:   int = 0
    unchanged: int = 0
    error:     str | None = None


class _HttpClient(Protocol):
    def get(self, url: str) -> Any: ...


def fetch_source(
    source: Source,
    cache: SignalsCache,
    *,
    client: _HttpClient | None = None,
    now: datetime | None = None,
    min_interval: timedelta = DEFAULT_MIN_INTERVAL,
) -> FetchOutcome:
    now = now or datetime.now(tz=timezone.utc)

    # Resolve which URL to GET and how to parse the response. Aggregator
    # sources (e.g. GDELT) have their query template encoded in the
    # feed_ref under a small URI scheme — see desk/signals/aggregator.py.
    try:
        url, parser = _request_plan(source, now=now)
    except _Unsupported:
        # Sitemaps + APIs land in later PRs. Return cleanly so a batch
        # run can mix supported + unsupported sources.
        return FetchOutcome(source.id, "unsupported")

    last = cache.last_fetched(source.id)
    if last is not None and (now - last) < min_interval:
        return FetchOutcome(source.id, "skipped")

    owns_client = client is None
    if owns_client:
        import httpx  # local — keeps the test runtime free of network deps.
        client = httpx.Client(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    try:
        try:
            resp = client.get(url)
        except Exception as e:  # noqa: BLE001 — any transport failure is "http_error"
            cache.mark_fetched(source.id, now, "http_error")
            _LOG.warning("fetch %s failed: %s", source.id, e)
            return FetchOutcome(source.id, "http_error", error=str(e))

        status_code = getattr(resp, "status_code", 0)
        if status_code != 200:
            label = f"http_{status_code}"
            cache.mark_fetched(source.id, now, label)
            return FetchOutcome(source.id, "http_error", error=f"HTTP {status_code}")

        try:
            items = parser(resp.text)
        except Exception as e:  # noqa: BLE001
            cache.mark_fetched(source.id, now, "parse_error")
            _LOG.warning("parse %s failed: %s", source.id, e)
            return FetchOutcome(source.id, "parse_error", error=str(e))

        counts = cache.upsert_many(items)
        cache.mark_fetched(source.id, now, "ok")
        return FetchOutcome(
            source.id, "ok",
            new=counts["new"], changed=counts["changed"], unchanged=counts["unchanged"],
        )
    finally:
        if owns_client:
            client.close()


class _Unsupported(Exception):
    pass


def _request_plan(source: Source, *, now: datetime):
    """Resolve (url, parser) for a source, or raise _Unsupported."""
    if source.feed_type == "rss":
        from desk.signals.parse import parse_feed
        url = source.feed_ref
        def parse(body: str):
            return parse_feed(source_id=source.id, body=body, fetched_at=now)
        return url, parse

    if source.feed_type == "aggregator":
        from desk.signals.aggregator import (
            build_gdelt_url, parse_aggregator_ref, parse_gdelt_response,
        )
        scheme, raw_query = parse_aggregator_ref(source.feed_ref)
        if scheme != "gdelt":
            raise _Unsupported(f"aggregator scheme {scheme!r} not supported yet")
        url = build_gdelt_url(raw_query)
        def parse(body: str):
            return parse_gdelt_response(source_id=source.id, body=body, fetched_at=now)
        return url, parse

    raise _Unsupported(f"feed_type {source.feed_type!r} not supported")


def fetch_all(
    registry: Registry,
    cache: SignalsCache,
    *,
    tiers: tuple[str, ...] = ("trusted_core",),
    client: _HttpClient | None = None,
    now: datetime | None = None,
    min_interval: timedelta = DEFAULT_MIN_INTERVAL,
) -> list[FetchOutcome]:
    """Fetch every enabled source in the given tier(s). Long-tail tier
    is excluded by default — its aggregator lives in PR E."""
    tier_set = set(tiers)
    outcomes: list[FetchOutcome] = []
    for source in registry.enabled():
        if source.tier not in tier_set:
            continue
        outcomes.append(
            fetch_source(
                source, cache, client=client, now=now, min_interval=min_interval,
            )
        )
    return outcomes
