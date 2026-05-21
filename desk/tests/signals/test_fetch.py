"""End-to-end fetch orchestrator — mock HTTP client, real cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from desk.signals.cache import SignalsCache
from desk.signals.fetch import DEFAULT_MIN_INTERVAL, fetch_all, fetch_source
from desk.signals.models import Source
from desk.signals.registry import Registry

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


# ── tiny stand-in for httpx ───────────────────────────────────────────

@dataclass
class _FakeResponse:
    status_code: int
    text: str


class _FakeClient:
    """Returns canned responses by URL. Records every URL hit."""

    def __init__(self, responses: dict[str, _FakeResponse], *, raise_for=None):
        self.responses = responses
        self.raise_for = raise_for or set()
        self.calls: list[str] = []

    def get(self, url: str) -> _FakeResponse:
        self.calls.append(url)
        if url in self.raise_for:
            raise ConnectionError("simulated network failure")
        return self.responses.get(url, _FakeResponse(404, ""))

    def close(self) -> None:
        pass


def _rss_body() -> str:
    return (FIXTURES / "sample-rss.xml").read_text(encoding="utf-8")


def _source(**overrides) -> Source:
    base = dict(
        id="test-src",
        name="Test",
        feed_type="rss",
        feed_ref="https://example.com/rss",
        language="en",
        coverage_tags="global|sport:football",
        reliability=0.9,
        bias_flag="none",
        parent_org="example",
        tier="trusted_core",
        enabled=True,
    )
    base.update(overrides)
    return Source.model_validate(base)


@pytest.fixture
def cache(tmp_path: Path):
    with SignalsCache(tmp_path / "signals.db") as c:
        yield c


# ── happy path ────────────────────────────────────────────────────────

def test_first_fetch_inserts_all_items(cache):
    src = _source()
    client = _FakeClient({src.feed_ref: _FakeResponse(200, _rss_body())})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "ok"
    assert out.new == 2  # third item dropped (empty title)
    assert out.changed == 0
    assert out.unchanged == 0
    assert cache.last_status(src.id) == "ok"
    assert cache.last_fetched(src.id) == _NOW


def test_second_fetch_with_same_body_is_all_unchanged(cache):
    src = _source()
    body = _rss_body()
    client = _FakeClient({src.feed_ref: _FakeResponse(200, body)})

    # First time: respects no rate gate
    fetch_source(src, cache, client=client, now=_NOW)
    # Second time: jump past the rate gate so we actually re-fetch
    out = fetch_source(
        src, cache, client=client,
        now=_NOW + DEFAULT_MIN_INTERVAL + timedelta(seconds=1),
    )
    assert out.status == "ok"
    assert out.unchanged == 2
    assert out.new == out.changed == 0


def test_changed_body_counted_as_changed(cache):
    src = _source()
    base = _rss_body()
    edited = base.replace("miss tomorrow's match", "miss the next two matches")

    fetch_source(src, cache,
                 client=_FakeClient({src.feed_ref: _FakeResponse(200, base)}),
                 now=_NOW)
    out = fetch_source(src, cache,
                       client=_FakeClient({src.feed_ref: _FakeResponse(200, edited)}),
                       now=_NOW + DEFAULT_MIN_INTERVAL + timedelta(seconds=1))
    assert out.changed == 1
    assert out.unchanged == 1


# ── polite-rate gate ──────────────────────────────────────────────────

def test_skips_when_within_min_interval(cache):
    src = _source()
    client = _FakeClient({src.feed_ref: _FakeResponse(200, _rss_body())})
    fetch_source(src, cache, client=client, now=_NOW)

    out = fetch_source(
        src, cache, client=client,
        now=_NOW + timedelta(minutes=1),  # well within the 10-min default
    )
    assert out.status == "skipped"
    assert out.new == out.changed == out.unchanged == 0
    # only one GET should have happened
    assert len(client.calls) == 1


def test_does_not_skip_when_min_interval_overridden_short(cache):
    src = _source()
    client = _FakeClient({src.feed_ref: _FakeResponse(200, _rss_body())})
    fetch_source(src, cache, client=client, now=_NOW,
                 min_interval=timedelta(seconds=0))
    out = fetch_source(src, cache, client=client, now=_NOW + timedelta(seconds=1),
                       min_interval=timedelta(seconds=0))
    assert out.status == "ok"
    assert len(client.calls) == 2


# ── error paths ───────────────────────────────────────────────────────

def test_http_error_recorded(cache):
    src = _source()
    client = _FakeClient({}, raise_for={src.feed_ref})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "http_error"
    assert "simulated" in out.error.lower()
    assert cache.last_status(src.id) == "http_error"


def test_non_200_recorded_as_http_error(cache):
    src = _source()
    client = _FakeClient({src.feed_ref: _FakeResponse(503, "oops")})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "http_error"
    assert "503" in out.error
    assert cache.last_status(src.id) == "http_503"


def test_parse_error_recorded(cache):
    src = _source()
    client = _FakeClient({src.feed_ref: _FakeResponse(200, "<not really xml")})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "parse_error"
    assert cache.last_status(src.id) == "parse_error"


def test_sitemap_feed_type_skipped(cache):
    src = _source(feed_type="sitemap")
    client = _FakeClient({src.feed_ref: _FakeResponse(200, _rss_body())})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "unsupported"
    assert client.calls == []  # never hit the wire
    assert cache.last_fetched(src.id) is None


def test_aggregator_feed_type_routes_to_gdelt(cache):
    src = _source(
        feed_type="aggregator",
        feed_ref="gdelt:query=sport:football",
        tier="long_tail",
    )
    gdelt_body = (FIXTURES / "sample-gdelt.json").read_text(encoding="utf-8")
    # Any URL targeting api.gdeltproject.org returns our canned JSON.
    class _GdeltClient(_FakeClient):
        def get(self, url):
            self.calls.append(url)
            if "api.gdeltproject.org" in url:
                return _FakeResponse(200, gdelt_body)
            return _FakeResponse(404, "")
    client = _GdeltClient({})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "ok"
    assert out.new == 3  # five raw, two dropped for missing fields
    assert any("api.gdeltproject.org" in u for u in client.calls)


def test_aggregator_unknown_scheme_returns_unsupported(cache):
    src = _source(feed_type="aggregator", feed_ref="newsapi:q=football", tier="long_tail")
    client = _FakeClient({})
    out = fetch_source(src, cache, client=client, now=_NOW)
    assert out.status == "unsupported"
    assert client.calls == []


# ── fetch_all over registry ───────────────────────────────────────────

def test_fetch_all_only_hits_trusted_core_by_default(cache):
    reg = Registry.from_csv()
    # Map every reachable source's feed_ref to a canned RSS response;
    # feed_type=none sources have empty feed_ref and we don't even reach
    # them, the fetcher returns "unsupported" without a network call.
    responses = {
        s.feed_ref: _FakeResponse(200, _rss_body())
        for s in reg.enabled() if s.feed_ref
    }
    client = _FakeClient(responses)

    outcomes = fetch_all(reg, cache, client=client, now=_NOW)
    statuses = {o.source_id: o.status for o in outcomes}

    rss_ids:   set[str] = {s.id for s in reg.enabled() if s.feed_type == "rss"}
    nofeed_ids: set[str] = {s.id for s in reg.enabled() if s.feed_type == "none"}
    # RSS sources got an "ok"
    assert all(statuses[i] == "ok" for i in rss_ids)
    # Trust-only (feed_type=none) rows surface as "unsupported" — the
    # fetcher knows there's no public feed to hit, so it skips them
    # cleanly without an http call.
    assert all(statuses[i] == "unsupported" for i in nofeed_ids)


def test_fetch_all_with_long_tail_hits_aggregator(cache, tmp_path):
    # The shipped seed currently carries no long-tail rows, so spin up
    # a tiny synthetic registry to exercise the long-tail path.
    from desk.signals.models import Source
    gdelt_body = (FIXTURES / "sample-gdelt.json").read_text(encoding="utf-8")
    reg = Registry((
        _source(id="trusted-rss", feed_type="rss",
                feed_ref="https://example.com/rss", tier="trusted_core"),
        _source(id="long-tail-gdelt", feed_type="aggregator",
                feed_ref="gdelt:query=sport:football", tier="long_tail"),
    ))

    class _MixedClient:
        def __init__(self):
            self.calls = []
        def get(self, url):
            self.calls.append(url)
            if "api.gdeltproject.org" in url:
                return _FakeResponse(200, gdelt_body)
            return _FakeResponse(200, _rss_body())
        def close(self): pass
    client = _MixedClient()

    outcomes = fetch_all(
        reg, cache, client=client, now=_NOW,
        tiers=("trusted_core", "long_tail"),
    )
    statuses = {o.source_id: o.status for o in outcomes}
    assert statuses["long-tail-gdelt"] == "ok"
    assert statuses["trusted-rss"]     == "ok"
