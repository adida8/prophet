"""Drafter runner integration tests — end-to-end through queue + renderer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from desk.social import SocialQueue
from desk.social.runner import draft_daily, draft_weekly, stub_outcome_lookup
from desk.social.models import DraftKind, DraftStatus


def test_draft_daily_persists_through_queue(fra_mex_pick, tmp_path: Path) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    with SocialQueue(tmp_path / "q.db") as q:
        draft = draft_daily(
            queue=q,
            assets_dir=tmp_path / "assets",
            matches=[fra_mex_pick],
            now=now,
        )
        assert draft is not None
        assert draft.kind == DraftKind.DAILY
        assert draft.match_id == fra_mex_pick.match_id
        assert draft.status == DraftStatus.PENDING
        assert len(draft.slides) == 4
        for s in draft.slides:
            assert s.png_path.is_file()


def test_draft_daily_idempotent_on_rerun(fra_mex_pick, tmp_path: Path) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    with SocialQueue(tmp_path / "q.db") as q:
        first  = draft_daily(queue=q, assets_dir=tmp_path / "assets",
                               matches=[fra_mex_pick], now=now)
        second = draft_daily(queue=q, assets_dir=tmp_path / "assets",
                               matches=[fra_mex_pick], now=now)
        assert first is not None
        assert second is None


def test_draft_daily_returns_none_when_no_picks(usa_can_pass, tmp_path: Path) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    with SocialQueue(tmp_path / "q.db") as q:
        d = draft_daily(queue=q, assets_dir=tmp_path / "assets",
                         matches=[usa_can_pass], now=now)
        assert d is None


def test_draft_weekly_persists(fra_mex_pick, tmp_path: Path) -> None:
    # 2026-06-17 (Wed) → trailing week 06-08..06-14 covers fra_mex (06-12).
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    with SocialQueue(tmp_path / "q.db") as q:
        draft = draft_weekly(
            queue=q, assets_dir=tmp_path / "assets",
            outcome_lookup=stub_outcome_lookup,
            matches=[fra_mex_pick], now=now,
        )
        assert draft is not None
        assert draft.kind == DraftKind.WEEKLY_ROUNDUP
        assert draft.week_starting == "2026-06-08"
        assert draft.status == DraftStatus.PENDING


def test_draft_weekly_skips_empty_window(usa_can_pass, tmp_path: Path) -> None:
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    with SocialQueue(tmp_path / "q.db") as q:
        d = draft_weekly(
            queue=q, assets_dir=tmp_path / "assets",
            outcome_lookup=stub_outcome_lookup,
            matches=[usa_can_pass], now=now,
        )
        assert d is None


def test_draft_weekly_idempotent_on_rerun(fra_mex_pick, tmp_path: Path) -> None:
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    with SocialQueue(tmp_path / "q.db") as q:
        first  = draft_weekly(queue=q, assets_dir=tmp_path / "assets",
                                outcome_lookup=stub_outcome_lookup,
                                matches=[fra_mex_pick], now=now)
        second = draft_weekly(queue=q, assets_dir=tmp_path / "assets",
                                outcome_lookup=stub_outcome_lookup,
                                matches=[fra_mex_pick], now=now)
        assert first is not None
        assert second is None
