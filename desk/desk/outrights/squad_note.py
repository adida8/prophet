"""Deterministic per-team squad summary for the outright ladder — Q4
of the squad-paragraph spec.

The outright surface has no per-team Haiku pass (48 teams × an LLM
call per refresh would be both expensive and pointless for a one-line
mechanical summary). Instead each ladder row carries a templated
`squad_note` string built from the same `TeamNews` payload the match
blurbs use.

Template:

    "Out: <names>. One booking from a ban: <names>."

Either clause is omitted when empty. Returns the empty string when
nothing is known for the team — the renderer can skip the field
without checking.

Behaviour rules:

  * Only `absences` (injuries + suspensions) populate the "Out" clause.
    Each name carries `(injury)` / `(suspension)` so the reader can
    tell why.
  * Only `at_risk` cards populate the "One booking from a ban" clause.
    The Q2 reconcile already drops players who are both at-risk AND
    already suspended; the template never has to filter again.
  * No `lineup` content is surfaced — the ladder is about availability
    between matches, not the next-match XI.

Failures are silent: the team-news builder never raises, and a missing
api-football cache just yields an empty `TeamNews` → empty note.
"""

from __future__ import annotations

import logging
from typing import Iterable

from desk.sports.football.team_news import (
    PlayerAbsence,
    TeamNews,
    build_team_news,
    iso3_for_team,
)

_LOG = logging.getLogger(__name__)


def _absence_label(absence: PlayerAbsence) -> str:
    """Render one absence as `Name (injury)` / `Name (suspension)`.

    Name comes verbatim from the upstream source (api-football or RSS
    claim). Empty names are filtered upstream by `_merge_absences`.
    """
    return f"{absence.name} ({absence.type})"


def render_squad_note(news: TeamNews | None) -> str:
    """Build the one-line squad summary string for one team.

    Empty string when there are no absences AND no at-risk cards. The
    caller can write the field unconditionally without a None guard.
    """
    if news is None:
        return ""
    out_parts: list[str] = []
    if news.absences:
        labels = [_absence_label(a) for a in news.absences if (a.name or "").strip()]
        if labels:
            out_parts.append(f"Out: {', '.join(labels)}.")
    if news.cards:
        names = [c.name for c in news.cards if (c.name or "").strip()]
        if names:
            out_parts.append(f"One booking from a ban: {', '.join(names)}.")
    return " ".join(out_parts)


def squad_notes_for_teams(
    teams: Iterable[str],
    *,
    api_football_runtime,
    competition: str = "wc26",
) -> dict[str, str]:
    """Build `{team_name: squad_note}` for every team in the ladder.

    Reuses `build_team_news` with empty `signals` and no `lineup_row`
    (the outright ladder is between matches, no fixture-specific
    context). When `api_football_runtime` is None or the cache is
    cold, every team gets an empty string — same shape, no surprises
    for the renderer.
    """
    notes: dict[str, str] = {}
    for team in teams:
        if not team:
            continue
        iso3 = iso3_for_team(team)
        injury_rows = []
        card_rows = []
        elo_penalty = None
        if api_football_runtime is not None and iso3:
            try:
                injury_rows = list(api_football_runtime.injuries_for_iso3(iso3))
                card_rows = list(api_football_runtime.cards_for_iso3(
                    iso3, competition=competition,
                ))
                elo_penalty = api_football_runtime.injury_penalty_for_iso3(iso3)
            except Exception as e:  # noqa: BLE001 — never block the ladder
                _LOG.warning("squad_note lookup failed for %s: %s", team, e)
        try:
            news = build_team_news(
                team_name=team, iso3=iso3,
                injury_rows=injury_rows, signals=[],
                elo_penalty=elo_penalty,
                lineup_row=None,
                card_rows=card_rows,
            )
        except Exception as e:  # noqa: BLE001 — builder shouldn't raise
            _LOG.warning("squad_note builder failed for %s: %s", team, e)
            notes[team] = ""
            continue
        notes[team] = render_squad_note(news)
    return notes
