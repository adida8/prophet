"""
Aggregate cross-platform statistics for the dashboard header cards.
"""

from __future__ import annotations

from core.market_normalizer import NormalizedMarket
from services.odds_comparator import ComparedMarket
from services.arbitrage_detector import ArbitrageOpportunity

PLATFORM_META = {
    "kalshi": {
        "name":          "Kalshi",
        "type":          "CFTC Regulated · USD",
        "weekly_vol":    "$3.54B",
        "market_count":  "8,200+",
        "fee":           "0%",
        "avg_spread":    "3-5¢",
        "url":           "https://kalshi.com",
        "utm":           "?utm_source=predictionedge&utm_medium=referral",
    },
    "polymarket": {
        "name":          "Polymarket",
        "type":          "CFTC via QCEX · USDC",
        "weekly_vol":    "$2.48B",
        "market_count":  "4,600+",
        "fee":           "0%",
        "avg_spread":    "2-4¢",
        "url":           "https://polymarket.com",
        "utm":           "?utm_source=predictionedge&utm_medium=referral",
    },
    "draftkings": {
        "name":          "DraftKings",
        "type":          "CFTC via CME · USD",
        "weekly_vol":    "$380M",
        "market_count":  "1,200+",
        "fee":           "~4¢ RT",
        "avg_spread":    "4-6¢",
        "url":           "https://draftkings.com",
        "utm":           "?utm_source=predictionedge&utm_medium=referral",
    },
}


def compute_stats(
    all_markets:  list[NormalizedMarket],
    arb_opps:     list[ArbitrageOpportunity],
    movers_24h:   list[dict],
) -> dict:
    """Aggregate stats for the 4 header stat cards."""
    total_volume = sum(m.volume_24h for m in all_markets)
    total_markets = len(all_markets)
    arb_count = len(arb_opps)
    avg_edge = (
        sum(o.edge_pct for o in arb_opps) / arb_count if arb_count else 0.0
    )

    biggest_mover: dict = {}
    if movers_24h:
        bm = movers_24h[0]
        biggest_mover = {
            "title":       bm["title"],
            "current":     bm["current_price"],
            "change_abs":  bm["change_abs"],
            "change_pct":  bm["change_pct"],
            "platform":    bm["platform"],
        }

    return {
        "total_volume_24h": round(total_volume, 2),
        "total_markets":    total_markets,
        "arb_count":        arb_count,
        "avg_arb_edge_pct": round(avg_edge, 1),
        "biggest_mover":    biggest_mover,
    }


def compute_platform_stats(markets: list[NormalizedMarket]) -> dict:
    """Per-platform breakdown of live market + volume counts."""
    by_platform: dict[str, dict] = {}
    for m in markets:
        entry = by_platform.setdefault(m.platform, {
            **PLATFORM_META.get(m.platform, {"name": m.platform}),
            "live_markets": 0,
            "live_volume_24h": 0.0,
        })
        entry["live_markets"]   += 1
        entry["live_volume_24h"] = round(entry["live_volume_24h"] + m.volume_24h, 2)

    # Always include the three platforms even if no live data yet
    for platform, meta in PLATFORM_META.items():
        if platform not in by_platform:
            by_platform[platform] = {**meta, "live_markets": 0, "live_volume_24h": 0.0}

    return by_platform


def build_ticker_items(compared: list[ComparedMarket], limit: int = 12) -> list[dict]:
    """Top markets for the scrolling ticker bar."""
    top = sorted(compared, key=lambda c: c.total_volume_24h, reverse=True)[:limit]
    return [
        {
            "title":    c.title[:40],
            "price":    c.best_yes_price,
            "platform": c.best_yes_platform,
            "gap":      c.price_gap,
        }
        for c in top
    ]
