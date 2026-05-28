"""Ingest resolved match outcomes into forward_validation.db.

Per-fixture flow:
  1. The forward-validation log has unresolved predictions keyed by
     match_id (e.g. `fb-wc26-fra-mex-20260612`).
  2. We parse the match_id to extract the home/away ISO3 + the kickoff
     date.
  3. Look up api-football team_ids via the existing api-football cache
     (`team_resolution` table).
  4. Hit `/fixtures?team={home_team_id}&date={yyyy-mm-dd}` — find the
     fixture that matches both teams, read its final goals, derive the
     (a / draw / b) outcome.
  5. Write to `outcomes` table.

We do NOT hit api-football unless the fixture is past its kickoff date
+ a 6h settle buffer. Live + recently-finished games may not have
finalized in api-football's feed yet.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.client import APIFootballClient, APIFootballError

_LOG = logging.getLogger(__name__)

# Minimum time after the match_id's date (midnight UTC) before we
# look for a settled result. The parser uses 00:00 UTC as kickoff
# because the match_id only carries date precision; 30h covers any
# real kickoff time on that date + extra time + a comfortable margin
# for api-football to propagate the final.
SETTLE_BUFFER = timedelta(hours=30)

# match_id format: fb-{comp}-{home_iso3}-{away_iso3}-{yyyymmdd}
_MATCH_ID_RE = re.compile(
    r"^fb-(?P<comp>[a-z0-9]+)-(?P<home>[a-z0-9]+)-(?P<away>[a-z0-9]+)-(?P<date>\d{8})$"
)


@dataclass(frozen=True)
class IngestOutcome:
    match_id: str
    status:   str          # "ok", "not_settled_yet", "unparseable_match_id",
                           # "team_id_missing", "no_fixture_found", "error"
    outcome:  str | None = None    # "a" / "draw" / "b" when status == "ok"
    error:    str | None = None


def parse_match_id(match_id: str) -> tuple[str, str, str, datetime] | None:
    """Return (comp, home_iso3, away_iso3, kickoff_date_utc) or None
    when the match_id doesn't follow the canonical shape."""
    m = _MATCH_ID_RE.match(match_id)
    if not m:
        return None
    try:
        d = datetime.strptime(m.group("date"), "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return m.group("comp"), m.group("home"), m.group("away"), d


def _classify_outcome(team_goals: int, opponent_goals: int) -> str:
    if team_goals > opponent_goals:
        return "a"     # home / team_a wins
    if team_goals < opponent_goals:
        return "b"     # away / team_b wins
    return "draw"


async def ingest_one(
    match_id: str,
    *,
    client: APIFootballClient,
    af_cache: APIFootballCache,
    now: datetime | None = None,
) -> IngestOutcome:
    """Look up + return the outcome for one fixture. Does NOT write to
    the forward-validation log — the CLI loop does that after batching
    decisions."""
    now = now or datetime.now(tz=timezone.utc)

    parsed = parse_match_id(match_id)
    if parsed is None:
        return IngestOutcome(match_id, "unparseable_match_id")
    _, home_iso3, away_iso3, kickoff = parsed

    # Don't ingest yet if the fixture hasn't comfortably settled.
    if now < kickoff + SETTLE_BUFFER:
        return IngestOutcome(match_id, "not_settled_yet")

    home_team_id = af_cache.team_id_for_iso3(home_iso3)
    away_team_id = af_cache.team_id_for_iso3(away_iso3)
    if home_team_id is None or away_team_id is None:
        return IngestOutcome(
            match_id, "team_id_missing",
            error=f"home={home_iso3} away={away_iso3} not resolved",
        )

    date_str = kickoff.strftime("%Y-%m-%d")
    try:
        resp = await client.get(
            "/fixtures",
            params={"team": str(home_team_id), "date": date_str},
        )
    except APIFootballError as e:
        return IngestOutcome(match_id, "error", error=f"{e.kind}: {e}")

    fixtures = resp.payload.get("response") or []
    # Pick the fixture where the other side matches our away_team_id.
    settled = None
    for entry in fixtures:
        teams = entry.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        fid_a = home.get("id")
        fid_b = away.get("id")
        if fid_a == home_team_id and fid_b == away_team_id:
            settled = entry
            break
        # api-football sometimes returns the same fixture from the
        # other side's perspective if the operator's team_id swap
        # drifted. Tolerate that one corner.
        if fid_b == home_team_id and fid_a == away_team_id:
            settled = entry
            break
    if settled is None:
        return IngestOutcome(
            match_id, "no_fixture_found",
            error=f"no /fixtures?team={home_team_id}&date={date_str} matches away={away_team_id}",
        )

    status = (settled.get("fixture") or {}).get("status") or {}
    if status.get("short") != "FT":
        return IngestOutcome(
            match_id, "not_settled_yet",
            error=f"status.short={status.get('short')}",
        )

    goals = settled.get("goals") or {}
    teams = settled["teams"]
    home_id = (teams.get("home") or {}).get("id")
    home_goals = goals.get("home")
    away_goals = goals.get("away")
    if home_goals is None or away_goals is None:
        return IngestOutcome(match_id, "error",
                             error="missing goals in FT fixture")

    if home_id == home_team_id:
        team_a_goals = home_goals
        team_b_goals = away_goals
    else:
        team_a_goals = away_goals
        team_b_goals = home_goals
    return IngestOutcome(
        match_id, "ok",
        outcome=_classify_outcome(int(team_a_goals), int(team_b_goals)),
    )


async def ingest_pending(
    match_ids: list[str],
    *,
    client: APIFootballClient,
    af_cache: APIFootballCache,
    now: datetime | None = None,
) -> list[IngestOutcome]:
    """Sequential ingest — one /fixtures call per pending match_id.
    Order is preserved; failures don't block later items.
    """
    out: list[IngestOutcome] = []
    for mid in match_ids:
        try:
            out.append(await ingest_one(
                mid, client=client, af_cache=af_cache, now=now,
            ))
        except APIFootballError as e:
            out.append(IngestOutcome(mid, "error", error=f"{e.kind}: {e}"))
    return out
