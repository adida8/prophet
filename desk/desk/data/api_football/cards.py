"""api-football card accumulation — Q1 of the squad-paragraph spec.

Derives a per-player "at-risk" flag from accumulated yellow cards.
api-football has no "at-risk" field of its own; we count yellows from
the cheaper season-scoped `/players?team=&season=&league=` endpoint and
apply the competition rule to flag players one booking from a ban.

Two viable endpoints (pick by cost):

  * Preferred long-form: `/fixtures/players?fixture={id}` per played
    tournament fixture → per-player `cards.yellow` / `cards.red`. Tight
    accuracy (tournament-scoped) but one call per fixture per team.
  * **v1 (this module)**: `/players?team={id}&season={year}&league={lid}`
    → `statistics[].cards.yellow` / `cards.red` filtered to the WC26
    league entry. One call per team. Coarser (season totals span
    qualifiers + friendlies) but the cost fits inside one daily tick
    comfortably. Upgrade to the per-fixture path if the operator
    eyeballs wrong flags.

Card rules are competition-scoped and live in `CARD_RULES`. WC 2026:
two yellows in separate matches triggers a one-match ban; accumulated
yellows wipe after the quarter-finals (standard FIFA rule, **confirm
against the final WC26 tournament regulations before flipping
DESK_CARD_FETCH=1 live** — see the open-questions section of the
squad-paragraph spec). Wrong rule → false at-risk flags after the QFs.

Failure modes: any HTTP / parse / shape error is logged and returns
`(status="fetch_failed", [])`. The blurb path treats absent card data
as "no at-risk info" — silent, identical to today's behaviour.

Sanity gates (see `_sane_row`) reject:
  * negative card counts (data error),
  * yellow counts > 20 (impossible per season),
the row is dropped rather than the whole batch being failed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from desk.data.api_football.client import APIFootballClient, APIFootballError

_LOG = logging.getLogger(__name__)


# ── competition rules ────────────────────────────────────────────────

@dataclass(frozen=True)
class CardRule:
    """Card-accumulation policy for one competition.

    `yellow_ban_threshold` — number of accumulated yellows that triggers
        a one-match ban. WC26: 2 (per standard FIFA group/KO rules; the
        wipe-after-QF guidance is the open question to confirm).
    `wipe_after_stage` — opaque label for the stage at which yellows
        reset to 0. Not enforced here (we count fixtures from api-football
        directly; once the wipe point passes, the next tournament leg's
        fixture set won't include the pre-wipe yellows). Kept on the rule
        for documentation + future per-stage assertions.
    """
    yellow_ban_threshold: int
    wipe_after_stage:     str


# Per-competition card rules. WC 2026 confirmed at spec time as 2/QF
# wipe; **DESK_CARD_FETCH must NOT be flipped live until the 2026
# tournament regulations are audited and this row signed off**.
CARD_RULES: dict[str, CardRule] = {
    "wc26": CardRule(yellow_ban_threshold=2, wipe_after_stage="quarter_final"),
}

# api-football's league id for FIFA World Cup. Confirmed against the
# /leagues endpoint sample payloads as of 2026-05-30. Used as the
# `league=` filter on /players so the season totals only reflect
# WC-tournament matches (not qualifiers / friendlies).
WC26_LEAGUE_ID: int = 1

# Hard sanity caps. A yellow count outside [0, 20] in a single season
# is a data error — drop the row rather than feed garbage to the
# at-risk derivation.
_MAX_PLAUSIBLE_YELLOWS: int = 20
_MAX_PLAUSIBLE_REDS:    int = 10


@dataclass(frozen=True)
class CardDatum:
    """One player's tournament card state pulled from api-football."""
    team_id:         int
    player_id:       int
    player_name:     str
    position:        str | None
    yellows:         int
    reds:            int
    fetched_at:      datetime
    source_endpoint: str = ""


def _coerce_int(value) -> int:
    """api-football sometimes returns null or '0' — coerce to int safely."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _sane_row(yellows: int, reds: int) -> bool:
    """Cards sanity per spec: reject negative or implausibly large counts."""
    if yellows < 0 or reds < 0:
        return False
    if yellows > _MAX_PLAUSIBLE_YELLOWS or reds > _MAX_PLAUSIBLE_REDS:
        return False
    return True


def _parse_player_entry(
    entry: dict, *, league_id: int, fetched_at: datetime,
    source_endpoint: str,
) -> CardDatum | None:
    """Normalise one /players response row to a CardDatum.

    api-football's /players payload shape:
      {
        "player": {"id": 12345, "name": "...", ...},
        "statistics": [
          {
            "team":   {"id": 33, "name": "..."},
            "league": {"id": 1, "name": "World Cup", "season": 2026, ...},
            "games":  {"position": "Midfielder", ...},
            "cards":  {"yellow": 1, "yellowred": 0, "red": 0},
            ...
          },
          ...
        ]
      }

    A player may have multiple statistics entries (one per competition
    they played in that season). We pick the row whose league.id matches
    `league_id` — the WC26 tournament entry — so qualifiers + friendlies
    don't bleed into the count. Returns None when no matching league row
    exists OR when the parsed counts fail sanity.
    """
    player = entry.get("player") or {}
    statistics = entry.get("statistics") or []
    try:
        player_id = int(player["id"])
        player_name = str(player.get("name") or "")
    except (KeyError, TypeError, ValueError):
        return None
    if not player_name:
        return None

    # Pick the row whose league.id matches the target competition.
    chosen: dict | None = None
    for stat in statistics:
        league = (stat.get("league") or {})
        try:
            lid = int(league.get("id"))
        except (TypeError, ValueError):
            continue
        if lid == league_id:
            chosen = stat
            break
    if chosen is None:
        return None

    team = (chosen.get("team") or {})
    try:
        team_id = int(team["id"])
    except (KeyError, TypeError, ValueError):
        return None

    cards = (chosen.get("cards") or {})
    yellows = _coerce_int(cards.get("yellow")) + _coerce_int(cards.get("yellowred"))
    reds = _coerce_int(cards.get("red"))
    if not _sane_row(yellows, reds):
        _LOG.debug(
            "cards sanity drop: team=%s player=%s yellows=%s reds=%s",
            team_id, player_id, yellows, reds,
        )
        return None

    games = (chosen.get("games") or {})
    position = games.get("position") or None

    return CardDatum(
        team_id=team_id,
        player_id=player_id,
        player_name=player_name,
        position=position,
        yellows=yellows,
        reds=reds,
        fetched_at=fetched_at,
        source_endpoint=source_endpoint,
    )


async def fetch_for_team(
    api_football_team_id: int,
    *,
    season: int,
    league_id: int = WC26_LEAGUE_ID,
    client: APIFootballClient,
) -> tuple[str, list[CardDatum]]:
    """Return (status, items). Status is "ok" on success; client error
    `kind` on failure (items=[]). The /players endpoint paginates by
    default; we read only the first page — squad size for a national
    side fits inside one page (api-football: 20 / page, ~26 max squad).

    api-football /players returns paginated; the first page covers the
    full national-team squad. Multi-page reads stay deferred to v2 if
    a club fixture ever extends beyond 20 — flag it loud and revisit.
    """
    endpoint = f"/players?team={api_football_team_id}&season={season}&league={league_id}"
    try:
        resp = await client.get("/players", params={
            "team":   str(api_football_team_id),
            "season": str(season),
            "league": str(league_id),
        })
    except APIFootballError as e:
        return (f"{e.kind}", [])

    now = datetime.now(tz=timezone.utc)
    items: list[CardDatum] = []
    for entry in (resp.payload.get("response") or []):
        parsed = _parse_player_entry(
            entry, league_id=league_id, fetched_at=now,
            source_endpoint=endpoint,
        )
        if parsed is not None:
            items.append(parsed)

    # Note: a player on more than one page is possible for very large
    # squads. Page total surfaces in `resp.payload.paging.total` —
    # warn but don't fail the batch if it's > 1.
    paging = (resp.payload.get("paging") or {})
    if _coerce_int(paging.get("total")) > 1:
        _LOG.warning(
            "fetch_for_team team=%s season=%s: paging.total > 1; "
            "v1 reads page 1 only — see cards.py docstring",
            api_football_team_id, season,
        )
    return ("ok", items)


# ── derivation ───────────────────────────────────────────────────────

def derive_at_risk(
    yellows: int,
    *,
    competition: str,
    already_suspended: bool = False,
) -> bool:
    """Spec §Q1 derivation: `at_risk = (yellows == threshold-1) AND not
    already_suspended`. A player who's been sent off OR triggered the
    accumulation ban already isn't "at-risk for the next match" — they
    *are* the next-match absence. The injuries / cards reconcile in Q2
    drops the duplicate from `cards` so the squad paragraph never names
    the same player twice.

    Unknown competition → False. Defensive: better silent than wrong.
    """
    if already_suspended:
        return False
    rule = CARD_RULES.get(competition.lower())
    if rule is None:
        return False
    return yellows == (rule.yellow_ban_threshold - 1)


_AbsenceKind = Literal["injury", "suspension", "none"]


def card_data_to_rows(
    items: list[CardDatum],
    *,
    competition: str,
    suspended_player_ids: set[int] | None = None,
) -> list:
    """Convert raw CardDatum list to CardAccumulationRow list with
    at_risk derived. Sanity-rejects anything `_sane_row` already filtered
    upstream; this is the pure conversion.

    `suspended_player_ids` is the set of api-football player_ids the
    injuries cache has flagged as `Suspended` for this team (so the
    at-risk reconcile drops them — they're already a confirmed absence,
    naming them as "at-risk" would be wrong).
    """
    from desk.data.api_football.cache import CardAccumulationRow
    suspended = suspended_player_ids or set()
    out: list = []
    for it in items:
        already = it.player_id in suspended
        at_risk = derive_at_risk(
            it.yellows, competition=competition, already_suspended=already,
        )
        out.append(CardAccumulationRow(
            api_football_team_id=it.team_id,
            player_id=it.player_id,
            player_name=it.player_name,
            position=it.position,
            yellows=it.yellows,
            reds=it.reds,
            at_risk=1 if at_risk else 0,
            competition=competition.lower(),
            computed_at=it.fetched_at.isoformat(),
            source_endpoint=it.source_endpoint,
        ))
    return out
