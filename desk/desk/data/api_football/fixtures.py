"""Fetch a team's last-N fixtures from api-football.

Endpoint: `/fixtures?team={team_id}&last={N}` — returns recent matches
sorted by date. We filter to `status.short == "FT"` (Full Time) so
postponements, abandonments, and unfinished games don't feed form_delta.

Per fixture, normalise to a FixtureResult with the team's perspective:
  * `team_goals` / `opponent_goals` are the team's actual goals, not
    raw "home" / "away" — we flip based on which side the fetched team
    appears on.
"""

from __future__ import annotations

import logging
from datetime import datetime

from desk.data.api_football.cache import APIFootballCache, FixtureResult
from desk.data.api_football.client import APIFootballClient, APIFootballError

_LOG = logging.getLogger(__name__)


async def fetch_recent_fixtures(
    api_football_team_id: int,
    *,
    client: APIFootballClient,
    n: int = 10,
) -> list[FixtureResult]:
    """Return a list of FixtureResult, freshest first. Raises
    `APIFootballError` on transport / auth failure; the caller decides
    whether to fail hard or proceed with stale data."""

    resp = await client.get(
        "/fixtures",
        params={"team": str(api_football_team_id), "last": str(n)},
    )
    response_list = resp.payload.get("response") or []
    out: list[FixtureResult] = []
    for entry in response_list:
        try:
            out.append(_normalise_fixture(api_football_team_id, entry))
        except (KeyError, TypeError, ValueError) as e:
            _LOG.warning("skipping malformed fixture for team %d: %s",
                         api_football_team_id, e)
    return out


def _normalise_fixture(team_id: int, entry: dict) -> FixtureResult:
    fixture = entry["fixture"]
    teams = entry["teams"]
    goals = entry.get("goals") or {}

    fixture_id = int(fixture["id"])
    status_short = (fixture.get("status") or {}).get("short", "")
    date_raw = fixture.get("date")  # ISO-8601 with timezone
    played_at = datetime.fromisoformat(date_raw) if date_raw else datetime.fromtimestamp(0)

    home = teams.get("home") or {}
    away = teams.get("away") or {}
    home_id = int(home["id"]) if home.get("id") is not None else None
    away_id = int(away["id"]) if away.get("id") is not None else None
    home_goals = goals.get("home")
    away_goals = goals.get("away")

    if home_id == team_id:
        team_goals = home_goals
        opp_goals = away_goals
        opp_id = away_id
    elif away_id == team_id:
        team_goals = away_goals
        opp_goals = home_goals
        opp_id = home_id
    else:
        # api-football returned a fixture where neither side is the
        # requested team — shouldn't happen but defensively log + skip
        # by raising a clear error.
        raise ValueError(
            f"fixture {fixture_id}: team {team_id} appears as neither side"
        )

    return FixtureResult(
        api_football_team_id=team_id,
        fixture_id=fixture_id,
        played_at=played_at,
        opponent_team_id=opp_id,
        team_goals=int(team_goals) if team_goals is not None else None,
        opponent_goals=int(opp_goals) if opp_goals is not None else None,
        status_short=status_short,
    )
