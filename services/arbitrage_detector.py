"""
Detect and rank arbitrage opportunities across prediction market platforms.

A risk-free edge exists when:
    YES_price_A + NO_price_B < 1.00  (buy YES on A, buy NO on B)
Edge % = (1 - total_cost) / total_cost * 100
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import config
from services.odds_comparator import ComparedMarket


@dataclass
class ArbitrageOpportunity:
    id: str
    market_title: str
    category: str
    buy_yes_platform: str
    buy_yes_price: float
    buy_no_platform: str
    buy_no_price: float
    edge_pct: float
    total_volume_24h: float

    def to_dict(self) -> dict:
        return {
            "id":                self.id,
            "market_title":      self.market_title,
            "category":          self.category,
            "buy_yes_platform":  self.buy_yes_platform,
            "buy_yes_price":     self.buy_yes_price,
            "buy_no_platform":   self.buy_no_platform,
            "buy_no_price":      self.buy_no_price,
            "edge_pct":          self.edge_pct,
            "total_volume_24h":  self.total_volume_24h,
        }


def detect_arbitrage(
    compared: list[ComparedMarket],
    min_edge_pct: float = None,
) -> list[ArbitrageOpportunity]:
    """
    Scan ComparedMarket rows for cross-platform arb, return sorted by edge desc.
    """
    if min_edge_pct is None:
        min_edge_pct = config.ARB_MIN_EDGE_PCT

    opportunities: list[ArbitrageOpportunity] = []

    for cm in compared:
        if len(cm.platforms) < 2:
            continue

        platforms = list(cm.platforms.items())

        # Try all ordered pairs (A=buy YES, B=buy NO)
        for i, (p_a, price_a) in enumerate(platforms):
            for j, (p_b, price_b) in enumerate(platforms):
                if i == j:
                    continue

                yes_cost = price_a.yes_price
                no_cost  = price_b.no_price
                if yes_cost <= 0 or no_cost <= 0:
                    continue

                total = yes_cost + no_cost
                if total >= 1.0:
                    continue

                edge_pct = round((1.0 - total) / total * 100, 2)
                if edge_pct < min_edge_pct:
                    continue

                opportunities.append(ArbitrageOpportunity(
                    id=f"{cm.id}:yes_{p_a}:no_{p_b}",
                    market_title=cm.title,
                    category=cm.category,
                    buy_yes_platform=p_a,
                    buy_yes_price=yes_cost,
                    buy_no_platform=p_b,
                    buy_no_price=no_cost,
                    edge_pct=edge_pct,
                    total_volume_24h=cm.total_volume_24h,
                ))

    # Deduplicate (keep highest-edge version per market)
    seen: dict[str, ArbitrageOpportunity] = {}
    for opp in sorted(opportunities, key=lambda o: o.edge_pct, reverse=True):
        key = opp.market_title
        if key not in seen:
            seen[key] = opp

    return sorted(seen.values(), key=lambda o: o.edge_pct, reverse=True)
