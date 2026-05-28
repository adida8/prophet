"""SocialQueue tests — schema, idempotency, state machine."""

from __future__ import annotations

import hashlib
import pytest
from datetime import date
from pathlib import Path

from desk.social.models import DraftKind, DraftStatus, SlideAsset, can_transition
from desk.social.queue import (
    Draft,
    DraftNotFound,
    InvalidTransition,
    SocialQueue,
)


def _slide(n: int, tmp: Path) -> SlideAsset:
    p = tmp / f"slide-{n}.png"
    payload = f"slide-{n}".encode()
    p.write_bytes(payload)
    return SlideAsset(
        slide_no=n,
        png_path=p,
        png_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _slides(tmp: Path) -> list[SlideAsset]:
    return [_slide(i, tmp) for i in (1, 2, 3, 4)]


# ── Insert + read ──────────────────────────────────────────────────────


def test_insert_and_read_daily(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        d = q.insert(
            draft_id="soc-daily-20260612-fb-wc26-fra-mex-20260612",
            kind=DraftKind.DAILY,
            match_id="fb-wc26-fra-mex-20260612",
            week_starting=None,
            source_json={"hello": "world"},
            slides=_slides(tmp_path),
            caption_ig="ig",
            caption_x="x",
        )
        assert d.status == DraftStatus.PENDING
        assert d.match_id == "fb-wc26-fra-mex-20260612"
        assert len(d.slides) == 4

        rt = q.get_or_raise(d.draft_id)
        assert rt.caption_ig == "ig"
        assert rt.caption_x  == "x"
        assert rt.slides[0].png_path == tmp_path / "slide-1.png"


def test_insert_weekly_requires_week_starting(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        with pytest.raises(ValueError):
            q.insert(
                draft_id="soc-weekly-20260601",
                kind=DraftKind.WEEKLY_ROUNDUP,
                match_id=None,
                week_starting=None,
                source_json={},
                slides=_slides(tmp_path),
                caption_ig="ig", caption_x="x",
            )


def test_insert_daily_requires_match_id(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        with pytest.raises(ValueError):
            q.insert(
                draft_id="soc-daily-foo",
                kind=DraftKind.DAILY,
                match_id=None,
                week_starting=None,
                source_json={},
                slides=_slides(tmp_path),
                caption_ig="ig", caption_x="x",
            )


def test_insert_rejects_wrong_slide_count(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        with pytest.raises(ValueError):
            q.insert(
                draft_id="soc-daily-foo",
                kind=DraftKind.DAILY,
                match_id="fb-x-a-b-20260101",
                week_starting=None,
                source_json={},
                slides=_slides(tmp_path)[:3],
                caption_ig="ig", caption_x="x",
            )


# ── Idempotency ────────────────────────────────────────────────────────


def test_daily_uniqueness_per_match(tmp_path: Path) -> None:
    import sqlite3
    with SocialQueue(tmp_path / "q.db") as q:
        q.insert(
            draft_id="soc-daily-20260612-fb-wc26-fra-mex-20260612",
            kind=DraftKind.DAILY,
            match_id="fb-wc26-fra-mex-20260612",
            week_starting=None,
            source_json={}, slides=_slides(tmp_path),
            caption_ig="ig", caption_x="x",
        )
        assert q.has_daily_for_match("fb-wc26-fra-mex-20260612")
        with pytest.raises(sqlite3.IntegrityError):
            q.insert(
                draft_id="soc-daily-20260612-dup",
                kind=DraftKind.DAILY,
                match_id="fb-wc26-fra-mex-20260612",
                week_starting=None,
                source_json={}, slides=_slides(tmp_path),
                caption_ig="ig", caption_x="x",
            )


def test_weekly_uniqueness_per_week(tmp_path: Path) -> None:
    import sqlite3
    with SocialQueue(tmp_path / "q.db") as q:
        q.insert(
            draft_id="soc-weekly-20260608",
            kind=DraftKind.WEEKLY_ROUNDUP,
            match_id=None,
            week_starting=date(2026, 6, 8).isoformat(),
            source_json={}, slides=_slides(tmp_path),
            caption_ig="ig", caption_x="x",
        )
        assert q.has_weekly_for(date(2026, 6, 8).isoformat())
        with pytest.raises(sqlite3.IntegrityError):
            q.insert(
                draft_id="soc-weekly-20260608-dup",
                kind=DraftKind.WEEKLY_ROUNDUP,
                match_id=None,
                week_starting=date(2026, 6, 8).isoformat(),
                source_json={}, slides=_slides(tmp_path),
                caption_ig="ig", caption_x="x",
            )


# ── State machine ──────────────────────────────────────────────────────


def _setup_pending(q: SocialQueue, tmp: Path, *, draft_id: str = "soc-daily-x",
                   match_id: str = "fb-wc26-fra-mex-20260612") -> Draft:
    return q.insert(
        draft_id=draft_id,
        kind=DraftKind.DAILY,
        match_id=match_id,
        week_starting=None,
        source_json={}, slides=_slides(tmp),
        caption_ig="ig", caption_x="x",
    )


def test_pending_to_approved(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        d = q.transition("soc-daily-x", to=DraftStatus.APPROVED, by="alice")
        assert d.status == DraftStatus.APPROVED
        assert d.decided_by == "alice"


def test_pending_to_published_is_illegal(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        with pytest.raises(InvalidTransition):
            q.transition("soc-daily-x", to=DraftStatus.PUBLISHED, by="alice")


def test_approved_to_published(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        q.transition("soc-daily-x", to=DraftStatus.APPROVED, by="a")
        d = q.transition("soc-daily-x", to=DraftStatus.PUBLISHED, by="a",
                          ig_permalink="https://ig/p/abc",
                          x_tweet_id="42")
        assert d.status == DraftStatus.PUBLISHED
        assert d.ig_permalink == "https://ig/p/abc"
        assert d.x_tweet_id == "42"
        assert d.published_at is not None


def test_terminal_states_have_no_legal_exit(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        q.transition("soc-daily-x", to=DraftStatus.REJECTED, by="a")
        with pytest.raises(InvalidTransition):
            q.transition("soc-daily-x", to=DraftStatus.APPROVED, by="a")
        with pytest.raises(InvalidTransition):
            q.transition("soc-daily-x", to=DraftStatus.PENDING, by="a")


def test_publish_failed_can_recover(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        q.transition("soc-daily-x", to=DraftStatus.APPROVED, by="a")
        q.transition("soc-daily-x", to=DraftStatus.PUBLISH_FAILED, by="a",
                      publish_error="rate limit")
        d = q.transition("soc-daily-x", to=DraftStatus.APPROVED, by="a")
        assert d.status == DraftStatus.APPROVED


def test_get_or_raise(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        with pytest.raises(DraftNotFound):
            q.get_or_raise("nope")


# ── Caption editor ─────────────────────────────────────────────────────


def test_edit_caption_writes_history(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        d = q.edit_caption("soc-daily-x", platform="ig",
                            new_text="new IG body", by="alice")
        assert d.caption_ig == "new IG body"
        assert d.caption_x  == "x"
        assert len(d.edit_history) == 1
        assert d.edit_history[0]["field"] == "caption_ig"
        assert d.edit_history[0]["before"] == "ig"
        assert d.edit_history[0]["after"]  == "new IG body"


def test_edit_caption_locked_on_terminal(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        q.transition("soc-daily-x", to=DraftStatus.REJECTED, by="a")
        with pytest.raises(InvalidTransition):
            q.edit_caption("soc-daily-x", platform="ig",
                            new_text="trying", by="alice")


def test_edit_caption_bad_platform(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path)
        with pytest.raises(ValueError):
            q.edit_caption("soc-daily-x", platform="twitter",
                            new_text="x", by="a")


# ── List + filter ──────────────────────────────────────────────────────


def test_list_by_status_filters(tmp_path: Path) -> None:
    with SocialQueue(tmp_path / "q.db") as q:
        _setup_pending(q, tmp_path,
                        draft_id="d1", match_id="fb-wc26-fra-mex-20260612")
        _setup_pending(q, tmp_path,
                        draft_id="d2", match_id="fb-wc26-bra-arg-20260613")
        q.transition("d1", to=DraftStatus.APPROVED, by="a")

        pending  = q.list_by_status(status=DraftStatus.PENDING)
        approved = q.list_by_status(status=DraftStatus.APPROVED)
        assert {p.draft_id for p in pending}  == {"d2"}
        assert {p.draft_id for p in approved} == {"d1"}


# ── Helper test ────────────────────────────────────────────────────────


def test_can_transition_matrix() -> None:
    assert can_transition(DraftStatus.PENDING, DraftStatus.APPROVED)
    assert can_transition(DraftStatus.PENDING, DraftStatus.REJECTED)
    assert can_transition(DraftStatus.PENDING, DraftStatus.SKIPPED)
    assert can_transition(DraftStatus.APPROVED, DraftStatus.PUBLISHED)
    assert can_transition(DraftStatus.APPROVED, DraftStatus.PUBLISH_FAILED)
    assert can_transition(DraftStatus.PUBLISH_FAILED, DraftStatus.APPROVED)

    assert not can_transition(DraftStatus.PENDING, DraftStatus.PUBLISHED)
    assert not can_transition(DraftStatus.REJECTED, DraftStatus.APPROVED)
    assert not can_transition(DraftStatus.SKIPPED, DraftStatus.APPROVED)
    assert not can_transition(DraftStatus.PUBLISHED, DraftStatus.APPROVED)
