"""Worker drain — outbox state transitions under success/retry/dead."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

from desk.distribute.client import DeliverResult, Ok, Permanent, Retryable
from desk.distribute.config import RETRY_SCHEDULE_SEC
from desk.distribute.outbox import Outbox
from desk.distribute.worker import drain_once


@dataclass
class StubClient:
    """In-memory client that returns scripted outcomes in order. Each
    deliver() call pops the next outcome; if exhausted, returns Ok."""
    outcomes: list[DeliverResult]
    calls: list[bytes] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    async def deliver(self, body: bytes, *, now: int | None = None) -> DeliverResult:
        assert self.calls is not None
        self.calls.append(body)
        if self.outcomes:
            return self.outcomes.pop(0)
        return Ok(status_code=200)

    async def aclose(self) -> None:
        pass


@pytest.fixture
def outbox(tmp_path: Path) -> Outbox:
    return Outbox(tmp_path / "drain.db")


async def test_drain_empty_outbox(outbox: Outbox) -> None:
    stats = await drain_once(outbox, StubClient(outcomes=[]), now=1)
    assert stats.claimed == stats.sent == stats.retried == stats.dead == 0


async def test_drain_sends_pending_and_deletes(outbox: Outbox) -> None:
    outbox.enqueue(match_id="m1", updated_at="t", body=b'p1', now=10)
    outbox.enqueue(match_id="m2", updated_at="t", body=b'p2', now=10)
    client = StubClient(outcomes=[Ok(200), Ok(200)])

    stats = await drain_once(outbox, client, now=100)
    assert stats.claimed == 2
    assert stats.sent == 2
    assert stats.retried == 0
    assert stats.dead == 0
    assert outbox.pending_count() == 0


async def test_drain_retryable_schedules_next_attempt(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'p1', now=10)
    client = StubClient(outcomes=[Retryable(reason="503", status_code=503)])

    stats = await drain_once(outbox, client, now=100)
    assert stats.retried == 1
    assert stats.sent == 0
    row = outbox.get(rid)
    assert row is not None
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.next_attempt_at == 100 + RETRY_SCHEDULE_SEC[0]  # first step
    assert row.last_error and "503" in row.last_error


async def test_drain_permanent_dead_letters_immediately(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'p1', now=10)
    client = StubClient(outcomes=[Permanent(reason="413 too large", status_code=413)])

    stats = await drain_once(outbox, client, now=100)
    assert stats.dead == 1
    assert stats.retried == 0
    row = outbox.get(rid)
    assert row is not None
    assert row.status == "dead"
    assert row.last_error and "413" in row.last_error


async def test_drain_dead_letters_after_schedule_exhausted(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'p1', now=0)
    # Pre-bump attempts to the end of the schedule.
    for i in range(len(RETRY_SCHEDULE_SEC)):
        outbox.mark_retry(rid, next_attempt_at=0, last_error=f"step {i}")
    assert outbox.get(rid).attempts == len(RETRY_SCHEDULE_SEC)

    client = StubClient(outcomes=[Retryable(reason="503", status_code=503)])
    stats = await drain_once(outbox, client, now=1000)
    assert stats.dead == 1
    row = outbox.get(rid)
    assert row is not None
    assert row.status == "dead"
    assert "exhausted" in (row.last_error or "")


async def test_drain_respects_rate_per_min(outbox: Outbox) -> None:
    """Token-bucket caps how many rows we claim per sweep — extras stay
    pending for the next call."""
    for i in range(10):
        outbox.enqueue(match_id=f"m{i}", updated_at="t", body=b'x', now=10 + i)
    client = StubClient(outcomes=[])  # default Ok

    stats = await drain_once(outbox, client, now=100, rate_per_min=3)
    assert stats.claimed == 3
    assert stats.sent == 3
    assert outbox.pending_count() == 7


async def test_drain_concurrency_under_semaphore(outbox: Outbox) -> None:
    """max_in_flight semaphore caps concurrency. We verify with a
    counting stub — it should never see more than N in flight."""
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    @dataclass
    class CountingClient:
        async def deliver(self, body: bytes, *, now: int | None = None) -> DeliverResult:
            nonlocal in_flight, peak
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            async with lock:
                in_flight -= 1
            return Ok(200)

        async def aclose(self) -> None:
            pass

    for i in range(15):
        outbox.enqueue(match_id=f"m{i}", updated_at="t", body=b'x', now=10 + i)

    await drain_once(outbox, CountingClient(), now=100,
                     max_in_flight=3, rate_per_min=50)
    assert peak <= 3
    assert outbox.pending_count() == 0


async def test_drain_does_not_double_send_on_collapse(outbox: Outbox) -> None:
    """Two enqueues for the same match_id collapse to one row → one
    deliver call. Pre-claim invariant."""
    outbox.enqueue(match_id="m1", updated_at="t1", body=b'v1', now=10)
    outbox.enqueue(match_id="m1", updated_at="t2", body=b'v2', now=20)
    client = StubClient(outcomes=[Ok(200)])

    stats = await drain_once(outbox, client, now=100)
    assert stats.claimed == 1
    assert client.calls == [b'v2']
