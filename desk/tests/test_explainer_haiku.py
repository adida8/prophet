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
    # ~95-word blurb, no banned phrases, no attribution at all, no
    # availability keywords (so the materiality=none guard stays quiet).
    blurb = (
        "France carries an Elo edge that the market hasn't fully priced. "
        "The model rates them at 56% with the closing line at 52% — a "
        "four-point gap that sits at the upper edge of what we treat as "
        "noise. Mexico's home advantage shaves it but doesn't close it: "
        "altitude in Guadalajara isn't the lever a Mexico City fixture "
        "would be. The model and the market disagree on the favourite "
        "side, and that disagreement is what flags the Pick. We'll "
        "re-evaluate near kickoff and treat the gap as a selection "
        "question rather than a calibration one."
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
    """As of 2026-05-31, parse_tool_use requires squad_blurb too — the
    tool schema mandates it. A payload missing the field yields None."""
    resp = _Response([_Block(type="tool_use", name="write_blurb", input={
        "title": "t", "summary": "s", "blurb": "b",
        "squad_blurb": "Both squads clean.",
    })])
    assert haiku.parse_tool_use(resp) == {
        "title": "t", "summary": "s", "blurb": "b",
        "squad_blurb": "Both squads clean.",
    }


def test_parse_tool_use_returns_none_when_squad_blurb_missing() -> None:
    """Spec 2026-05-31: squad_blurb is required — payload without it
    is treated as malformed (falls back to stub)."""
    resp = _Response([_Block(type="tool_use", name="write_blurb", input={
        "title": "t", "summary": "s", "blurb": "b",
    })])
    assert haiku.parse_tool_use(resp) is None


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


def test_materiality_none_strict_rejects_negative_player_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec-update 2026-05-31: materiality=none guard now rejects only
    negative CLAIMS ('X is injured', 'ruled out', 'one yellow from a
    ban'), not generic vocabulary. A concrete claim about a player's
    availability when neither side has cached data is a hallucination
    and falls back to the stub in strict mode."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Mbappé is injured for this match."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


def test_materiality_none_soft_only_warns_on_negative_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DESK_TEAM_NEWS_BLURB_REQUIRED", raising=False)
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Mbappé is injured for this match."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    # Soft mode → still True (warning only).
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is True


def test_materiality_none_allows_positive_squad_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec-update 2026-05-31: the no-data case now prompts Haiku for a
    positive squad sentence ('squad picture is clean', 'no flagged
    absences'). Those phrasings MUST pass the materiality=none guard."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    # Each variant the prompt teaches Haiku to use must pass strict mode.
    for positive_sentence in (
        " Both squads come through clean; no late absences flagged.",
        " Neither side carries any flagged availability concerns into kickoff.",
        " Squad picture is straightforward — nothing flagged either way.",
        " Both sides arrive ready, no late concerns surfaced.",
        " No flagged absences on either side.",
        " Both sides at full strength as far as we know.",
    ):
        p = _good_payload()
        p["blurb"] = p["blurb"] + positive_sentence
        assert haiku.post_check(
            p, cites=None, team_a_news=none_a, team_b_news=none_b,
        ) is True, f"strict guard rejected positive sentence: {positive_sentence!r}"


def test_materiality_none_strict_rejects_ruled_out_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " A defender has been ruled out of the match."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


def test_materiality_none_strict_rejects_hallucinated_card_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even in materiality=none, claiming a player is 'one yellow from a
    ban' is a hallucination — we have no cards data."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Their captain is one yellow from a suspension."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


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


# ── starter highlights (Slice B / N4b) ──────────────────────────────

def _team_news_with_lineup(
    *, team: str, starters: tuple[str, ...] = (),
    formation: str | None = None, materiality: str = "none",
) -> TeamNews:
    return TeamNews(
        team=team, absences=(),
        lineup=LineupStatus(
            state="confirmed" if starters or formation else "unknown",  # type: ignore[arg-type]
            formation=formation,
            starters=starters,
            source="api-football" if starters else None,
        ),
        materiality=materiality,  # type: ignore[arg-type]
    )


def test_user_message_includes_starters_when_lineup_confirmed() -> None:
    news = _team_news_with_lineup(
        team="Brazil",
        starters=("Alisson", "Neymar", "Vinicius Jr"),
        formation="4-2-3-1",
    )
    inp = _pick_inputs(team_a_news=news, team_b_news=None)
    msg = haiku.build_user_message(inp)
    assert "starters: Alisson, Neymar, Vinicius Jr" in msg
    assert "formation: 4-2-3-1" in msg
    assert "state: confirmed" in msg


def test_system_prompt_mandates_naming_starters() -> None:
    system_blocks, _ = haiku.build_messages(_pick_inputs())
    text = system_blocks[0]["text"]
    # Sample assertions on the new prompt sections.
    assert "starters" in text
    assert "Neymar" in text or "Mbapp" in text  # name examples


def test_post_check_confirmed_lineup_strict_requires_starter_or_formation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When lineup.state=confirmed AND starters present, blurb must
    mention a starter OR a lineup hook word."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    news = _team_news_with_lineup(
        team="Brazil", starters=("Neymar", "Vinicius Jr"),
        formation="4-2-3-1",
    )
    # Blurb does NOT mention any starter or lineup hook.
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is False


def test_post_check_confirmed_lineup_passes_when_starter_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Neymar opens for Brazil from a 4-2-3-1."
    news = _team_news_with_lineup(
        team="Brazil", starters=("Neymar", "Vinicius Jr"),
        formation="4-2-3-1",
    )
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


def test_post_check_confirmed_lineup_passes_on_formation_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Brazil set up in a 4-2-3-1 formation."
    news = _team_news_with_lineup(
        team="Brazil", starters=("Neymar",), formation="4-2-3-1",
    )
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


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


# ── squad-paragraph guards (Q3) ─────────────────────────────────────

from desk.sports.football.team_news import CardStatus  # noqa: E402


def _team_news_with_cards(
    *, team: str, card_names: tuple[str, ...] = (),
    materiality: str = "low",
) -> TeamNews:
    cards = tuple(
        CardStatus(
            name=n, position="Midfielder",
            yellows=1, state="at_risk",
            source="api-football", source_url=None,
            source_name=None, importance="medium",
        )
        for n in card_names
    )
    return TeamNews(
        team=team, absences=(),
        lineup=LineupStatus(state="unknown"),
        materiality=materiality,   # type: ignore[arg-type]
        cards=cards,
    )


def test_system_prompt_has_squad_paragraph_section() -> None:
    system_blocks, _ = haiku.build_messages(_pick_inputs())
    text = system_blocks[0]["text"]
    # Renamed 2026-05-31: squad content now lives in its own
    # `squad_blurb` field, and the prompt section is titled "SQUAD BLURB".
    assert "SQUAD BLURB" in text
    # Card-specific instructions land in the prompt too.
    assert "at-risk" in text.lower() or "at_risk" in text.lower()
    assert "one booking" in text.lower() or "one yellow" in text.lower()


def test_system_prompt_has_no_data_positive_case() -> None:
    """Spec-update 2026-05-31: the prompt MUST instruct Haiku to write
    a positive squad sentence when both sides have no availability
    data. Without that instruction, Haiku falls back to silence and the
    operator never sees a squad paragraph on most matches pre-tournament."""
    system_blocks, _ = haiku.build_messages(_pick_inputs())
    text = system_blocks[0]["text"]
    # Mandate language: explicit no-data case.
    assert "no-data case" in text.lower() or "no data" in text.lower()
    # At least one positive example phrase the prompt teaches.
    positives = ["clean", "no flagged absences", "at full strength",
                 "no late concerns", "ready"]
    assert any(p in text.lower() for p in positives), \
        "prompt must include positive-vocabulary examples for the no-data case"


def test_user_message_includes_cards_block() -> None:
    news = _team_news_with_cards(team="France", card_names=("Tchouaméni",))
    inp = _pick_inputs(team_a_news=news, team_b_news=None)
    msg = haiku.build_user_message(inp)
    assert "cards:" in msg
    assert "Tchouaméni" in msg
    assert "state: at_risk" in msg


def test_user_message_empty_cards_block_marker() -> None:
    """Both sides absent cards → block still rendered with explicit marker."""
    news = _team_news(team="France", materiality="none")
    inp = _pick_inputs(team_a_news=news, team_b_news=None)
    msg = haiku.build_user_message(inp)
    assert "[] (no at-risk players)" in msg


def test_materiality_none_strict_catches_at_risk_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The materiality=none guard catches a hallucinated at-risk story:
    'at risk', 'one booking', 'one yellow', 'yellow accumulation' are
    now in the availability keyword set."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " A defender is at risk of a suspension."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


def test_materiality_none_strict_catches_one_booking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " One booking from a ban is on the cards."
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


def test_at_risk_player_named_as_banned_fails_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §Q3 post-check: an at-risk player must not be presented as
    a confirmed ban. Word 'suspended' next to the player's name = fail."""
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Tchouaméni is suspended for the match."
    news = _team_news_with_cards(team="France", card_names=("Tchouaméni",))
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is False


def test_at_risk_player_phrased_as_risk_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DESK_TEAM_NEWS_BLURB_REQUIRED", "1")
    p = _good_payload()
    p["blurb"] = (
        p["blurb"] + " Tchouaméni carries one yellow into the match."
    )
    news = _team_news_with_cards(team="France", card_names=("Tchouaméni",))
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


def test_at_risk_guard_soft_mode_only_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default mode (DESK_TEAM_NEWS_BLURB_REQUIRED unset) → soft."""
    monkeypatch.delenv("DESK_TEAM_NEWS_BLURB_REQUIRED", raising=False)
    p = _good_payload()
    p["blurb"] = p["blurb"] + " Tchouaméni is banned for the match."
    news = _team_news_with_cards(team="France", card_names=("Tchouaméni",))
    # Soft mode → True even with the violation logged.
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is True


def test_word_budget_blurb_stays_220_now_that_squad_is_separate() -> None:
    """Spec 2026-05-31: squad content moved to its own `squad_blurb`
    field, so the main blurb's ceiling stays 220 regardless of
    team_news content. Anything over 220 → reject."""
    p = _good_payload()
    p["blurb"] = " ".join(["word"] * 235)   # over the 220 cap
    news = _team_news_with_lineup(
        team="France", starters=("Mbappé",), formation="4-3-3",
    )
    assert haiku.post_check(
        p, cites=None, team_a_news=news, team_b_news=None,
    ) is False


def test_word_budget_stays_220_when_no_squad_content() -> None:
    """Without squad content (or with — the rule is the same now), the
    ceiling stays 220."""
    p = _good_payload()
    long_blurb = " ".join(["word"] * 235)
    p["blurb"] = long_blurb
    none_a = _team_news(team="France", materiality="none")
    none_b = _team_news(team="Mexico", materiality="none")
    assert haiku.post_check(
        p, cites=None, team_a_news=none_a, team_b_news=none_b,
    ) is False


def test_squad_blurb_word_budget_rejects_too_long() -> None:
    """squad_blurb caps at 120 words (1-4 sentences). Anything over
    falls back to the stub."""
    p = _good_payload()
    p["squad_blurb"] = " ".join(["word"] * 150)
    assert haiku.post_check(p, cites=None) is False


def test_squad_blurb_word_budget_rejects_too_short() -> None:
    """squad_blurb has a small min (8 words) so a one-word fragment
    or empty-ish response doesn't slip through."""
    p = _good_payload()
    p["squad_blurb"] = "Clean."
    assert haiku.post_check(p, cites=None) is False


def test_squad_blurb_word_budget_passes_typical() -> None:
    p = _good_payload()
    p["squad_blurb"] = (
        "Both squads come through clean — no late absences flagged "
        "either way ahead of kickoff."
    )
    assert haiku.post_check(p, cites=None) is True


def test_squad_blurb_voice_rules_apply() -> None:
    """Banned phrases / exclamations / emoji in squad_blurb → fall back."""
    p = _good_payload()
    p["squad_blurb"] = "Both squads at full strength and ready to go!"
    # Exclamation mark fails voice check.
    assert haiku.post_check(p, cites=None) is False
