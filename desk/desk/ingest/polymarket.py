"""Polymarket gamma client — football fixture lister.

We pull events with `tag_slug=games` (Polymarket's tag for individual
match events, as opposed to season-long markets) and filter to the
`soccer` sub-tag. The endpoint caps responses at 100 rows per page, so
we paginate via `offset` — without this, WC 2026 fixtures (which sort
onto pages 2+ behind shorter-dated esports / cricket markets) are
silently dropped.

Every match event has a slug like `fifwc-mex-rsa-2026-06-11`, a title
like "Mexico vs. South Africa", and an `endDate` that doubles as
kickoff.

We do NOT read prices here — PR 4 owns that. PR 2 only needs the fixture
identity.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from desk.ingest.base import Source, register

log = logging.getLogger("desk.ingest.polymarket")

GAMMA_URL = "https://gamma-api.polymarket.com"
DEFAULT_LIMIT = 100  # Polymarket caps a single /events response at 100.
MAX_PAGES = 30       # 30 × 100 = 3000 events — well beyond what we ever expect.

# `{prefix}-{home}-{away}-{yyyy-mm-dd}` (with optional `-more-markets` suffix).
_SLUG_RE = re.compile(
    r"^(?P<prefix>[a-z0-9]+)-(?P<home>[a-z0-9]+)-(?P<away>[a-z0-9]+)-"
    r"(?P<yyyy>\d{4})-(?P<mm>\d{2})-(?P<dd>\d{2})(?:-more-markets)?$"
)


def parse_slug(slug: str) -> dict[str, str] | None:
    m = _SLUG_RE.match(slug)
    if not m:
        return None
    return m.groupdict()


def parse_title(title: str) -> tuple[str, str] | None:
    """Polymarket titles use `Home vs. Away` (sometimes `Home vs Away`)."""
    title = re.sub(r"\s*-\s*More Markets$", "", title or "")
    m = re.split(r"\s+vs\.?\s+", title, maxsplit=1)
    if len(m) != 2:
        return None
    return m[0].strip(), m[1].strip()


class PolymarketSoccerEventsSource(Source):
    id    = "polymarket.soccer_events"
    label = "Polymarket — soccer match events"
    sport = "football"

    def __init__(self, *, limit: int = DEFAULT_LIMIT) -> None:
        super().__init__()
        self._limit = limit

    async def fetch(self) -> list[dict[str, Any]]:
        # Polymarket's /events endpoint caps each response at 100 rows even
        # when you ask for more, so paginate via `offset` until we hit an
        # empty / short page. The WC 2026 fixtures sit on page 2+, which is
        # why a single un-paginated call missed all 72 of them.
        all_events: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        async with httpx.AsyncClient(
            base_url=GAMMA_URL,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"Accept": "application/json"},
        ) as client:
            for page in range(MAX_PAGES):
                offset = page * self._limit
                r = await client.get(
                    "/events",
                    params={
                        "tag_slug": "games",
                        "closed":   "false",
                        "active":   "true",
                        "limit":    self._limit,
                        "offset":   offset,
                    },
                )
                r.raise_for_status()
                events = r.json()
                if not events:
                    break
                for e in events:
                    eid = str(e.get("id") or e.get("slug") or "")
                    if eid and eid not in seen_ids:
                        seen_ids.add(eid)
                        all_events.append(e)
                if len(events) < self._limit:
                    break

        log.info("polymarket gamma: fetched %d events across pages", len(all_events))
        return [e for e in all_events if "soccer" in {t.get("slug") for t in e.get("tags", [])}]


# Auto-register on import.
register(PolymarketSoccerEventsSource())
