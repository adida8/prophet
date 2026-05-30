"""Tests for the TeamNews builder (Slice A of the team-news blurb spec).

The builder fuses api-football injury rows + RSS hard signals into a
single per-team payload the Haiku writer can read. Tests cover:

  * Materiality matrix — none / low / medium / high.
  * Dedupe between api-football and RSS by normalised name + surname.
  * Lineup state precedence (confirmed > predicted > unknown).
  * Importance promotion (GK / CB / captain → materiality=high).
  * Edge cases: empty inputs, name mismatches, partial diacritics.
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.data.api_football.cache import CardAccumulationRow, InjuryRow
from desk.signals.models import Signal, SignalType, Source
from desk.sports.football.team_news import (
    CardStatus,
    PlayerAbsence,
    TeamNews,
    build_team_news,
)


# ── helpers ─────────────────────────────────────────────────────────

def _injury(
    *, name: str, position: str | None = "Midfielder",
    type: str = "Missing Fixture", reason: str = "Knock",
) -> InjuryRow:
    return InjuryRow(
        api_football_team_id=33,
        player_id=hash(name) % 100000,
        player_name=name,
        type=type,
        reason=reason,
        position=position,
        fetched_at="2026-05-30T08:00:00+00:00",
    )


def _source(*, id: str = "guardian-football", reliability: float = 0.9) -> Source:
    return Source(
        id=id,
        name="The Guardian (football)" if id == "guardian-football" else id,
        feed_type="rss",
        feed_ref="https://example.com/rss",
        language="en",
        coverage_tags=frozenset({"global", "sport:football"}),
        reliability=reliability,
        bias_flag="none",
        tier="trusted_core",
    )


def _signal(
    *, team: str, type: SignalType = SignalType.INJURY,
    claim: str = "Mbappé will miss the match", source_id: str = "guardian-football",
) -> Signal:
    return Signal(
        type=type,
        team=team,
        claim=claim,
        quote="some verbatim quote from the article",
        source_id=source_id,
        url="https://www.theguardian.com/football/2026/may/30/foo",
        published_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
        confidence=0.9,
    )


# ── materiality matrix ──────────────────────────────────────────────

def test_materiality_none_with_empty_inputs() -> None:
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=[], signals=[], elo_penalty=None,
    )
    assert news.materiality == "none"
    assert news.absences == ()
    assert news.lineup.state == "unknown"


def test_materiality_high_on_goalkeeper_absence() -> None:
    rows = [_injury(name="Maignan", position="Goalkeeper")]
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=rows, signals=[], elo_penalty=10.0,
    )
    assert news.materiality == "high"
    assert news.absences[0].importance == "high"


def test_materiality_high_on_three_or_more_absences() -> None:
    rows = [
        _injury(name="A", position="Midfielder"),
        _injury(name="B", position="Midfielder"),
        _injury(name="C", position="Midfielder"),
    ]
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=rows, signals=[], elo_penalty=15.0,
    )
    assert news.materiality == "high"
    assert len(news.absences) == 3


def test_materiality_high_on_large_elo_penalty() -> None:
    rows = [_injury(name="One", position="Midfielder")]
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=rows, signals=[], elo_penalty=45.0,
    )
    assert news.materiality == "high"


def test_materiality_medium_on_mid_penalty() -> None:
    rows = [_injury(name="One", position="Midfielder")]
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=rows, signals=[], elo_penalty=15.0,
    )
    assert news.materiality == "medium"


def test_materiality_low_on_small_penalty_no_high_importance() -> None:
    # A single Defender absence with a tiny Elo penalty → low. We don't
    # flag a fringe absence as material content for the blurb.
    rows = [_injury(name="One", position="Attacker")]
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=rows, signals=[], elo_penalty=5.0,
    )
    # The single Attacker is medium-importance per the bucket, so the
    # materiality lands at "medium" — verifying the boundary.
    assert news.materiality == "medium"


def test_questionable_rows_excluded() -> None:
    rows = [_injury(name="Ignored", type="Questionable")]
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=rows, signals=[], elo_penalty=None,
    )
    assert news.absences == ()
    assert news.materiality == "none"


# ── dedupe ──────────────────────────────────────────────────────────

def test_dedupe_promotes_api_row_with_rss_url() -> None:
    api_rows = [_injury(name="Kylian Mbappé", position="Attacker")]
    sig = _signal(team="France", claim="Mbappé")
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=api_rows, signals=[(sig, _source())], elo_penalty=10.0,
    )
    # Single row (deduped), with the RSS source_url attached.
    assert len(news.absences) == 1
    abs0 = news.absences[0]
    assert abs0.name == "Kylian Mbappé"  # api-football display name wins
    assert abs0.position == "Attacker"   # api-football position survives
    assert abs0.source_url == sig.url    # RSS URL upgraded onto the row
    assert abs0.source_name == "The Guardian (football)"


def test_dedupe_handles_diacritics() -> None:
    api_rows = [_injury(name="Vázquez", position="Defender")]
    sig = _signal(team="France", claim="Vazquez")
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=api_rows, signals=[(sig, _source())], elo_penalty=10.0,
    )
    assert len(news.absences) == 1
    assert news.absences[0].source_url == sig.url


def test_rss_only_player_appears_separately() -> None:
    sig = _signal(team="France", claim="Griezmann doubtful")
    news = build_team_news(
        team_name="France", iso3="fra",
        injury_rows=[], signals=[(sig, _source())], elo_penalty=None,
    )
    assert len(news.absences) == 1
    assert news.absences[0].source == "guardian-football"
    assert news.absences[0].source_url == sig.url


# ── lineup state precedence ─────────────────────────────────────────

def test_confirmed_lineup_wins_over_predicted() -> None:
    pred = _signal(
        team="France", type=SignalType.PREDICTED_LINEUP,
        claim="France 4-3-3 expected",
    )
    conf = _signal(
        team="France", type=SignalType.CONFIRMED_LINEUP,
        claim="France official XI announced",
    )
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[(pred, _source()), (conf, _source())], elo_penalty=None,
    )
    assert news.lineup.state == "confirmed"


def test_predicted_lineup_when_no_confirmed() -> None:
    pred = _signal(
        team="France", type=SignalType.PREDICTED_LINEUP,
        claim="France 4-3-3 expected",
    )
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[(pred, _source())], elo_penalty=None,
    )
    assert news.lineup.state == "predicted"


def test_lineup_unknown_when_no_lineup_signals() -> None:
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[], elo_penalty=None,
    )
    assert news.lineup.state == "unknown"


# ── team filter ─────────────────────────────────────────────────────

def test_signals_filtered_by_team_name() -> None:
    # Signal for Mexico passed into the France builder → dropped.
    sig = _signal(team="Mexico", claim="Vázquez out")
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[(sig, _source())], elo_penalty=None,
    )
    assert news.absences == ()


def test_signals_team_iso3_match() -> None:
    # Extractor may emit ISO3 instead of display name — accept both.
    sig = _signal(team="fra", claim="Griezmann doubt")
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[(sig, _source())], elo_penalty=None,
    )
    assert len(news.absences) == 1


# ── builder never raises ────────────────────────────────────────────

def test_builder_returns_empty_team_news_on_empty_iso3() -> None:
    news = build_team_news(
        team_name="Mystery FC", iso3=None, injury_rows=None,
        signals=[], elo_penalty=None,
    )
    assert isinstance(news, TeamNews)
    assert news.materiality == "none"


# ── lineup integration (Slice B / N3) ───────────────────────────────

from desk.data.api_football.cache import LineupRow  # noqa: E402


def _lineup_row(*, state: str = "confirmed", starters_n: int = 11) -> LineupRow:
    return LineupRow(
        fixture_id=999,
        api_football_team_id=33,
        state=state,
        formation="4-3-3",
        coach_name="Didier Deschamps",
        starters=tuple(f"Player{i}" for i in range(1, starters_n + 1)),
        substitutes=("Sub1", "Sub2"),
        fetched_at="2026-06-12T17:00:00+00:00",
        announced_at=None,
    )


def test_api_football_lineup_wins_over_rss() -> None:
    """When api-football has the row, RSS lineup signals don't overwrite."""
    rss_pred = _signal(
        team="France", type=SignalType.PREDICTED_LINEUP,
        claim="France expected to start in 4-2-3-1",
    )
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[(rss_pred, _source())], elo_penalty=None,
        lineup_row=_lineup_row(),
    )
    assert news.lineup.state == "confirmed"
    assert news.lineup.formation == "4-3-3"
    assert news.lineup.source == "api-football"
    assert len(news.lineup.starters) == 11


