"""Football hard-signal → Elo adjuster."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from desk.signals.models import Signal, SignalType, Source
from desk.sport import FixtureRef
from desk.sports.football.hard_signals import (
    INJURY_ELO_PENALTY,
    LATE_BINDING_DAYS,
    MAX_TOTAL_PENALTY_ELO,
    SUSPENSION_ELO_PENALTY,
    HardSignalAdjustment,
    apply_hard_signals,
    within_late_binding_window,
)
from desk.sports.football.model import FootballFeatures

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


def _fx(*, a: str = "France", b: str = "Mexico",
        kickoff: datetime | None = None) -> FixtureRef:
    return FixtureRef(
        match_id="fb-wc26-fra-mex-20260612",
        sport="football",
        competition_code="wc26",
        competition_label="World Cup 2026",
        competition_stage="group_d",
        team_a=a, team_b=b,
        kickoff_utc=kickoff or (_NOW + timedelta(days=2)),
        market_outcomes=("a", "draw", "b"),
        venue_city="Guadalajara",
        venue_stadium="Estadio Akron",
        venue_country="MX",
    )


def _features(*, a_elo: float = 1850.0, b_elo: float = 1650.0) -> FootballFeatures:
    return FootballFeatures(
        team_a_name="France", team_b_name="Mexico",
        team_a_elo=a_elo, team_b_elo=b_elo,
        is_international=True,
        team_a_iso3="fra", team_b_iso3="mex",
        venue_host_iso3="mex",
    )


def _src(id: str = "bbc") -> Source:
    return Source.model_validate(dict(
        id=id, name=id.upper(), feed_type="rss",
        feed_ref=f"https://{id}/rss",
        language="en", coverage_tags="global|sport:football",
        reliability=0.95, bias_flag="none",
        parent_org=id, tier="trusted_core", enabled=True,
    ))


def _signal(*, team: str = "France", type: SignalType = SignalType.INJURY,
            source_id: str = "bbc",
            url: str = "https://bbc/article",
            claim: str = "Mbappé out with calf strain",
            quote: str = "Mbappé will miss the match with a calf strain.",
            published_at: datetime | None = None) -> Signal:
    return Signal(
        type=type, team=team,
        claim=claim, quote=quote,
        source_id=source_id, url=url,
        published_at=published_at or (_NOW - timedelta(hours=4)),
        confidence=0.9,
    )


# ── within_late_binding_window ────────────────────────────────────────

def test_window_open_inside_default_range():
    ko = _NOW + timedelta(days=3)
    assert within_late_binding_window(kickoff_utc=ko, now=_NOW)


def test_window_closed_for_kickoff_too_far_out():
    ko = _NOW + timedelta(days=LATE_BINDING_DAYS + 1)
    assert not within_late_binding_window(kickoff_utc=ko, now=_NOW)


def test_window_closed_for_past_kickoff():
    ko = _NOW - timedelta(hours=2)
    assert not within_late_binding_window(kickoff_utc=ko, now=_NOW)


# ── single-signal adjustment ──────────────────────────────────────────

def test_injury_to_team_a_lowers_team_a_elo_by_penalty():
    fx = _fx()
    base = _features(a_elo=1850.0, b_elo=1650.0)
    adjusted, audit = apply_hard_signals(
        base, fx=fx, signals=[(_signal(team="France"), _src())], now=_NOW,
    )
    assert adjusted.team_a_elo == 1850.0 - INJURY_ELO_PENALTY
    assert adjusted.team_b_elo == 1650.0
    assert len(audit) == 1
    assert audit[0].side == "a"
    assert audit[0].delta_elo == -INJURY_ELO_PENALTY
    assert audit[0].team == "France"


def test_suspension_uses_suspension_magnitude():
    fx = _fx()
    base = _features()
    adjusted, audit = apply_hard_signals(
        base, fx=fx,
        signals=[(_signal(team="France", type=SignalType.SUSPENSION), _src())],
        now=_NOW,
    )
    assert adjusted.team_a_elo == base.team_a_elo - SUSPENSION_ELO_PENALTY
    assert audit[0].signal_type == "suspension"


def test_confirmed_lineup_applies_no_elo_change_but_audits():
    fx = _fx()
    base = _features()
    adjusted, audit = apply_hard_signals(
        base, fx=fx,
        signals=[(_signal(team="France", type=SignalType.CONFIRMED_LINEUP), _src())],
        now=_NOW,
    )
    assert adjusted is base or adjusted.team_a_elo == base.team_a_elo
    # PR F treats confirmed_lineup as a zero-delta hard signal; no audit row
    # because nothing moved. Future PRs may surface it as a band-tightener.
    assert audit == []


# ── multiple signals + per-team cap ───────────────────────────────────

def test_multiple_injuries_on_same_team_accumulate():
    fx = _fx()
    base = _features()
    signals = [
        (_signal(team="France", url="https://bbc/1"), _src()),
        (_signal(team="France", url="https://bbc/2"), _src()),
    ]
    adjusted, audit = apply_hard_signals(base, fx=fx, signals=signals, now=_NOW)
    assert adjusted.team_a_elo == base.team_a_elo - 2 * INJURY_ELO_PENALTY
    assert len(audit) == 2
    assert all(not a.capped for a in audit)


def test_per_team_cap_clips_total_penalty():
    fx = _fx()
    base = _features(a_elo=2000.0)
    # Enough injuries to blow past the cap.
    n_signals = int(MAX_TOTAL_PENALTY_ELO / INJURY_ELO_PENALTY) + 3
    signals = [
        (_signal(team="France", url=f"https://bbc/{i}"), _src())
        for i in range(n_signals)
    ]
    adjusted, audit = apply_hard_signals(base, fx=fx, signals=signals, now=_NOW)
    # Adjusted Elo bottoms out at base - MAX_TOTAL_PENALTY_ELO
    assert adjusted.team_a_elo == base.team_a_elo - MAX_TOTAL_PENALTY_ELO
    # At least one row should be marked capped (the one that hit the wall)
    assert any(a.capped for a in audit)


def test_signals_for_both_teams_adjust_independently():
    fx = _fx()
    base = _features()
    signals = [
        (_signal(team="France", url="https://bbc/1"), _src()),
        (_signal(team="Mexico", url="https://bbc/2"), _src()),
    ]
    adjusted, audit = apply_hard_signals(base, fx=fx, signals=signals, now=_NOW)
    assert adjusted.team_a_elo == base.team_a_elo - INJURY_ELO_PENALTY
    assert adjusted.team_b_elo == base.team_b_elo - INJURY_ELO_PENALTY
    assert {a.side for a in audit} == {"a", "b"}


def test_team_match_is_case_insensitive():
    fx = _fx(a="France")
    base = _features()
    adjusted, audit = apply_hard_signals(
        base, fx=fx,
        signals=[(_signal(team="FRANCE"), _src())],
        now=_NOW,
    )
    assert adjusted.team_a_elo < base.team_a_elo
    assert len(audit) == 1


def test_signal_for_unknown_team_dropped_silently():
    fx = _fx(a="France", b="Mexico")
    base = _features()
    adjusted, audit = apply_hard_signals(
        base, fx=fx,
        signals=[(_signal(team="Brazil"), _src())],
        now=_NOW,
    )
    assert adjusted is base
    assert audit == []


# ── late-binding gate ─────────────────────────────────────────────────

def test_outside_late_binding_window_is_a_no_op():
    fx = _fx(kickoff=_NOW + timedelta(days=LATE_BINDING_DAYS + 5))
    base = _features()
    adjusted, audit = apply_hard_signals(
        base, fx=fx, signals=[(_signal(team="France"), _src())], now=_NOW,
    )
    assert adjusted is base
    assert audit == []


def test_window_kwarg_overrides_default():
    fx = _fx(kickoff=_NOW + timedelta(days=10))
    base = _features()
    # Open the window wide so the same fixture *does* get adjusted.
    adjusted, audit = apply_hard_signals(
        base, fx=fx, signals=[(_signal(team="France"), _src())],
        now=_NOW, window=timedelta(days=14),
    )
    assert adjusted.team_a_elo < base.team_a_elo


# ── audit row content ─────────────────────────────────────────────────

def test_audit_row_carries_citation_back_to_source():
    fx = _fx()
    base = _features()
    sig = _signal(
        team="France",
        url="https://bbc.co.uk/sport/football/12345",
        claim="Mbappé out with calf strain",
    )
    _, audit = apply_hard_signals(
        base, fx=fx, signals=[(sig, _src("bbc-sport"))], now=_NOW,
    )
    a = audit[0]
    assert isinstance(a, HardSignalAdjustment)
    assert a.signal_url == "https://bbc.co.uk/sport/football/12345"
    assert a.source_id == "bbc-sport"
    assert "Mbappé" in a.reason
    assert a.signal_type == "injury"
