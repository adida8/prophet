"""Polymarket — extract per-side implied probabilities from a gamma event.

The gamma response we already pull during fixture ingest carries the
prices we need; no extra HTTP call. Each football match event ships
three sub-markets:

  "Will <home> win on <date>?"             → side "a"
  "Will <home> vs. <away> end in a draw?"  → side "draw"
  "Will <away> win on <date>?"             → side "b"

Each market's "Yes" outcome price is the implied probability of that
side. We match the team name in the market `question` against the
fixture's `team_a` / `team_b` to assign sides robustly.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from desk.verdict.compare import MarketSnapshot, Side, VenuePrice

log = logging.getLogger("desk.ingest.polymarket_prices")


def _parse_outcome_prices(raw: Any) -> list[float] | None:
    """Polymarket sends `outcomePrices` as a JSON-encoded string of strings.
    Handle both that shape and the already-decoded list form.
    """
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


def _yes_index(outcomes: Any) -> int | None:
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            return None
    if not isinstance(outcomes, list):
        return None
    for i, o in enumerate(outcomes):
        if isinstance(o, str) and o.strip().lower() == "yes":
            return i
    return None


def _classify_market(question: str, *, team_a: str, team_b: str) -> Side | None:
    """Match the question text against the fixture's two teams."""
    q = (question or "").lower()
    if "draw" in q or "end in a draw" in q:
        return "draw"

    a = team_a.lower()
    b = team_b.lower()
    if a in q and b not in q:
        return "a"
    if b in q and a not in q:
        return "b"
    if a in q and b in q:
        return "draw" if "draw" in q else None
    return None


def _strip_accents_lower(s: str) -> str:
    """Polymarket sometimes drops accents from `outcomes`; we normalise to
    plain ASCII lowercase so 'Bayern München' matches a market that drops
    the umlaut.
    """
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    ).lower()


def prices_from_polymarket_event(
    ev: dict[str, Any],
    *,
    match_id: str,
    team_a: str,
    team_b: str,
    asof: datetime | None = None,
) -> MarketSnapshot:
    """Extract a `MarketSnapshot` from one gamma event row."""
    asof = asof or datetime.now(tz=timezone.utc)
    out: list[VenuePrice] = []

    a_norm = _strip_accents_lower(team_a)
    b_norm = _strip_accents_lower(team_b)

    for m in ev.get("markets", []) or []:
        question_norm = _strip_accents_lower(m.get("question") or "")
        side = _classify_market(question_norm, team_a=a_norm, team_b=b_norm)
        if side is None:
            continue

        prices = _parse_outcome_prices(m.get("outcomePrices"))
        if not prices:
            continue
        yi = _yes_index(m.get("outcomes"))
        if yi is None or yi >= len(prices):
            continue

        yes_p = prices[yi]
        if not (0.0 <= yes_p <= 1.0):
            continue
        out.append(VenuePrice(venue="polymarket", side=side, implied_p=yes_p))

    return MarketSnapshot(match_id=match_id, asof=asof, prices=tuple(out))
