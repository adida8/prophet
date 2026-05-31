"""Outbox sqlite layer — enqueue, claim_due, mark_*, collapse semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from desk.distribute.outbox import Outbox, SCHEMA_VERSION


@pytest.fixture
def outbox(tmp_path: Path) -> Outbox:
    return Outbox(tmp_path / "distribute.db")


def test_enqueue_creates_row(outbox: Outbox) -> None:
    rid = outbox.enqueue(
        match_id="fb-wc26-fra-mex-20260612",
        updated_at="2026-06-12T17:00:00Z",
        body=b'{"x":1}',
        now=100,
    )
    row = outbox.get(rid)
    assert row is not None
    assert row.match_id == "fb-wc26-fra-mex-20260612"
    assert row.attempts == 0
    assert row.next_attempt_at == 100
    assert row.status == "pending"
    assert outbox.pending_count() == 1


def test_enqueue_collapses_on_same_match(outbox: Outbox) -> None:
    """Two writes for the same match_id leave one pending row, with the
    second body — older body is no longer truth."""
    a = outbox.enqueue(match_id="m1", updated_at="t1", body=b'{"v":1}', now=100)
    b = outbox.enqueue(match_id="m1", updated_at="t2", body=b'{"v":2}', now=200)
    assert a == b, "second enqueue must update the same row id"
    assert outbox.pending_count() == 1
    row = outbox.get(a)
    assert row is not None
    assert row.body == b'{"v":2}'
    assert row.updated_at == "t2"
    assert row.attempts == 0          # reset on replace
    assert row.next_attempt_at == 200  # reset to now
    assert row.last_error is None


def test_enqueue_after_retry_resets_attempts(outbox: Outbox) -> None:
    """Replacing a row that's been retried clears the attempt counter —
    the replacement is fresh content, not a continuation."""
    rid = outbox.enqueue(match_id="m1", updated_at="t1", body=b'{"v":1}', now=100)
    outbox.mark_retry(rid, next_attempt_at=300, last_error="429 throttled")
    row = outbox.get(rid)
    assert row is not None and row.attempts == 1

    outbox.enqueue(match_id="m1", updated_at="t2", body=b'{"v":2}', now=500)
    row2 = outbox.get(rid)
    assert row2 is not None
    assert row2.attempts == 0
    assert row2.last_error is None
    assert row2.body == b'{"v":2}'


def test_claim_due_respects_next_attempt_at(outbox: Outbox) -> None:
    outbox.enqueue(match_id="ready",      updated_at="t", body=b'r', now=100)
    not_yet = outbox.enqueue(match_id="later", updated_at="t", body=b'l', now=100)
    outbox.mark_retry(not_yet, next_attempt_at=1000, last_error="x")

    due = outbox.claim_due(now=500, limit=10)
    ids = {r.match_id for r in due}
    assert "ready" in ids
    assert "later" not in ids


def test_claim_due_orders_oldest_first(outbox: Outbox) -> None:
    r1 = outbox.enqueue(match_id="m1", updated_at="t", body=b'1', now=100)
    r2 = outbox.enqueue(match_id="m2", updated_at="t", body=b'2', now=200)
    r3 = outbox.enqueue(match_id="m3", updated_at="t", body=b'3', now=150)

    due = outbox.claim_due(now=999, limit=10)
    # Ordered by next_attempt_at, then id.
    assert [r.id for r in due] == [r1, r3, r2]


def test_claim_due_honours_limit(outbox: Outbox) -> None:
    for i in range(5):
        outbox.enqueue(match_id=f"m{i}", updated_at="t", body=b'x', now=100 + i)
    assert len(outbox.claim_due(now=999, limit=3)) == 3


def test_mark_sent_deletes_row(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'x', now=100)
    outbox.mark_sent(rid)
    assert outbox.get(rid) is None
    assert outbox.pending_count() == 0


def test_mark_retry_bumps_attempts(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'x', now=100)
    outbox.mark_retry(rid, next_attempt_at=200, last_error="503")
    outbox.mark_retry(rid, next_attempt_at=300, last_error="503 again")
    row = outbox.get(rid)
    assert row is not None
    assert row.attempts == 2
    assert row.next_attempt_at == 300
    assert row.last_error == "503 again"
    assert row.status == "pending"


def test_mark_dead_preserves_row(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'x', now=100)
    outbox.mark_dead(rid, reason="permanent: 413 payload too large")
    row = outbox.get(rid)
    assert row is not None
    assert row.status == "dead"
    assert row.last_error == "permanent: 413 payload too large"
    assert outbox.pending_count() == 0
    assert outbox.dead_count() == 1


def test_dead_rows_dont_appear_in_claim_due(outbox: Outbox) -> None:
    rid = outbox.enqueue(match_id="m1", updated_at="t", body=b'x', now=100)
    outbox.mark_dead(rid, reason="permanent")
    assert outbox.claim_due(now=999, limit=10) == []


def test_list_dead_returns_recent_first(outbox: Outbox) -> None:
    ids = []
    for i in range(3):
        rid = outbox.enqueue(match_id=f"m{i}", updated_at="t", body=b'x', now=100 + i)
        outbox.mark_dead(rid, reason=f"err{i}")
        ids.append(rid)
    dead = outbox.list_dead(limit=10)
    assert [r.id for r in dead] == list(reversed(ids))


def test_schema_version_set(tmp_path: Path) -> None:
    """PRAGMA user_version is bumped on init so future migrations have a
    starting point."""
    box = Outbox(tmp_path / "x.db")
    cur = box._conn.execute("PRAGMA user_version").fetchone()
    assert cur[0] == SCHEMA_VERSION
    box.close()


def test_outbox_survives_close_reopen(tmp_path: Path) -> None:
    """Persistence sanity — close one handle, open another, rows are there.
    Critical because the runner subprocess opens-uses-closes per tick."""
    db_path = tmp_path / "persist.db"
    with Outbox(db_path) as box:
        box.enqueue(match_id="m1", updated_at="t1", body=b'survived', now=100)

    with Outbox(db_path) as box2:
        rows = box2.claim_due(now=999, limit=10)
        assert len(rows) == 1
        assert rows[0].body == b'survived'


# ── retry_dead_letters ────────────────────────────────────────────────

def test_retry_dead_letters_all_when_no_filter(tmp_path: Path) -> None:
    """Calling without match_ids retries every dead row."""
    with Outbox(tmp_path / "x.db") as box:
        rid1 = box.enqueue(match_id="m1", updated_at="t1", body=b'a', now=100)
        rid2 = box.enqueue(match_id="m2", updated_at="t1", body=b'b', now=100)
        box.mark_dead(rid1, reason="permanent: 400")
        box.mark_dead(rid2, reason="permanent: 400")
        assert box.dead_count() == 2

        n = box.retry_dead_letters(now=200)
        assert n == 2
        assert box.dead_count() == 0
        assert box.pending_count() == 2

        # And the rows are due immediately (next_attempt_at=200).
        due = box.claim_due(now=200, limit=10)
        assert {r.id for r in due} == {rid1, rid2}


def test_retry_dead_letters_match_ids_filter(tmp_path: Path) -> None:
    """Filter retries to a specific list of match_ids."""
    with Outbox(tmp_path / "x.db") as box:
        r1 = box.enqueue(match_id="fb-wc26-mex-rsa-20260611", updated_at="t1", body=b'a', now=100)
        r2 = box.enqueue(match_id="fb-wc26-bra-hai-20260620", updated_at="t1", body=b'b', now=100)
        r3 = box.enqueue(match_id="fb-wc26-arg-pol-20260626", updated_at="t1", body=b'c', now=100)
        box.mark_dead(r1, reason="x")
        box.mark_dead(r2, reason="y")
        box.mark_dead(r3, reason="z")

        n = box.retry_dead_letters(
            match_ids=["fb-wc26-mex-rsa-20260611", "fb-wc26-bra-hai-20260620"],
            now=200,
        )
        assert n == 2
        # arg-pol stays dead.
        dead = {r.match_id for r in box.list_dead()}
        assert dead == {"fb-wc26-arg-pol-20260626"}


def test_retry_dead_letters_empty_match_ids_list_is_noop(tmp_path: Path) -> None:
    """Passing an empty list explicitly retries nothing — guard against
    accidentally retrying everything when the caller intended a
    filtered call with a runtime-built (and possibly empty) list."""
    with Outbox(tmp_path / "x.db") as box:
        rid = box.enqueue(match_id="m1", updated_at="t1", body=b'a', now=100)
        box.mark_dead(rid, reason="x")
        n = box.retry_dead_letters(match_ids=[], now=200)
        assert n == 0
        assert box.dead_count() == 1


def test_retry_dead_letters_resets_attempts(tmp_path: Path) -> None:
    """Retried rows have `attempts` reset to 0 so the standard backoff
    schedule starts fresh on the next failure."""
    with Outbox(tmp_path / "x.db") as box:
        rid = box.enqueue(match_id="m1", updated_at="t1", body=b'a', now=100)
        box.mark_retry(rid, next_attempt_at=200, last_error="transient")
        box.mark_retry(rid, next_attempt_at=300, last_error="transient again")
        box.mark_dead(rid, reason="permanent")
        # After 2 retries + 1 dead, attempts should be 3.
        row = box.get(rid)
        assert row is not None and row.attempts == 3

        box.retry_dead_letters(now=500)
        row = box.get(rid)
        assert row is not None
        assert row.status == "pending"
        assert row.attempts == 0
        assert row.next_attempt_at == 500