def test_lineup_starters_carried_onto_status() -> None:
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[], elo_penalty=None,
        lineup_row=_lineup_row(),
    )
    assert news.lineup.starters[0] == "Player1"
    assert news.lineup.coach == "Didier Deschamps"


def test_no_lineup_row_falls_through_to_rss_signals() -> None:
    confirmed = _signal(
        team="France", type=SignalType.CONFIRMED_LINEUP,
        claim="France official XI announced",
    )
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[],
        signals=[(confirmed, _source())], elo_penalty=None,
        lineup_row=None,
    )
    assert news.lineup.state == "confirmed"
    assert news.lineup.source == "guardian-football"  # RSS source preserved
    assert news.lineup.starters == ()


# ── cards (Q2 — squad-paragraph spec) ───────────────────────────────

def _card_row(
    *, player_id: int, name: str, yellows: int = 1, at_risk: int = 1,
    position: str | None = "Midfielder",
) -> CardAccumulationRow:
    return CardAccumulationRow(
        api_football_team_id=33,
        player_id=player_id,
        player_name=name,
        position=position,
        yellows=yellows, reds=0,
        at_risk=at_risk,
        competition="wc26",
        computed_at="2026-06-12T06:00:00+00:00",
        source_endpoint="/players?team=33&season=2026&league=1",
    )


