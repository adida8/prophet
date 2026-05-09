"""Kalshi prices — STUB.

The Kalshi football catalog is thin and the API is auth-gated. We
return an empty `MarketSnapshot` here so the verdict layer's "best
across venues" still works — best_for() simply has no Kalshi entry.
v1.1 will wire this live.
"""

from __future__ import annotations

from datetime import datetime, timezone

from desk.verdict.compare import MarketSnapshot


def prices_for(match_id: str) -> MarketSnapshot:
    return MarketSnapshot(
        match_id=match_id,
        asof=datetime.now(tz=timezone.utc),
        prices=(),
    )
