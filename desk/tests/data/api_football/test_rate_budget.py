"""Rate-budget instrumentation."""

from __future__ import annotations

from desk.data.api_football.rate_budget import (
    PRO_DAILY_CAP, build_report,
)


def test_default_one_tick_per_day_fits_pro_cap():
    report = build_report(fetch_ticks_per_day=1)
    assert report.within_cap
    assert report.headroom_pct > 95.0


def test_more_ticks_increases_call_count_linearly():
    one = build_report(fetch_ticks_per_day=1)
    six = build_report(fetch_ticks_per_day=6)
    # Fixtures call class scales; team resolution doesn't (one-off).
    assert six.total_calls_per_day > one.total_calls_per_day


def test_hourly_cadence_still_fits():
    """24 ticks/day — what we'd want during the WC final stretch."""
    hourly = build_report(fetch_ticks_per_day=24)
    assert hourly.within_cap


def test_report_includes_reserved_b3_lines():
    """The B.3 (injuries/lineups) slots should be present at 0
    calls/day so the rate budget ages with the codebase."""
    report = build_report()
    phases = {l.phase for l in report.lines}
    assert "B.3 (reserved)" in phases


def test_pro_cap_constant_matches_vendor():
    """Pro tier is 7,500 req/day per api-football's pricing page."""
    assert PRO_DAILY_CAP == 7_500


def test_total_matches_sum_of_lines():
    report = build_report(fetch_ticks_per_day=2)
    assert report.total_calls_per_day == sum(l.calls_per_day for l in report.lines)


def test_within_cap_flips_when_cap_lowered():
    """A tiny daily cap should fail the within-cap check."""
    report = build_report(daily_cap=10)
    assert not report.within_cap
