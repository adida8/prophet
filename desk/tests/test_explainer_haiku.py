"""Tests for the PR 5 Haiku blurb writer.

The real Anthropic client is never invoked here. Tests inject a fake
extractor that returns canned `{title, summary, blurb}` payloads so
the dispatch + post-check logic is exercised in isolation.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from desk.explainer import build_copy
from desk.explainer import haiku
from desk.explainer.stub import Inputs
from desk.publish.contract import Citation


# ── fakes ────────────────────────────────────────────────────────────

class FakeExtractor:
    def __init__(self, payload: dict[str, str] | None) -> None:
        self.payload = payload
        self.calls: list[Inputs] = []

    def write_raw(self, i: Inputs) -> dict[str, str] | None:
        self.calls.append(i)
        return self.payload


def _pick_inputs(**overrides: Any) -> Inputs:
    """Minimal Pick inputs the writer expects."""
    base: Inputs = {
        "state":         "pick",
        "side":          "France",
        "edge_pp":       4.2,
        "market_venue":  "polymarket",
        "price":         "-180",
        "team_a":        "France",
        "team_b":        "Mexico",
        "competition":   "FIFA World Cup 2026",
        "model_p_a":     0.56,
        "model_p_draw":  0.25,
        "model_p_b":     0.19,
        "market_p_a":    0.52,
        "market_p_draw": 0.26,
        "market_p_b":    0.22,
        "editorial_citations": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


# ── post_check ───────────────────────────────────────────────────────

def _good_payload() -> dict[str, str]:
    # ~95-word blurb, no banned phrases, no attribution at all.
    blurb = (
        "France carries an Elo edge that the market hasn't fully priced. "
        "The model rates them at 56% with the closing line at 52% — a "
        "four-point gap that sits at the upper edge of what we treat as "
        "noise. Mexico's home advantage shaves it but doesn't close it: "
        "altitude in Guadalajara isn't the lever a Mexico City fixture "
        "would be. There's no late-binding injury or form signal pulling "
        "the model apart from the market yet. We'll re-evaluate near "
        "kickoff when the confirmed XI lands, and treat the gap as a "
        "selection question rather than a calibration one."
    )
    return {
        "title":   "France v Mexico · the model leans France",
        "summary": (
            "The model rates France at 56% and the market at 52%, a 4pp "
            "gap that clears the Pick threshold."
        ),
        "blurb": blurb,
    }


def test_post_check_passes_clean_payload() -> None:
    assert haiku.post_check(_good_payload(), cites=None) is True


def test_post_check_rejects_banned_phrase() -> None:
    p = _good_payload()
    p["blurb"] = p["blurb"] + " This is a guaranteed result."
    assert haiku.post_check(p, cites=None) is False


def test_post_check_rejects_exclamation() -> None:
    p = _good_payload()
    p["summary"] = p["summary"] + "!"
    assert haiku.post_check(p, cites=None) is False


def test_post_check_rejects_too_short() -> None:
    p = _good_payload()
    p["blurb"] = "Short blurb."
    assert haiku.post_check(p, cites=None) is False


def test_post_check_rejects_too_long() -> None:
    p = _good_payload()
    p["blurb"] = "word " * 300
    assert haiku.post_check(p, cites=None) is False


def test_post_check_rejects_unknown_outlet() -> None:
    p = _good_payload()
    p["blurb"] = p["blurb"] + " The Telegraph reported on the build-up."
    # No citations → any attribution is suspect → reject.
    assert haiku.post_check(p, cites=None) is False


def test_post_check_accepts_known_outlet() -> None:
    p = _good_payload()
    p["blurb"] = p["blurb"] + ' BBC Sport noted "the line is holding."'
    cites = [Citation(
        outlet="BBC Sport",
        url="https://www.bbc.co.uk/sport/football/1",
        quote="the line is holding",
    )]
    assert haiku.post_check(p, cites=cites) is True


def test_post_check_matches_outlet_short_form() -> None:
    """'BBC' should match 'BBC Sport' and vice versa."""
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Per BBC: holding the line."
    cites = [Citation(
        outlet="BBC Sport",
        url="https://www.bbc.co.uk/sport/football/2",
        quote="holding the line",
    )]
    assert haiku.post_check(p, cites=cites) is True


def test_post_check_rejects_outlet_not_in_list() -> None:
    p = _good_payload()
    p["blurb"] = p["blurb"] + " The Telegraph reported on the build-up."
    cites = [Citation(
        outlet="BBC Sport",
        url="https://www.bbc.co.uk/sport/football/3",
        quote="something else",
    )]
    assert haiku.post_check(p, cites=cites) is False


# ── try_haiku_copy ──────────────────────────────────────────────────

def test_try_haiku_copy_returns_copy_on_clean_payload() -> None:
    extractor = FakeExtractor(_good_payload())
    copy = haiku.try_haiku_copy(_pick_inputs(), extractor=extractor)
    assert copy is not None
    assert copy.title.startswith("France v Mexico")
    assert "56%" in copy.summary
    assert len(extractor.calls) == 1


def test_try_haiku_copy_returns_none_when_extractor_yields_none() -> None:
    extractor = FakeExtractor(None)
    assert haiku.try_haiku_copy(_pick_inputs(), extractor=extractor) is None


def test_try_haiku_copy_returns_none_on_voice_fail() -> None:
    bad = _good_payload()
    bad["blurb"] = bad["blurb"] + " You should bet on this match."
    extractor = FakeExtractor(bad)
    assert haiku.try_haiku_copy(_pick_inputs(), extractor=extractor) is None


# ── build_copy dispatch ─────────────────────────────────────────────

def test_build_copy_falls_back_to_stub_when_haiku_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """No DESK_BLURB_HAIKU=1 → stub-only, no API call."""
    monkeypatch.delenv("DESK_BLURB_HAIKU", raising=False)
    copy = build_copy(_pick_inputs())
    # Stub title pattern: "France v Mexico · the model leans France"
    assert "France v Mexico" in copy.title
    # Stub always populates drivers; Haiku does not.
    assert len(copy.drivers) > 0


def test_build_copy_uses_haiku_overlay_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Haiku enabled + payload clean, prose fields come from Haiku.
    Drivers + citations still come from the stub."""
    monkeypatch.setenv("DESK_BLURB_HAIKU", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    extractor = FakeExtractor(_good_payload())
    monkeypatch.setattr(haiku, "_make_default_extractor", lambda: extractor)

    copy = build_copy(_pick_inputs())
    assert copy.title == "France v Mexico · the model leans France"
    assert "56%" in copy.summary
    # Drivers still come from the stub.
    assert len(copy.drivers) > 0


def test_build_copy_falls_back_when_haiku_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_BLURB_HAIKU", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    extractor = FakeExtractor(None)
    monkeypatch.setattr(haiku, "_make_default_extractor", lambda: extractor)

    copy = build_copy(_pick_inputs())
    # Falls back to the stub's templated prose.
    assert "the model leans" in copy.title
    assert any("Elo" in d for d in copy.drivers)


def test_build_copy_falls_back_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """DESK_BLURB_HAIKU=1 but no ANTHROPIC_API_KEY → no Haiku call."""
    monkeypatch.setenv("DESK_BLURB_HAIKU", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    sentinel = {"called": False}

    def boom() -> haiku.BlurbExtractor | None:
        sentinel["called"] = True
        return None

    monkeypatch.setattr(haiku, "_make_default_extractor", boom)
    copy = build_copy(_pick_inputs())
    assert sentinel["called"] is False
    # Stub still ran.
    assert len(copy.drivers) > 0


# ── prompt construction ─────────────────────────────────────────────

def test_user_message_includes_citation_block() -> None:
    cites = [Citation(
        outlet="The Guardian (football)",
        url="https://www.theguardian.com/football/1",
        quote="form is steady",
    )]
    msg = haiku.build_user_message(_pick_inputs(editorial_citations=cites))
    assert "The Guardian (football)" in msg
    assert "form is steady" in msg
    assert "https://www.theguardian.com/football/1" in msg


def test_user_message_empty_citation_section_says_so() -> None:
    msg = haiku.build_user_message(_pick_inputs())
    assert "no editorial citations" in msg.lower()


def test_system_prompt_has_cache_control() -> None:
    system_blocks, _ = haiku.build_messages(_pick_inputs())
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "VOICE" in system_blocks[0]["text"] or "voice" in system_blocks[0]["text"]


# ── parse_tool_use ──────────────────────────────────────────────────

class _Block:
    def __init__(self, *, type: str, name: str | None = None, input: dict | None = None) -> None:
        self.type = type
        self.name = name
        self.input = input


class _Response:
    def __init__(self, blocks: list[_Block]) -> None:
        self.content = blocks


def test_parse_tool_use_returns_payload() -> None:
    resp = _Response([_Block(type="tool_use", name="write_blurb", input={
        "title": "t", "summary": "s", "blurb": "b",
    })])
    assert haiku.parse_tool_use(resp) == {"title": "t", "summary": "s", "blurb": "b"}


def test_parse_tool_use_returns_none_when_tool_missing() -> None:
    resp = _Response([_Block(type="text")])
    assert haiku.parse_tool_use(resp) is None


# ── team news guards (Slice A) ──────────────────────────────────────

from desk.sports.football.team_news import (  # noqa: E402
    LineupStatus, PlayerAbsence, TeamNews,
)


def _team_news(
    *, team: str, materiality: str,
    absences: tuple[PlayerAbsence, ...] = (),
    lineup_state: str = "unknown",
) -> TeamNews:
    return TeamNews(
        team=team, absences=absences,
        lineup=LineupStatus(state=lineup_state),  # type: ignore[arg-type]
        materiality=materiality,  # type: ignore[arg-type]
    )


def _absence(name: str, *, importance: str = "high") -> PlayerAbsence:
    return PlayerAbsence(
        name=name, position="Goalkeeper",
        type="injury", reason=None,
        source="api-football", source_url=None,
        source_name=None,
        importance=importance,  # type: ignore[arg-type]
    )


def test_post_check_passes_when_no_team_news_supplied() -> None:
    # Existing callers (and tests) call post_check without team_news;
    # the guards must default to "nothing to enforce".
    assert haiku.post_check(_good_payload(), cites=None) is True


def test_materiality_high_warns_without_player_name_default_soft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default mode (DESK_TEAM_NEWS_BLURB_REQUIRED unset) → soft fail."""
    monkeypatch.delenv("DESK_TEAM_NEWS_BLURB_REQUIRED", raising=False)
    p = _good_payload()
    news = _team_news(
        team="France", materiality="high",
        absences=(_absence("Maignan"),),
    )
    # Blurb does NOT contain "Maignan" → would fail strict mode but
    # passes soft mode.
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


def test_materiality_high_strict_mode_fails_without_player_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    news = _team_news(
        team="France", materiality="high",
        absences=(_absence("Maignan"),),
    )
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is False


def test_materiality_high_passes_when_player_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Maignan is out of the France squad."
    news = _team_news(
        team="France", materiality="high",
        absences=(_absence("Maignan"),),
    )
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


def test_materiality_high_matches_on_surname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Player name 'Kylian Mbappé' should match surname-only mention."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Mbappé will miss the match."
    news = _team_news(
        team="France", materiality="high",
        absences=(_absence("Kylian Mbappé"),),
    )
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


def test_materiality_none_strict_rejects_availability_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " There are no major injuries to report."
    # Both sides materiality=none.
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


def test_materiality_none_soft_only_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DESK_TEAM_NEWS_BLURB_REQUIRED", raising=False)
    p = _good_payload()
    p["blurb"] = p["blurb"] + " There are no major injuries to report."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    # Soft mode → still True.
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is True


def test_materiality_none_passes_with_clean_blurb() -> None:
    # Default blurb has no availability keywords; both-sides-none is fine.
    p = _good_payload()
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is True


def test_user_message_includes_team_news_block() -> None:
    news = _team_news(
        team="France", materiality="high",
        absences=(_absence("Maignan"),),
    )
    inp = _pick_inputs(team_a_news=news, team_b_news=None)
    msg = haiku.build_user_message(inp)
    assert "team_a_news" in msg
    assert "team_b_news" in msg
    assert "materiality: high" in msg
    assert "Maignan" in msg
    assert "(no data)" in msg  # team_b_news=None marker


def test_system_prompt_mentions_team_news_policy() -> None:
    system_blocks, _ = haiku.build_messages(_pick_inputs())
    text = system_blocks[0]["text"]
    assert "TEAM NEWS POLICY" in text
    assert "materiality" in text


def test_parse_tool_use_returns_none_when_fields_empty() -> None:
    resp = _Response([_Block(type="tool_use", name="write_blurb", input={
        "title": "t", "summary": "", "blurb": "b",
    })])
    assert haiku.parse_tool_use(resp) is None