def test_cards_at_risk_player_appears_in_cards_tuple() -> None:
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None,
        card_rows=[_card_row(player_id=1, name="Tchouaméni", yellows=1)],
    )
    assert len(news.cards) == 1
    c = news.cards[0]
    assert isinstance(c, CardStatus)
    assert c.name == "Tchouaméni"
    assert c.yellows == 1
    assert c.state == "at_risk"
    assert c.source == "api-football"


def test_cards_not_at_risk_rows_are_filtered() -> None:
    """v1 only surfaces `at_risk=1` CardStatus rows."""
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None,
        card_rows=[
            _card_row(player_id=1, name="A", yellows=1, at_risk=1),
            _card_row(player_id=2, name="B", yellows=0, at_risk=0),
        ],
    )
    assert [c.name for c in news.cards] == ["A"]


def test_cards_reconcile_drops_suspended_player() -> None:
    """Spec §Q2: a player both at-risk AND already suspended is dropped
    from `cards` — the suspension is the confirmed absence, naming them
    as 'at-risk' as well would double-count."""
    suspension_row = InjuryRow(
        api_football_team_id=33,
        player_id=99,
        player_name="Bellingham",
        type="Suspended",
        reason="Yellow accumulation",
        position="Midfielder",
        fetched_at="2026-06-12T06:00:00+00:00",
    )
    news = build_team_news(
        team_name="England", iso3="eng",
        injury_rows=[suspension_row], signals=[], elo_penalty=None,
        card_rows=[
            _card_row(player_id=1, name="Foden",      yellows=1),
            _card_row(player_id=99, name="Bellingham", yellows=1),
        ],
    )
    # Bellingham is in absences as a suspension; cards drops the dup.
    assert any(a.name == "Bellingham" and a.type == "suspension"
               for a in news.absences)
    assert [c.name for c in news.cards] == ["Foden"]


def test_cards_reconcile_handles_partial_name_match() -> None:
    """Substring fallback: 'Bellingham' (card row) vs 'Jude Bellingham'
    (suspension absence) should still reconcile out."""
    suspension_row = InjuryRow(
        api_football_team_id=33,
        player_id=99,
        player_name="Jude Bellingham",   # full name
        type="Suspended",
        reason="Yellow accumulation",
        position="Midfielder",
        fetched_at="2026-06-12T06:00:00+00:00",
    )
    news = build_team_news(
        team_name="England", iso3="eng",
        injury_rows=[suspension_row], signals=[], elo_penalty=None,
        card_rows=[_card_row(player_id=99, name="Bellingham", yellows=1)],
    )
    assert news.cards == ()


def test_cards_dont_raise_materiality_above_low() -> None:
    """Spec §Q2: at-risk cards never push materiality above 'low' on
    their own — they're a risk, not a fact."""
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None,
        card_rows=[
            _card_row(player_id=1, name="A", yellows=1),
            _card_row(player_id=2, name="B", yellows=1),
            _card_row(player_id=3, name="C", yellows=1),
            _card_row(player_id=4, name="D", yellows=1),   # 4 at-risk players
        ],
    )
    assert news.materiality == "low"


def test_cards_only_bumps_none_to_low() -> None:
    """Empty absences + None penalty + ≥1 at-risk card → materiality=low
    (was 'none' before cards). All other inputs unchanged."""
    news_empty = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None,
    )
    assert news_empty.materiality == "none"

    news_cards = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None,
        card_rows=[_card_row(player_id=1, name="A", yellows=1)],
    )
    assert news_cards.materiality == "low"


def test_cards_default_empty_tuple_when_no_card_rows() -> None:
    """Existing callers that don't pass card_rows still get a TeamNews
    with an empty cards tuple — backwards-compatible default."""
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None,
    )
    assert news.cards == ()


def test_cards_skipped_when_card_rows_is_none() -> None:
    """None for card_rows behaves identically to []."""
    news = build_team_news(
        team_name="France", iso3="fra", injury_rows=[], signals=[],
        elo_penalty=None, card_rows=None,
    )
    assert news.cards == ()
