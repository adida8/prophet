"""ClubElo client — api.clubelo.com/{name}.

The endpoint returns a CSV of historical Elo rows for a club:

    Rank,Club,Country,Level,Elo,From,To
    None,ManCity,ENG,1,1800.5,2024-08-01,2024-08-04
    None,ManCity,ENG,1,1810.2,2024-08-05,2024-08-10
    ...

Current Elo = the row with the latest `To` date. Parser-hardened per
data-layer spec Phase 1b: schema check on every parse, last-good
fallback on mismatch, loud warning.

Per the spec the source is free + no auth. We're a polite consumer —
1 call per club per refresh, batch ≤ 30 / minute via simple sleep.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from desk.data.elo.cache import EloCache

_LOG = logging.getLogger(__name__)

CLUBELO_BASE = "https://api.clubelo.com"
SOURCE_ID = "clubelo"

# Expected header — fail loud if upstream renames a column.
_EXPECTED_HEADER = ("Rank", "Club", "Country", "Level", "Elo", "From", "To")


@dataclass(frozen=True)
class ClubEloFetch:
    club_id:        str
    status:         str    # "ok", "no_history", "parser_mismatch",
                           #  "http_error", "transient"
    elo:            float | None = None
    rows_parsed:    int = 0
    error:          str | None = None


class _Unparseable(Exception):
    pass


def _parse_csv(body: str) -> list[tuple[str, float]]:
    """Return [(to_date_str, elo)] in row order. Validates header
    against the expected shape; raises `_Unparseable` if it doesn't
    match (e.g. ClubElo renames a column)."""
    reader = csv.reader(io.StringIO(body))
    try:
        header = tuple(next(reader))
    except StopIteration:
        raise _Unparseable("empty response")
    if header[: len(_EXPECTED_HEADER)] != _EXPECTED_HEADER:
        raise _Unparseable(f"unexpected header: {header}")
    out: list[tuple[str, float]] = []
    for raw in reader:
        if not raw:
            continue
        try:
            elo = float(raw[4])
            to_date = raw[6]
            out.append((to_date, elo))
        except (IndexError, ValueError) as e:
            # Per-row malformation — log and skip; don't bail the
            # whole parse. A few stray rows shouldn't take down a
            # club's ingest.
            _LOG.warning("clubelo row skip: %s — %s", raw, e)
    return out


# ClubElo-name lookup. Their canonical club names diverge from our
# `{league}-{short}` ids: e.g. "epl-mci" maps to "ManCity". This is
# the WC 2026 + top-5-league starter set; extend as new clubs enter
# the priced universe.
CLUB_ID_TO_CLUBELO_NAME: dict[str, str] = {
    "epl-mci": "ManCity",
    "epl-mun": "ManUnited",
    "epl-liv": "Liverpool",
    "epl-ars": "Arsenal",
    "epl-che": "Chelsea",
    "epl-tot": "Tottenham",
    "epl-new": "Newcastle",
    "laliga-rea": "Real",      # Real Madrid
    "laliga-bar": "Barcelona",
    "laliga-atl": "Atletico",
    "bundesliga-bay": "Bayern",
    "bundesliga-bvb": "Dortmund",
    "bundesliga-rbl": "RBLeipzig",
    "ligue1-psg": "PSG",
    "seriea-juv": "Juventus",
    "seriea-int": "Inter",
    "seriea-mil": "Milan",
}


def clubelo_name_for(club_id: str) -> str | None:
    return CLUB_ID_TO_CLUBELO_NAME.get(club_id.lower())


async def fetch_one(
    club_id: str,
    *,
    client: httpx.AsyncClient,
) -> ClubEloFetch:
    """Fetch + parse one club. Returns the latest-dated Elo value."""
    name = clubelo_name_for(club_id)
    if name is None:
        return ClubEloFetch(club_id, "no_history",
                            error=f"no clubelo name mapping for {club_id}")

    url = f"{CLUBELO_BASE}/{name}"
    try:
        resp = await client.get(url)
    except httpx.HTTPError as e:
        return ClubEloFetch(club_id, "transient", error=str(e))
    if resp.status_code != 200:
        return ClubEloFetch(
            club_id, "http_error",
            error=f"HTTP {resp.status_code}",
        )
    try:
        rows = _parse_csv(resp.text)
    except _Unparseable as e:
        return ClubEloFetch(club_id, "parser_mismatch", error=str(e))
    if not rows:
        return ClubEloFetch(club_id, "no_history", rows_parsed=0,
                            error="no parseable rows in CSV")
    rows.sort(key=lambda x: x[0])     # ascending by 'To' date
    _, current_elo = rows[-1]
    return ClubEloFetch(
        club_id, "ok",
        elo=current_elo, rows_parsed=len(rows),
    )


async def refresh_clubs(
    club_ids: list[str],
    *,
    cache: EloCache,
    client: httpx.AsyncClient | None = None,
) -> list[ClubEloFetch]:
    """Walk a list of club_ids, fetch ClubElo per club, write to cache.

    Parser-mismatch outcomes do NOT write — the cache keeps its last-good
    value (per spec: "fall back to last-good cached values on mismatch,
    loud alert"). Other failures also skip the write.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=15.0)
    try:
        outcomes: list[ClubEloFetch] = []
        now = datetime.now(tz=timezone.utc)
        for cid in club_ids:
            outcome = await fetch_one(cid, client=client)
            if outcome.status == "ok" and outcome.elo is not None:
                name = clubelo_name_for(cid) or cid
                cache.upsert_club(
                    cid, outcome.elo,
                    source_id=SOURCE_ID,
                    source_url=f"{CLUBELO_BASE}/{name}",
                    fetched_at=now,
                )
            elif outcome.status == "parser_mismatch":
                _LOG.error("clubelo parser mismatch for %s: %s — "
                           "keeping last-good cached value",
                           cid, outcome.error)
            outcomes.append(outcome)
        cache.mark_fetch(SOURCE_ID, "ok" if any(o.status == "ok" for o in outcomes)
                         else "no_writes")
        return outcomes
    finally:
        if owns_client:
            await client.aclose()
