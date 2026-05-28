"""Selector unit tests — daily + weekly."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from desk.publish.contract import Verdict
from desk.social.selector import (
    build_weekly_roundup,
    daily_draft_id,
    select_daily_pick,
    week_window_for,
    weekly_draft_id,
)


# ── Daily ──────────────────────────────────────────────────────────────


def _kickoff_far(days: int = 7) -> datetime:
    return datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc) + timedelta(days=days)


def _kickoff_past() -> datetime:
    return datetime(2026, 6, 1, 19, 0, tzinfo=timezone.utc)


def test_select_daily_pick_returns_none_when_no_picks(
    fra_mex_pick, usa_can_pass,
) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    out = select_daily_pick([usa_can_pass], now=now, min_edge_pp=2.0)
    assert out is None


def test_select_daily_pick_picks_single_qualifying(fra_mex_pick) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    out = select_daily_pick([fra_mex_pick], now=now, min_edge_pp=2.0)
    assert out is fra_mex_pick


def test_select_daily_pick_filters_below_threshold(fra_mex_pick) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    # fra_mex edge is 4.2pp; min_edge 5.0 should exclude it.
    out = select_daily_pick([fra_mex_pick], now=now, min_edge_pp=5.0)
    assert out is None


def test_select_daily_pick_filters_past_kickoffs(fra_mex_pick) -> None:
    now = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
    out = select_daily_pick([fra_mex_pick], now=now, min_edge_pp=2.0)
    assert out is None


def test_select_daily_pick_idempotency_skips_drafted(fra_mex_pick) -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    out = select_daily_pick(
        [fra_mex_pick], now=now, min_edge_pp=2.0,
        already_drafted_match_ids={fra_mex_pick.match_id},
    )
    assert out is None


def test_select_daily_pick_picks_highest_edge(fra_mex_pick) -> None:
    """Two Picks; selector returns the larger edge_pp."""
    bigger = fra_mex_pick.model_copy(deep=True)
    bigger = bigger.model_copy(update={
        "match_id": "fb-wc26-bra-arg-20260613",
        "team_a":   "Brazil",
        "team_b":   "Argentina",
        "kickoff_utc": datetime(2026, 6, 13, 19, 0, tzinfo=timezone.utc),
        "verdict":  Verdict(
            state="pick",
            side="Brazil",
            market_venue="polymarket",
            price="+150",
            edge_pp=10.5,
            market_url="https://polymarket.com/event/bra-arg",
            model_p=0.55, market_p=0.45,
        ),
    })
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    out = select_daily_pick([fra_mex_pick, bigger], now=now, min_edge_pp=2.0)
    assert out is bigger


def test_select_daily_pick_rejects_naive_now(fra_mex_pick) -> None:
    with pytest.raises(ValueError):
        select_daily_pick([fra_mex_pick],
                          now=datetime(2026, 6, 1, 0, 0),
                          min_edge_pp=2.0)


# ── Weekly ─────────────────────────────────────────────────────────────


def test_week_window_for_sunday_morning() -> None:
    # Sun 2026-06-14 09:00 UTC — closes out the week Mon 06-08 → Sun 06-14.
    # Actually the function closes out the *previous* week (06-01 → 06-07)
    # because the spec says the Sunday job covers the just-completed Mon–Sun.
    now = datetime(2026, 6, 14, 9, 0, tzinfo=timezone.utc)
    w = week_window_for(now)
    assert w.start.date() == date(2026, 6, 1)
    assert w.end.date()   == date(2026, 6, 7)
    assert w.week_starting == date(2026, 6, 1)


def test_week_window_for_midweek() -> None:
    # Wed 2026-06-17 — should still look at last week (Mon 06-08 → Sun 06-14).
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    w = week_window_for(now)
    assert w.start.date() == date(2026, 6, 8)
    assert w.end.date()   == date(2026, 6, 14)


def test_week_window_rejects_naive_now() -> None:
    with pytest.raises(ValueError):
        week_window_for(datetime(2026, 6, 17, 12, 0))


def test_build_weekly_roundup_top_picks_only(fra_mex_pick, usa_can_pass) -> None:
    now = datetime(2026, 6, 21, 9, 0, tzinfo=timezone.utc)
    # fra_mex (2026-06-12) sits inside last week (06-08 → 06-14).
    w = week_window_for(now)
    payload = build_weekly_roundup(
        [fra_mex_pick, usa_can_pass],
        window=w,
        outcome_lookup=lambda mid: None,
    )
    assert payload.week_starting == w.week_starting
    assert len(payload.top_picks) == 1
    assert payload.top_picks[0].match_id == fra_mex_pick.match_id
    assert payload.hit_rate is None
    assert payload.what_we_got_wrong is None


def test_build_weekly_roundup_hit_rate_and_wrong(fra_mex_pick) -> None:
    """Two Picks inside the window; one resolved win, one resolved loss.
    Expect hit_rate=0.5 and what_we_got_wrong to be the losing one."""
    bigger = fra_mex_pick.model_copy(update={
        "match_id": "fb-wc26-bra-arg-20260613",
        "team_a":   "Brazil",
        "team_b":   "Argentina",
        "kickoff_utc": datetime(2026, 6, 13, 19, 0, tzinfo=timezone.utc),
        "verdict":  Verdict(
            state="pick",
            side="Brazil",
            market_venue="polymarket",
            price="+150",
            edge_pp=10.5,
            market_url="https://polymarket.com/event/bra-arg",
            model_p=0.55, market_p=0.45,
        ),
    })

    # Choose `now` such that both kickoffs (06-12 + 06-13) sit inside
    # last week's Mon-Sun. Wednesday 06-17 puts us in the right window.
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    w = week_window_for(now)
    assert w.start.date() == date(2026, 6, 8)

    def lookup(mid: str) -> bool | None:
        if mid == fra_mex_pick.match_id:  return True
        if mid == bigger.match_id:        return False
        return None

    payload = build_weekly_roundup(
        [fra_mex_pick, bigger],
        window=w,
        outcome_lookup=lookup,
    )
    assert payload.hit_rate == 0.5
    assert payload.hit_rate_sample_size == 2
    assert payload.what_we_got_wrong is not None
    assert payload.what_we_got_wrong.match_id == bigger.match_id


def test_build_weekly_roundup_excludes_outside_window(fra_mex_pick) -> None:
    """Pick whose kickoff is outside the window must not appear."""
    far_future_now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    w = week_window_for(far_future_now)
    payload = build_weekly_roundup(
        [fra_mex_pick], window=w, outcome_lookup=lambda mid: None,
    )
    assert payload.top_picks == []


# ── id helpers ─────────────────────────────────────────────────────────


def test_daily_draft_id(fra_mex_pick) -> None:
    now = datetime(2026, 6, 12, 6, 0, tzinfo=timezone.utc)
    s = daily_draft_id(fra_mex_pick, now=now)
    assert s == "soc-daily-20260612-fb-wc26-fra-mex-20260612"


def test_weekly_draft_id() -> None:
    s = weekly_draft_id(date(2026, 6, 1))
    assert s == "soc-weekly_roundup-20260601"
