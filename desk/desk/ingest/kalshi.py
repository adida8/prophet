"""Kalshi football fixture lister — STUB.

Kalshi's football coverage is thin compared to Polymarket and the API is
auth-gated. PR 2 ships an interface placeholder that returns an empty
list; live integration happens in v1.1 when there's an editorial reason
to compare a venue we don't already see on Polymarket.

Spec §3 calls out that v2's admin backend should be able to enable this
without code changes — the source registers itself even when it has
nothing to return.
"""

from __future__ import annotations

import logging
from typing import Any

from desk.ingest.base import Source, register

log = logging.getLogger("desk.ingest.kalshi")


class KalshiSoccerEventsSource(Source):
    id    = "kalshi.soccer_events"
    label = "Kalshi — soccer match events (stub)"
    sport = "football"

    async def fetch(self) -> list[dict[str, Any]]:
        log.debug("kalshi soccer source is a v1 stub — no fetch performed")
        return []


register(KalshiSoccerEventsSource())
