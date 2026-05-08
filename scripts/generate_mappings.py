#!/usr/bin/env python3
"""
Generate market_mappings.json candidates by fetching both platforms and
running the fuzzy matcher at a low threshold.

Run from project root with valid Kalshi credentials:
    python scripts/generate_mappings.py > /tmp/candidates.json

Review the output, correct polarity (same/inverted), set verified=true,
then copy confirmed entries into data/market_mappings.json.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from core.client import KalshiClient
from core.polymarket_client import PolymarketClient
from core.market_normalizer import normalize_kalshi, normalize_polymarket, match_markets


async def main() -> None:
    kc = KalshiClient()
    pc = PolymarketClient()

    print("Fetching Kalshi markets...", file=sys.stderr)
    try:
        resp = await kc.get_markets(limit=200, status="open")
        k_raw = resp.get("markets", [])
    except Exception as e:
        print(f"Kalshi fetch failed: {e}", file=sys.stderr)
        k_raw = []

    print("Fetching Polymarket markets...", file=sys.stderr)
    pm_raw = await pc.get_markets(limit=200)

    await kc.close()
    await pc.close()

    k_markets = [m for m in (normalize_kalshi(r) for r in k_raw) if m and m.yes_price > 0]
    pm_markets = [m for m in (normalize_polymarket(r) for r in pm_raw) if m and m.yes_price > 0]

    print(f"Kalshi: {len(k_markets)}, Polymarket: {len(pm_markets)}", file=sys.stderr)

    pairs = match_markets(k_markets, pm_markets, threshold=0.20)
    pairs.sort(key=lambda x: -x[2])

    print(f"Matched pairs: {len(pairs)}", file=sys.stderr)

    mappings = []
    for i, (km, pm, score) in enumerate(pairs[:20]):
        mappings.append({
            "id": f"auto-{i:02d}",
            "title": pm.title,
            "category": km.category or pm.category,
            "polarity": "same",
            "match_score": round(score, 3),
            "kalshi": {
                "ticker": km.platform_id,
                "title": km.title,
                "yes_price": km.yes_price,
            },
            "polymarket": {
                "id": pm.platform_id,
                "title": pm.title,
                "yes_price": pm.yes_price,
            },
            "verified": False,
            "notes": "REVIEW: confirm polarity (same/inverted) and title",
        })

    print(json.dumps({"version": "1.0", "mappings": mappings}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
