"""Outright squad_note (Q4 of the squad-paragraph spec).

Covers the deterministic template:
  * absences → "Out: Name (injury), Name (suspension)."
  * at-risk cards → "One booking from a ban: Name."
  * both clauses joined with a space.
  * empty when nothing known.
"""

from __future__ import annotations

from desk.outrights.squad_note import render_squad_note, squad_notes_for_teams
from desk.sports.football.team_news import (
    CardStatus, LineupStatus, PlayerAbsence, TeamNews,
)


def _news(
    *, team: str, absences: tuple[PlayerAbsence, ...] = (),
    cards: tuple[CardStatus, ...] = (),
) -> TeamNews:
    return TeamNews(
        team=team, absences=absences,
        lineup=LineupStatus(state="unknown"),
        materiality="none",
        cards=cards,
    )


def _absence(name: str, type_: str = "injury") -> PlayerAbsence:
    return PlayerAbsence(
        name=name, position="Defender",
        type=type_,  # type: ignore[arg-type]
        reason=None,
        source="api-football", source_url=None, source_name=None,
        importance="medium",
    )


def _card(name: str) -> CardStatus:
    return CardStatus(
        name=name, position="Midfielder", yellows=1,
        state="at_risk",
        source="api-football", source_url=None, source_name=None,
        importance="medium",
    )


# ── render_squad_note ────────────────────────────────────────────────

def test_render_empty_when_no_data():
    assert render_squad_note(None) == ""
    assert render_squad_note(_news(team="France")) == ""


def test_render_absences_only():
    news = _news(
        team="France",
        absences=(_absence("Saliba", "injury"),),
    )
    assert render_squad_note(news) == "Out: Saliba (injury)."


def test_render_cards_only():
    news = _news(
        team="France",
        cards=(_card("Tchouaméni"),),
    )
    assert render_squad_note(news) == "One booking from a ban: Tchouaméni."


def test_render_both_clauses_spec_example_shape():
    """Spec example: 'Out: Saliba (injury). One booking from a ban: Tchouaméni.'"""
    news = _news(
        team="France",
        absences=(_absence("Saliba", "injury"),),
        cards=(_card("Tchouaméni"),),
    )
    assert render_squad_note(news) == (
        "Out: Saliba (injury). One booking from a ban: Tchouaméni."
    )


def test_render_multiple_absences_comma_separated():
    news = _news(
        team="Mexico",
        absences=(
            _absence("Vázquez", "injury"),
            _absence("Pizarro", "suspension"),
        ),
    )
    assert render_squad_note(news) == (
        "Out: Vázquez (injury), Pizarro (suspension)."
    )


def test_render_multiple_at_risk_comma_separated():
    news = _news(
        team="England",
        cards=(_card("Foden"), _card("Bellingham")),
    )
    assert render_squad_note(news) == (
        "One booking from a ban: Foden, Bellingham."
    )


def test_render_drops_absences_with_empty_names():
    """Defensive: empty-name absences are filtered out of the labels."""
    news = _news(
        team="X",
        absences=(_absence(""), _absence("Real Player")),
    )
    assert render_squad_note(news) == "Out: Real Player (injury)."


# ── squad_notes_for_teams ────────────────────────────────────────────

class _FakeRuntime:
    """In-memory stand-in for APIFootballRuntime."""

    def __init__(self, injuries_by_iso3=None, cards_by_iso3=None):
        self._inj = injuries_by_iso3 or {}
        self._cards = cards_by_iso3 or {}

    def injuries_for_iso3(self, iso3):
        return list(self._inj.get(iso3, []))

    def cards_for_iso3(self, iso3, *, competition):
        return list(self._cards.get(iso3, []))

    def injury_penalty_for_iso3(self, iso3):
        return None


def test_squad_notes_for_teams_returns_empty_strings_when_runtime_absent():
    notes = squad_notes_for_teams(
        ["France", "Mexico"],
        api_football_runtime=None,
        competition="wc26",
    )
    assert notes == {"France": "", "Mexico": ""}


def test_squad_notes_for_teams_returns_empty_strings_on_cold_cache():
    """Real runtime, empty caches → empty notes for every team."""
    rt = _FakeRuntime()
    notes = squad_notes_for_teams(
        ["France", "Brazil"], api_football_runtime=rt,
    )
    assert notes == {"France": "", "Brazil": ""}


def test_squad_notes_for_teams_populated_from_runtime():
    """Direct injection at the runtime layer — verifies the wiring
    from runtime → build_team_news → render_squad_note."""
    from desk.data.api_football.cache import (
        CardAccumulationRow, InjuryRow,
    )
    rt = _FakeRuntime(
        injuries_by_iso3={
            "fra": [InjuryRow(
                api_football_team_id=2, player_id=1,
                player_name="Saliba", type="Missing Fixture",
                reason="Knee", position="Defender",
                fetched_at="2026-06-01T00:00:00+00:00",
            )],
        },
        cards_by_iso3={
            "fra": [CardAccumulationRow(
                api_football_team_id=2, player_id=2,
                player_name="Tchouaméni", position="Midfielder",
                yellows=1, reds=0, at_risk=1,
                competition="wc26",
                computed_at="2026-06-01T00:00:00+00:00",
            )],
        },
    )
    notes = squad_notes_for_teams(["France"], api_football_runtime=rt)
    assert notes == {
        "France": "Out: Saliba (injury). One booking from a ban: Tchouaméni.",
    }


def test_squad_notes_for_teams_ignores_unknown_iso3():
    """A team with no ISO3 mapping silently gets an empty note."""
    notes = squad_notes_for_teams(
        ["Mystery FC"], api_football_runtime=_FakeRuntime(),
    )
    assert notes == {"Mystery FC": ""}
