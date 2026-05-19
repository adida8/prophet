"""Pull the WC 2026 winner market from Polymarket gamma.

One outright event = N child binary markets ("Will <team> win the 2026
FIFA World Cup?"), each with a YES outcome price and a NO outcome
price. We surface them as per-team `OutrightPrice` rows so the decide
step can score YES and NO independently.

Field / Any-Other-Team / placeholder (Team AM / Team AN / …) markets
are skipped — they aren't real participants.

This is the local-Prophet build — straight HTTP to gamma, no Supabase.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

log = logging.getLogger("desk.outrights.ingest")

GAMMA_URL  = "https://gamma-api.polymarket.com"
EVENT_SLUG = "2026-fifa-world-cup-winner-595"

# "Will <team> win the 2026 FIFA World Cup?" — tolerant of trailing
# whitespace / missing '?' / variant phrasings.
_QUESTION_RE = re.compile(r"^Will (.+?) win the 2026 FIFA World Cup\?*\s*$")

# Polymarket sometimes uses placeholder participants. None of these
# map to a real WC qualifier; the simulator has nothing to say about
# them, so drop.
_PLACEHOLDER_PREFIXES = ("team a", "team b", "team c", "team d", "any other")

# Polymarket → canonical team name. Canonical names match the strings
# already used in match JSONs (`team_a` / `team_b`) and in
# `wc26_data.TEAM_ELO`. Names not listed here pass through unchanged.
_NAME_ALIASES: dict[str, str] = {
    "Turkiye":            "Türkiye",
    "South Korea":        "Korea Republic",
    "Ivory Coast":        "Côte d'Ivoire",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Iran":               "IR Iran",
    "Congo DR":           "DR Congo",
    "Cape Verde":         "Cabo Verde",
}


def _canonical(team: str) -> str:
    return _NAME_ALIASES.get(team, team)


@dataclass(frozen=True)
class OutrightPrice:
    team:        str
    yes_p:       float       # market-implied P(team wins), in [0, 1]
    no_p:        float       # market price of the NO side
    market_url:  str         # deep-link to the per-team binary market
    venue:       str = "polymarket"


@dataclass(frozen=True)
class OutrightSnapshot:
    event_id:        str               # Polymarket event id (stable across runs)
    event_slug:      str
    title:           str
    resolution_utc:  datetime          # event endDate (tournament close)
    asof:            datetime
    prices:          tuple[OutrightPrice, ...]
    overround:       float             # sum(yes_p) − 1.0; diagnostic


def _parse_prices(raw) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, list):
        return None
    try:
        return [float(x) for x in raw]
    except (TypeError, ValueError):
        return None


def _is_placeholder(team: str) -> bool:
    low = team.lower().strip()
    return any(low.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _team_market_url(event_slug: str, market: dict) -> str:
    """Polymarket exposes each binary as part of the parent event; the
    safest deep link is the event page itself. Per-market deep links
    exist via `conditionId`, but the event page surfaces the team
    binary cleanly enough for the Pick CTA.
    """
    return f"https://polymarket.com/event/{event_slug}"


async def fetch_snapshot(*, asof: datetime | None = None) -> OutrightSnapshot:
    """Hit gamma, parse the WC winner event, return one snapshot."""
    asof = asof or datetime.now(tz=timezone.utc)
    async with httpx.AsyncClient(
        base_url=GAMMA_URL,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"Accept": "application/json"},
    ) as client:
        r = await client.get("/events", params={"slug": EVENT_SLUG})
        r.raise_for_status()
        events = r.json()

    if not events:
        raise RuntimeError(f"polymarket event not found: {EVENT_SLUG}")

    ev = events[0]
    end_date = ev.get("endDate") or ""
    try:
        resolution_utc = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except ValueError as e:
        raise RuntimeError(f"unparseable endDate on {EVENT_SLUG}: {end_date}") from e

    prices: list[OutrightPrice] = []
    skipped_placeholder = 0
    skipped_no_price = 0

    for m in ev.get("markets") or []:
        q = (m.get("question") or "").strip()
        mt = _QUESTION_RE.match(q)
        if not mt:
            continue

        raw_team = mt.group(1).strip()
        if _is_placeholder(raw_team):
            skipped_placeholder += 1
            continue
        team = _canonical(raw_team)

        op = _parse_prices(m.get("outcomePrices"))
        if not op or len(op) < 2:
            skipped_no_price += 1
            continue

        yes_p, no_p = op[0], op[1]
        # Polymarket lists eliminated / not-qualified teams at 0.0 YES,
        # 1.0 NO. Drop those — they aren't in the field.
        if yes_p <= 0.0:
            continue
        if not (0.0 < yes_p < 1.0):
            continue

        prices.append(OutrightPrice(
            team=team,
            yes_p=yes_p,
            no_p=no_p,
            market_url=_team_market_url(EVENT_SLUG, m),
        ))

    overround = sum(p.yes_p for p in prices) - 1.0
    log.info(
        "polymarket outright: %d teams priced (placeholders skipped: %d, no-price: %d, overround %.2fpp)",
        len(prices), skipped_placeholder, skipped_no_price, overround * 100,
    )
    return OutrightSnapshot(
        event_id=str(ev.get("id") or ""),
        event_slug=EVENT_SLUG,
        title=ev.get("title", "").strip(),
        resolution_utc=resolution_utc,
        asof=asof,
        prices=tuple(prices),
        overround=overround,
    )
