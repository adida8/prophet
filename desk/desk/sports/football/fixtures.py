"""Fixture-list adapter for football.

Pulls priced match events from every football-tagged source in the
ingest registry and maps each into a `FixtureRef` with a stable
match_id.

The match_id is canonical:
    `fb-{competition}-{home}-{away}-{yyyymmdd}`

For unknown competitions we pass the raw Polymarket prefix through and
emit a log line — the engine still publishes the fixture; PR 3+ can fill
in proper team metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from desk import config
from desk.sport import FixtureRef
from desk.sports.football.teams import (
    is_international_competition,
    iso3_for_name,
    map_competition,
    normalize_team,
)

log = logging.getLogger("desk.sports.football.fixtures")

SPORT       = "football"
SHORT_CODE  = "fb"
MARKET_OUTCOMES_3WAY = ("a", "draw", "b")


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    # Polymarket sometimes drops microseconds, sometimes not.
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def make_match_id(*, competition: str, home: str, away: str, kickoff: datetime) -> str:
    return f"{SHORT_CODE}-{competition}-{home}-{away}-{kickoff.strftime('%Y%m%d')}"


def from_polymarket_event(ev: dict[str, Any]) -> FixtureRef | None:
    """Map one gamma-event row to a `FixtureRef`. Returns None on shapes
    we don't recognise (logged) so a single bad row never breaks ingest.
    """
    from desk.ingest.polymarket import parse_slug, parse_title

    slug = ev.get("slug") or ""
    parts = parse_slug(slug)
    if not parts:
        log.warning("polymarket event has unrecognised slug: %s", slug)
        return None

    title = ev.get("title") or ""
    name_pair = parse_title(title)
    home_name, away_name = name_pair if name_pair else ("", "")
    if not home_name or not away_name:
        log.warning("polymarket event title not parseable: %s", title)
        return None

    kickoff = _parse_dt(ev.get("endDate"))
    if not kickoff:
        log.warning("polymarket event missing endDate: %s", slug)
        return None

    comp_pair = map_competition(parts["prefix"])
    if comp_pair:
        comp_code, comp_label = comp_pair
    else:
        comp_code, comp_label = parts["prefix"], parts["prefix"]
        log.info("unmapped Polymarket competition prefix: %s", parts["prefix"])

    international = is_international_competition(comp_code)
    # Prefer the title-derived display name → ISO3 when we know it
    # (more reliable than Polymarket's slug codes — see e.g. their use
    # of `kor` for Curaçao, which collides with Korea Republic's ISO).
    home = (iso3_for_name(home_name) if international else None) \
           or normalize_team(parts["home"], is_national=international)
    away = (iso3_for_name(away_name) if international else None) \
           or normalize_team(parts["away"], is_national=international)
    if international and home == away:
        # Same ISO on both sides means the disambiguation failed —
        # fall back to slug codes so the match_id stays unique.
        log.warning("name-resolved ISO collision on %s: %s == %s — slug fallback", slug, home_name, away_name)
        home = normalize_team(parts["home"], is_national=international)
        away = normalize_team(parts["away"], is_national=international)

    match_id = make_match_id(
        competition=comp_code, home=home, away=away, kickoff=kickoff,
    )

    return FixtureRef(
        match_id=match_id,
        sport=SPORT,
        competition_code=comp_code,
        competition_label=comp_label,
        competition_stage=None,                 # PR 3 will populate from FIFA metadata
        team_a=home_name,
        team_b=away_name,
        kickoff_utc=kickoff,
        market_outcomes=MARKET_OUTCOMES_3WAY,
        venue_city=None,                        # PR 3 populates
        venue_stadium=None,
        venue_country=None,
        source_event_slug=slug,
        source_venue="polymarket",
    )


def fixtures_from_polymarket(events: Iterable[dict[str, Any]]) -> list[FixtureRef]:
    out: list[FixtureRef] = []
    seen: set[str] = set()
    for ev in events:
        fx = from_polymarket_event(ev)
        if fx is None:
            continue
        if fx.match_id in seen:
            # "More Markets" events sometimes duplicate the base match.
            continue
        seen.add(fx.match_id)
        out.append(fx)
    return out


async def list_priced_football_fixtures() -> list[FixtureRef]:
    """Live fetch from Polymarket + Kalshi (stub) → de-duplicated FixtureRefs.

    Purely additive — sources that fail are logged and skipped, never
    block a publish (spec §9 failure-mode rule).
    """
    from desk.ingest.kalshi import KalshiSoccerEventsSource
    from desk.ingest.polymarket import PolymarketSoccerEventsSource

    fixtures: list[FixtureRef] = []
    seen: set[str] = set()
    allow = config.COMPETITION_ALLOWLIST

    # Polymarket (real)
    try:
        events = await PolymarketSoccerEventsSource().fetch()
        for fx in fixtures_from_polymarket(events):
            if allow is not None and fx.competition_code not in allow:
                continue
            if fx.match_id not in seen:
                seen.add(fx.match_id)
                fixtures.append(fx)
    except Exception as e:                    # noqa: BLE001 — see spec §9
        log.warning("polymarket fetch failed: %s", e)

    # Kalshi (stub returns []; future-real)
    try:
        await KalshiSoccerEventsSource().fetch()
    except Exception as e:                    # noqa: BLE001
        log.warning("kalshi fetch failed: %s", e)

    return fixtures
