"""Caption tests — templates, length caps, voice gates, citation lockstep."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from desk.publish.contract import Citation, Copy, Verdict
from desk.social.caption import (
    IG_MAX_CHARS,
    X_MAX_CHARS,
    SOCIAL_BANNED_PHRASES,
    generate_daily_captions,
    generate_weekly_captions,
)
from desk.social.models import (
    ResolvedPick,
    RoundupPick,
    WeeklyRoundupPayload,
)


# ── Daily captions ─────────────────────────────────────────────────────


def test_ig_caption_contains_title_link_brand(fra_mex_pick) -> None:
    out = generate_daily_captions(fra_mex_pick)
    assert "France v Mexico" in out.caption_ig
    assert "oddsprimer.com/m/fb-wc26-fra-mex-20260612" in out.caption_ig
    assert "— The Desk" in out.caption_ig
    assert not out.fell_back


def test_ig_caption_hashtag_set(fra_mex_pick) -> None:
    out = generate_daily_captions(fra_mex_pick)
    for tag in ("#oddsprimer", "#worldcup2026", "#wc2026",
                "#predictionmarkets", "#france", "#mexico"):
        assert tag in out.caption_ig


def test_ig_caption_under_cap(fra_mex_pick) -> None:
    # Inflate the blurb to push past IG cap (2200 chars); templates
    # must truncate cleanly. Blurb contract max is 4000 chars.
    inflated = fra_mex_pick.model_copy(update={
        "copy": Copy(
            title=fra_mex_pick.copy.title,
            summary=fra_mex_pick.copy.summary,
            blurb=("paragraph. " * 350),   # ~3500 chars, > IG cap
            citations=fra_mex_pick.copy.citations,
            drivers=list(fra_mex_pick.copy.drivers),
        ),
    })
    out = generate_daily_captions(inflated)
    assert len(out.caption_ig) <= IG_MAX_CHARS


def test_x_caption_under_cap(fra_mex_pick) -> None:
    out = generate_daily_captions(fra_mex_pick)
    assert len(out.caption_x) <= X_MAX_CHARS
    assert "oddsprimer.com" in out.caption_x


def test_x_caption_drops_body_when_too_long(fra_mex_pick) -> None:
    """A long title should make the body line get dropped, with the
    title + link still under the cap. Copy.title contract caps at 120
    chars, so we use a title near that limit."""
    long_title = "France v Mexico — a deep look at the case for each side abc " * 2  # ~120 chars
    long_title = long_title[:120]
    long_match = fra_mex_pick.model_copy(update={
        "copy": Copy(
            title=long_title,
            summary=fra_mex_pick.copy.summary,
            blurb=fra_mex_pick.copy.blurb,
        ),
    })
    out = generate_daily_captions(long_match)
    assert len(out.caption_x) <= X_MAX_CHARS


def test_voice_check_falls_back_on_banned_phrase(fra_mex_pick) -> None:
    """If the blurb includes 'bet now', captions fall back to minimal form."""
    poisoned = fra_mex_pick.model_copy(update={
        "copy": Copy(
            title="bet now on France",
            summary="bet now",
            blurb="bet now",
        ),
    })
    out = generate_daily_captions(poisoned)
    assert out.fell_back
    assert "oddsprimer.com/m/" in out.caption_ig
    assert "oddsprimer.com/m/" in out.caption_x


def test_voice_check_falls_back_on_emoji(fra_mex_pick) -> None:
    poisoned = fra_mex_pick.model_copy(update={
        "copy": Copy(title="🔥 hot pick", summary="", blurb=""),
    })
    out = generate_daily_captions(poisoned)
    assert out.fell_back


def test_voice_check_falls_back_on_exclamation(fra_mex_pick) -> None:
    poisoned = fra_mex_pick.model_copy(update={
        "copy": Copy(title="France will win!", summary="", blurb=""),
    })
    out = generate_daily_captions(poisoned)
    assert out.fell_back


def test_social_banned_phrases_all_caught() -> None:
    """Every SOCIAL_BANNED_PHRASES entry must actually trigger fallback."""
    # `lock` is multi-context; we already test via voice rules elsewhere,
    # but the whole-word matcher should reject 'lock the line' here.
    from desk.publish.contract import Citation
    base = {
        "match_id": "fb-wc26-fra-mex-20260612",
        "sport":    "football",
    }
    # Reuse the fra_mex_pick shape via a minimal fixture re-creation.
    from desk.publish.contract import (
        Competition, Copy as Cp, MatchOutput, Venue, Verdict as Vd,
    )

    def _make(title: str):
        return MatchOutput(
            match_id="fb-wc26-fra-mex-20260612",
            sport="football",
            competition=Competition(code="wc26", label="FIFA World Cup 2026"),
            kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
            team_a="France", team_b="Mexico",
            venue=Venue(city="Guadalajara", stadium="Estadio Akron", country="MX"),
            market_outcomes=["a", "draw", "b"],
            verdict=Vd(
                state="pick", side="France", market_venue="polymarket",
                price="-180", edge_pp=4.2,
                market_url="https://polymarket.com/event/fra-mex",
                model_p=0.46, market_p=0.42,
            ),
            copy=Cp(title=title, summary="", blurb=""),
            updated_at=datetime(2026, 6, 12, 17, 0, tzinfo=timezone.utc),
        )

    for phrase in SOCIAL_BANNED_PHRASES:
        out = generate_daily_captions(_make(f"prefix {phrase} suffix"))
        assert out.fell_back, f"phrase {phrase!r} should have triggered fallback"


# ── Citation lockstep ─────────────────────────────────────────────────


def test_outlet_attribution_stripped_when_not_cited(fra_mex_pick) -> None:
    """If the blurb says 'according to Reuters' but Reuters isn't in
    editorial_citations, the social caption must not carry the sentence."""
    poisoned = fra_mex_pick.model_copy(update={
        "copy": Copy(
            title="France v Mexico — class",
            summary="Two short sentences.",
            blurb="Sixty to ninety words. According to Reuters something will happen.",
            editorial_citations=[],
        ),
    })
    out = generate_daily_captions(poisoned)
    assert "reuters" not in out.caption_ig.lower()


def test_outlet_attribution_kept_when_cited(fra_mex_pick) -> None:
    """The sentence stays when the cited outlet appears in editorial_citations."""
    cited = fra_mex_pick.model_copy(update={
        "copy": Copy(
            title="France v Mexico — class",
            summary="Two short sentences.",
            blurb="Sixty to ninety words. According to Reuters something will happen.",
            editorial_citations=[Citation(
                outlet="Reuters",
                url="https://www.reuters.com/foo",
                quote="something will happen",
                published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )],
        ),
    })
    out = generate_daily_captions(cited)
    assert "Reuters" in out.caption_ig


# ── Weekly ─────────────────────────────────────────────────────────────


def test_weekly_captions_contain_top_pick_and_hit_rate() -> None:
    payload = WeeklyRoundupPayload(
        week_starting=date(2026, 6, 1),
        top_picks=[
            RoundupPick(
                match_id="fb-wc26-fra-mex-20260612",
                team_a="France", team_b="Mexico",
                pick_side="France", edge_pp=4.2,
                kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
            ),
        ],
        hit_rate=0.6,
        hit_rate_sample_size=5,
        what_we_got_wrong=ResolvedPick(
            match_id="fb-wc26-bra-arg-20260613",
            pick_side="Brazil", edge_pp=10.5, won=False,
        ),
    )
    out = generate_weekly_captions(payload)
    assert "60% landed" in out.caption_ig
    assert "France" in out.caption_ig and "Mexico" in out.caption_ig
    assert "Brazil" in out.caption_ig
    assert len(out.caption_ig) <= IG_MAX_CHARS
    assert len(out.caption_x)  <= X_MAX_CHARS


def test_weekly_captions_skip_hit_rate_when_unresolved() -> None:
    payload = WeeklyRoundupPayload(
        week_starting=date(2026, 6, 1),
        top_picks=[
            RoundupPick(
                match_id="fb-wc26-fra-mex-20260612",
                team_a="France", team_b="Mexico",
                pick_side="France", edge_pp=4.2,
                kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    out = generate_weekly_captions(payload)
    assert "landed" not in out.caption_ig
    assert "what we got wrong" not in out.caption_ig.lower()
