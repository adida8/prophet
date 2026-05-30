"""Football glue for the Odds API.

Maps a parsed Odds API event onto a canonical football `FixtureRef`
(`fb-{competition}-{a}-{b}-{yyyymmdd}` per `THE_DESK_SPEC.md` §match-id
format). Lives under `desk/sports/football/` so the sport boundary
stays clean — the sport-agnostic odds-api adapter knows nothing about
football match_ids.

v1 scope: a SINGLE league's 1X2 market. EPL is the launch surface (full
launch-venue coverage on `soccer_epl` via The Odds API). Adding the
next league is two table edits: extend `SPORT_KEY_TO_COMPETITION` and
the per-league name → short-code map.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from desk.sport import FixtureRef
from desk.sports.football.fixtures import (
    MARKET_OUTCOMES_3WAY,
    SHORT_CODE,
    SPORT,
    make_match_id,
)

log = logging.getLogger("desk.sports.football.oddsapi_glue")


# ── Sport-key → competition code / label ─────────────────────────────

@dataclass(frozen=True)
class CompetitionMapping:
    code:  str    # match-id slug, e.g. "epl"
    label: str    # display label, e.g. "Premier League"


# Odds API sport keys → our canonical competition codes. v1 ships EPL
# only; the table is here so adding La Liga / Serie A / WC is a
# one-line edit (the rest of the pipeline is sport-key-agnostic).
SPORT_KEY_TO_COMPETITION: Mapping[str, CompetitionMapping] = {
    "soccer_epl": CompetitionMapping(code="epl", label="Premier League"),
}


# ── EPL team display name → 3-letter short slug ──────────────────────

# Used to build canonical match_ids. Keep this list aligned with the
# Polymarket / api-football lookups so a fixture resolves to the SAME
# match_id whether ingest came from Polymarket or the Odds API.
EPL_TEAM_SHORT: Mapping[str, str] = {
    "Arsenal":                "ars",
    "Aston Villa":            "avl",
    "Bournemouth":            "bou",
    "Brentford":              "bre",
    "Brighton and Hove Albion": "bha",
    "Brighton & Hove Albion":   "bha",
    "Brighton":               "bha",
    "Burnley":                "bur",
    "Chelsea":                "che",
    "Crystal Palace":         "cry",
    "Everton":                "eve",
    "Fulham":                 "ful",
    "Ipswich Town":           "ips",
    "Leeds United":           "lee",
    "Leicester City":         "lei",
    "Liverpool":              "liv",
    "Luton Town":             "lut",
    "Manchester City":        "mci",
    "Manchester United":      "mun",
    "Newcastle United":       "new",
    "Nottingham Forest":      "nfo",
    "Sheffield United":       "shu",
    "Southampton":            "sou",
    "Tottenham Hotspur":      "tot",
    "West Ham United":        "whu",
    "Wolverhampton Wanderers": "wol",
}


def short_code_for_epl_team(name: str) -> str | None:
    """Look up the 3-letter slug for an EPL team display name.

    The Odds API uses the long form ("Manchester United"); Polymarket
    uses the short form already. Returns None when the team isn't in
    the table — callers log + skip the fixture.
    """
    return EPL_TEAM_SHORT.get(name.strip())


# ── Event → FixtureRef ───────────────────────────────────────────────

def from_oddsapi_event(
    parsed_event: dict[str, Any],
) -> FixtureRef | None:
    """One Odds-API parsed event → canonical FixtureRef.

    `parsed_event` is the dict shape produced by
    `desk/data/oddsapi/events.parse_event_payload`. Returns None on any
    shape we don't recognise (unknown sport_key, missing team, etc) so
    a single bad row never breaks ingest.
    """
    sport_key = parsed_event.get("sport_key")
    if not isinstance(sport_key, str):
        return None
    comp = SPORT_KEY_TO_COMPETITION.get(sport_key)
    if comp is None:
        log.info("odds-api event from unmapped sport_key: %s", sport_key)
        return None

    home_team = parsed_event.get("home_team")
    away_team = parsed_event.get("away_team")
    if not isinstance(home_team, str) or not isinstance(away_team, str):
        return None
    kickoff = parsed_event.get("commence_time")
    if not isinstance(kickoff, datetime):
        return None
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)

    if comp.code == "epl":
        home_short = short_code_for_epl_team(home_team)
        away_short = short_code_for_epl_team(away_team)
        if not home_short or not away_short:
            log.warning(
                "odds-api EPL event missing team-short mapping: %s vs %s",
                home_team, away_team,
            )
            return None
    else:
        # Place-holder for the next league. Other comps wouldn't reach
        # this branch in v1 because they're not in SPORT_KEY_TO_COMPETITION;
        # leave the slot so adding the next league + its name-table is
        # the only edit needed.
        return None

    match_id = make_match_id(
        competition=comp.code,
        home=home_short,
        away=away_short,
        kickoff=kickoff,
    )
    return FixtureRef(
        match_id=match_id,
        sport=SPORT,
        competition_code=comp.code,
        competition_label=comp.label,
        competition_stage=None,
        team_a=home_team,
        team_b=away_team,
        kickoff_utc=kickoff,
        market_outcomes=MARKET_OUTCOMES_3WAY,
        venue_city=None,
        venue_stadium=None,
        venue_country=None,
        source_event_slug=str(parsed_event.get("event_id") or ""),
        source_venue="odds_api",
    )


def fixtures_from_oddsapi_payload(
    parsed_events: list[dict[str, Any]],
) -> list[FixtureRef]:
    """Many events → many de-duplicated FixtureRefs."""
    out: list[FixtureRef] = []
    seen: set[str] = set()
    for ev in parsed_events:
        fx = from_oddsapi_event(ev)
        if fx is None:
            continue
        if fx.match_id in seen:
            continue
        seen.add(fx.match_id)
        out.append(fx)
    return out
