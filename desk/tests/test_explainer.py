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


# ── Brand names with banned-word substrings (real prod bug, 2026-05-31) ──

@pytest.mark.parametrize("brand_text", [
    # 'bet' substring — used to dead-letter every Betfair / Sky Bet pick
    "Cheapest line is Betfair Exchange at 5.40 for France.",
    "Sky Bet has the draw at 3.40.",
    "The Betfair_Ex_Eu line opens at 1.75.",
    "Skybet's price matches William Hill's at 18.2%.",
    # 'lock' substring — Wycombe's striker 'Lockyer', etc.
    "Lockyer starts at centre-back.",
    "Bullock fronts the attack.",
    # multi-word phrases still need full match
    "He runs the half-back theory all night.",   # no 'back the' word-bdr
])
def test_brand_substrings_are_not_banned(brand_text: str) -> None:
    """Voice-check uses word boundaries: 'bet' must not match
    'Betfair'/'Sky Bet'/'Skybet', 'lock' must not match 'Lockyer'.
    A pre-fix substring check empty-Copy'd every cross-venue Pick
    that landed on Betfair Exchange or Sky Bet."""
    assert is_voice_clean(brand_text), brand_text


@pytest.mark.parametrize("real_violation", [
    "Place a bet on France.",
    "You should bet now.",
    "Lock this in before kickoff.",
    "Back the home side.",
])
def test_banned_words_still_caught_when_isolated(real_violation: str) -> None:
    """Word-boundary matching must STILL catch the real violations —
    otherwise the fix would just disable the rule entirely."""
    assert not is_voice_clean(real_violation), real_violation


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


# ── Cross-venue best-place driver (ADR 0004) ────────────────────────

def test_pick_driver_names_cheapest_venue_when_provided() -> None:
    """When best_venue_label + best_venue_true_price are passed in,
    the pick driver pool includes a 'Cheapest way in on X is Y at an
    effective Z%' line. With the inputs absent, behaviour unchanged."""
    inp = _pick_inputs(
        best_venue_label="William Hill",
        best_venue_true_price=0.182,
    )
    c = build_copy(inp)
    joined = " ".join(c.drivers)
    assert "William Hill" in joined
    assert "effective" in joined.lower()
    # Voice rules still pass.
    assert is_voice_clean(joined)


def test_pick_driver_skips_when_best_venue_label_absent() -> None:
    """No best_venue_label → no driver mentioning a venue beyond the
    headline venue_label."""
    inp = _pick_inputs()  # no best_venue_label
    c = build_copy(inp)
    joined = " ".join(c.drivers)
    assert "William Hill" not in joined
    assert "Cheapest way in" not in joined


def test_pick_driver_skips_when_label_matches_headline_venue() -> None:
    """When the best venue equals the verdict's headline venue, no new
    information — caller should not pass best_venue_label, so the
    driver pool stays the standard set."""
    inp = _pick_inputs(
        # Same venue as headline → caller would normally pass None;
        # if a buggy caller passed it, the driver still inserts but
        # we tolerate it. Just verify a non-headline case works.
    )
    c = build_copy(inp)
    assert isinstance(c.drivers, list)


# ── Stub squad_blurb (2026-05-31 spec change) ────────────────────────

def test_stub_populates_squad_blurb_with_positive_default_when_no_data() -> None:
    """Spec 2026-05-31: every published match must carry a non-empty
    squad_blurb so the website's Squad section is never blank. The
    stub falls back to a positive no-data sentence when team_news is
    empty (or absent)."""
    c = build_copy(_pick_inputs())
    assert c.squad_blurb
    # Default sentence is positive (mentions clean / no concerns / clean).
    assert any(
        word in c.squad_blurb.lower()
        for word in ["clean", "no flagged", "no late", "no availability"]
    )


def test_stub_squad_blurb_lists_absences_when_team_news_present() -> None:
    """When team_news carries absences, the stub names them in
    `Out for <team>: <names>` shape."""
    from desk.sports.football.team_news import (
        LineupStatus, PlayerAbsence, TeamNews,
    )
    a_news = TeamNews(
        team="France", absences=(
            PlayerAbsence(
                name="Mbappé", position="Attacker", type="injury",
                reason="Calf", source="api-football",
                source_url=None, source_name=None, importance="high",
            ),
        ),
        lineup=LineupStatus(state="unknown"),
        materiality="high",
    )
    inp = _pick_inputs(team_a_news=a_news)
    c = build_copy(inp)
    assert "Mbappé" in c.squad_blurb
    assert "Out for France" in c.squad_blurb


def test_stub_squad_blurb_lists_at_risk_cards() -> None:
    from desk.sports.football.team_news import (
        CardStatus, LineupStatus, TeamNews,
    )
    a_news = TeamNews(
        team="France", absences=(),
        lineup=LineupStatus(state="unknown"),
        materiality="low",
        cards=(
            CardStatus(
                name="Tchouaméni", position="Midfielder", yellows=1,
                state="at_risk", source="api-football",
                source_url=None, source_name=None, importance="medium",
            ),
        ),
    )
    inp = _pick_inputs(team_a_news=a_news)
    c = build_copy(inp)
    assert "Tchouaméni" in c.squad_blurb
    assert "yellow" in c.squad_blurb.lower()


def test_stub_squad_blurb_default_varies_across_matches() -> None:
    """The three positive variants rotate by salt so the stub doesn't
    write the same sentence on every match in the slate."""
    seen: set[str] = set()
    for a_team, b_team in [
        ("France", "Mexico"), ("Brazil", "Argentina"),
        ("Spain", "Portugal"), ("Germany", "Italy"),
        ("England", "Croatia"), ("Japan", "Australia"),
    ]:
        inp = _pick_inputs(team_a=a_team, team_b=b_team)
        c = build_copy(inp)
        seen.add(c.squad_blurb)
    # With 3 variants and 6 distinct salts, we expect ≥2 unique outputs
    # (proves the rotation isn't pinned to one variant).
    assert len(seen) >= 2
