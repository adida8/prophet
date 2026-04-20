"""
Cross-platform odds comparison.

Takes matched (Kalshi, Polymarket) market pairs plus any unmatched markets
from either platform and produces ComparedMarket objects ready for the
dashboard table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.market_normalizer import NormalizedMarket, match_markets

import config


@dataclass
class PlatformPrice:
    yes_price: float
    no_price:  float
    volume_24h: float
    url: str


@dataclass
class ComparedMarket:
    id: str
    title: str
    category: str
    resolution_date: Optional[datetime]
    platforms: dict[str, PlatformPrice]   # platform → price info
    best_yes_platform: str
    best_yes_price: float
    best_no_platform: str
    best_no_price: float
    price_gap: float        # max_yes - min_yes across platforms
    total_volume_24h: float
    arb_edge_pct: float     # >0 if a risk-free edge exists

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "resolution_date": self.resolution_date.isoformat() if self.resolution_date else None,
            "platforms": {
                p: {
                    "yes_price":  v.yes_price,
                    "no_price":   v.no_price,
                    "volume_24h": v.volume_24h,
                    "url":        v.url,
                }
                for p, v in self.platforms.items()
            },
            "best_yes_platform": self.best_yes_platform,
            "best_yes_price":    self.best_yes_price,
            "best_no_platform":  self.best_no_platform,
            "best_no_price":     self.best_no_price,
            "price_gap":         self.price_gap,
            "total_volume_24h":  self.total_volume_24h,
            "arb_edge_pct":      self.arb_edge_pct,
        }


def build_compared_markets(
    kalshi_markets: list[NormalizedMarket],
    poly_markets:   list[NormalizedMarket],
) -> list[ComparedMarket]:
    """
    Match markets across platforms and return ComparedMarket objects,
    sorted by total volume descending.  Also surfaces top unmatched
    markets from each platform (single-platform rows).
    """
    matched_pairs = match_markets(
        kalshi_markets, poly_markets, threshold=config.MATCH_THRESHOLD
    )

    used_kalshi = {km.id for km, _, _ in matched_pairs}
    used_poly   = {pm.id for _, pm, _ in matched_pairs}

    results: list[ComparedMarket] = []

    # --- Matched rows (have prices from both platforms) ---
    for km, pm, _ in matched_pairs:
        results.append(_make_compared(
            f"match:{km.platform_id}",
            km.title,
            km.category,
            km.resolution_date or pm.resolution_date,
            {km.platform: km, pm.platform: pm},
        ))

    # --- Unmatched Kalshi (top 20 by volume) ---
    unmatched_k = sorted(
        [m for m in kalshi_markets if m.id not in used_kalshi],
        key=lambda m: m.volume_24h, reverse=True,
    )[:20]
    for m in unmatched_k:
        results.append(_make_compared(m.id, m.title, m.category, m.resolution_date, {m.platform: m}))

    # --- Unmatched Polymarket (top 30 by volume) ---
    unmatched_p = sorted(
        [m for m in poly_markets if m.id not in used_poly],
        key=lambda m: m.volume_24h, reverse=True,
    )[:30]
    for m in unmatched_p:
        results.append(_make_compared(m.id, m.title, m.category, m.resolution_date, {m.platform: m}))

    results.sort(key=lambda c: c.total_volume_24h, reverse=True)
    return results


def _make_compared(
    cid: str,
    title: str,
    category: str,
    resolution_date: Optional[datetime],
    platform_markets: dict[str, NormalizedMarket],
) -> ComparedMarket:
    platform_prices: dict[str, PlatformPrice] = {}
    for platform, m in platform_markets.items():
        platform_prices[platform] = PlatformPrice(
            yes_price=m.yes_price,
            no_price=m.no_price,
            volume_24h=m.volume_24h,
            url=m.url,
        )

    yes_prices = {p: v.yes_price for p, v in platform_prices.items() if v.yes_price > 0}
    no_prices  = {p: v.no_price  for p, v in platform_prices.items() if v.no_price  > 0}

    if yes_prices:
        best_yes_platform = max(yes_prices, key=yes_prices.__getitem__)
        best_yes_price    = yes_prices[best_yes_platform]
    else:
        best_yes_platform, best_yes_price = list(platform_prices)[0], 0.5

    if no_prices:
        best_no_platform = max(no_prices, key=no_prices.__getitem__)
        best_no_price    = no_prices[best_no_platform]
    else:
        best_no_platform, best_no_price = list(platform_prices)[0], 0.5

    price_gap = (max(yes_prices.values()) - min(yes_prices.values())) if len(yes_prices) > 1 else 0.0

    # Arb edge: buy YES on cheapest + buy NO on cheapest simultaneously
    if len(yes_prices) > 1:
        min_yes = min(yes_prices.values())
        min_no  = min(no_prices.values()) if no_prices else 1.0 - max(yes_prices.values())
        total_cost = min_yes + min_no
        arb_edge = (1.0 - total_cost) / total_cost * 100 if total_cost < 1.0 else 0.0
    else:
        arb_edge = 0.0

    return ComparedMarket(
        id=cid,
        title=title,
        category=category,
        resolution_date=resolution_date,
        platforms=platform_prices,
        best_yes_platform=best_yes_platform,
        best_yes_price=best_yes_price,
        best_no_platform=best_no_platform,
        best_no_price=best_no_price,
        price_gap=round(price_gap, 4),
        total_volume_24h=sum(v.volume_24h for v in platform_prices.values()),
        arb_edge_pct=round(arb_edge, 2),
    )
