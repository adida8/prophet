"""Templated explainer + voice-rule tests."""

from __future__ import annotations

import pytest

from desk.explainer.stub import build_copy
from desk.explainer.voice import (
    BANNED_PHRASES,
    VoiceCheckFailed,
    assert_voice_clean,
    is_voice_clean,
)


# ── Voice rules ───────────────────────────────────────────────────────

def test_clean_text_passes() -> None:
    assert_voice_clean("The model rates France at 46% to win.")
    assert_voice_clean("France versus Mexico — calibration holds.")


@pytest.mark.parametrize("phrase", BANNED_PHRASES)
def test_every_banned_phrase_is_rejected(phrase: str) -> None:
    text = f"This is something — you should {phrase} on this match."
    assert not is_voice_clean(text), f"voice check missed banned phrase: {phrase!r}"


def test_exclamation_rejected() -> None:
    with pytest.raises(VoiceCheckFailed):
        assert_voice_clean("France will win!")


def test_emoji_rejected() -> None:
    with pytest.raises(VoiceCheckFailed):
        assert_voice_clean("Strong pick today 🔥")


# ── Templated copy per state ──────────────────────────────────────────

def _pick_inputs(**overrides) -> dict:
    base = dict(
        state="pick",
        side="France",
        edge_pp=4.2,
        market_venue="polymarket",
        price="-180",
        team_a="France",
        team_b="Mexico",
        competition="FIFA World Cup 2026",
        model_p_a=0.46, model_p_draw=0.25, model_p_b=0.29,
        market_p_a=0.42, market_p_draw=0.27, market_p_b=0.31,
    )
    base.update(overrides)
    return base


def test_pick_copy_mentions_both_probabilities() -> None:
    c = build_copy(_pick_inputs())
    assert c.title and c.summary and c.blurb
    # Reference both model and market probability.
    assert "46%" in c.summary
    assert "42%" in c.summary
    # Edge-pp present.
    assert "+4.2pp" in c.summary or "+4.2 pp" in c.summary or "+4.2" in c.summary


def test_pick_copy_passes_voice_rules() -> None:
    c = build_copy(_pick_inputs())
    for field in (c.title, c.summary, c.blurb):
        assert is_voice_clean(field), f"banned content in: {field!r}"


def test_pass_copy_has_real_text() -> None:
    c = build_copy({
        "state": "pass",
        "team_a": "USA", "team_b": "Canada",
        "competition": "FIFA World Cup 2026",
    })
    assert "Pass" in c.summary
    assert is_voice_clean(c.title)
    assert is_voice_clean(c.summary)
    assert is_voice_clean(c.blurb)


def test_avoid_copy_carries_edge_pp() -> None:
    c = build_copy({
        "state": "avoid",
        "edge_pp": -6.0,
        "team_a": "Manchester United", "team_b": "Liverpool",
        "competition": "Premier League",
    })
    assert "-6.0pp" in c.summary or "−6.0pp" in c.summary
    assert "Avoid" in c.summary
    assert is_voice_clean(c.blurb)


def test_unknown_state_returns_empty_copy() -> None:
    c = build_copy({"state": "unknown", "team_a": "A", "team_b": "B"})
    assert c.title == ""
    assert c.summary == ""
    assert c.blurb == ""


# ── Citations field is empty by default (PR 5 will populate) ─────────

def test_citations_field_remains_empty_in_stub() -> None:
    c = build_copy(_pick_inputs())
    assert c.citations == []


# ── Side="draw" surfaces correctly ───────────────────────────────────

def test_pick_on_draw_uses_share_phrasing() -> None:
    c = build_copy(_pick_inputs(side="draw"))
    assert "share the points" in c.blurb or "draw" in c.summary.lower()
    assert is_voice_clean(c.blurb)
