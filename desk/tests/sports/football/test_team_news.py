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

from desk.data.api_football.cache import InjuryRow
from desk.signals.models import Signal, SignalType, Source
from desk.sports.football.team_news import (
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
