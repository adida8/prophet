"""
Cross-platform odds comparison.

Priority:
  1. Explicit pairs from data/market_mappings.json (polarity-verified by hand)
  2. Fuzzy Jaccard matches for remaining markets
  3. High-volume unmatched markets shown as single-platform rows

Polarity handling: if a mapping has polarity="inverted", the Polymarket NO
price is treated as the YES equivalent when computing best prices and arb.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.market_normalizer import NormalizedMarket, match_markets

import config

log = logging.getLogger("prophet.comparator")

MAPPINGS_PATH = Path(__file__).parent.parent / "data" / "market_mappings.json"


# ── Data classes ──────────────────────────────────────────────────────

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
    source: str = "fuzzy"  # "explicit" | "fuzzy" | "single"

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
            "source":            self.source,
        }


# ── Explicit mapping loader ───────────────────────────────────────────

def _load_mappings() -> list[dict]:
    try:
        data = json.loads(MAPPINGS_PATH.read_text())
        return data.get("mappings", [])
    except Exception as e:
        log.warning("Could not load market_mappings.json: %s", e)
        return []


def _index_by(markets: list[NormalizedMarket], key: str) -> dict[str, NormalizedMarket]:
    """Build a lookup dict by platform_id."""
    return {m.platform_id: m for m in markets}


# ── Main build function ───────────────────────────────────────────────

def build_compared_markets(
    kalshi_markets: list[NormalizedMarket],
    poly_markets:   list[NormalizedMarket],
) -> list[ComparedMarket]:
    """
    Build ComparedMarket rows with explicit mappings taking priority over fuzzy.
    Sorted by total volume descending.
    """
    mappings = _load_mappings()
    k_by_id  = _index_by(kalshi_markets, "platform_id")
    pm_by_id = _index_by(poly_markets,   "platform_id")

    used_kalshi: set[str] = set()
    used_poly:   set[str] = set()
    results: list[ComparedMarket] = []

    # ── Phase 1: Explicit mappings ────────────────────────────────────
    for mapping in mappings:
        k_cfg  = mapping.get("kalshi")   or {}
        pm_cfg = mapping.get("polymarket") or {}
        polarity = mapping.get("polarity", "same")

        k_ticker = k_cfg.get("ticker", "")
        pm_id    = pm_cfg.get("id", "")

        km = k_by_id.get(k_ticker) if k_ticker else None
        pm = pm_by_id.get(pm_id)   if pm_id    else None

        if km is None and pm is None:
            continue  # neither platform returned this market right now

        platform_markets: dict[str, NormalizedMarket] = {}
        if km:
            platform_markets["kalshi"] = km
            used_kalshi.add(k_ticker)
        if pm:
            # Apply polarity inversion: swap YES/NO on Polymarket if inverted
            if polarity == "inverted" and pm:
                pm = _invert(pm)
            platform_markets["polymarket"] = pm
            used_poly.add(pm_id)

        category = mapping.get("category") or (km or pm).category
        resolution = (km.resolution_date if km else None) or (pm.resolution_date if pm else None)
        source = "explicit" if (km and pm) else "single"

        results.append(_make_compared(
            cid=mapping["id"],
            title=mapping.get("title") or (km or pm).title,
            category=category,
            resolution_date=resolution,
            platform_markets=platform_markets,
            source=source,
        ))

    # ── Phase 2: Fuzzy matches for remaining markets ──────────────────
    remaining_k  = [m for m in kalshi_markets  if m.platform_id not in used_kalshi]
    remaining_pm = [m for m in poly_markets    if m.platform_id not in used_poly]

    fuzzy_pairs = match_markets(remaining_k, remaining_pm, threshold=config.MATCH_THRESHOLD)
    for km, pm, _ in fuzzy_pairs:
        results.append(_make_compared(
            cid=f"match:{km.platform_id}",
            title=km.title,
            category=km.category,
            resolution_date=km.resolution_date or pm.resolution_date,
            platform_markets={"kalshi": km, "polymarket": pm},
            source="fuzzy",
        ))
        used_kalshi.add(km.platform_id)
        used_poly.add(pm.platform_id)

    # ── Phase 3: High-volume unmatched markets ────────────────────────
    unmatched_k = sorted(
        [m for m in kalshi_markets if m.platform_id not in used_kalshi],
        key=lambda m: m.volume_24h, reverse=True,
    )[:20]
    for m in unmatched_k:
        results.append(_make_compared(m.id, m.title, m.category, m.resolution_date, {m.platform: m}, "single"))

    unmatched_pm = sorted(
        [m for m in poly_markets if m.platform_id not in used_poly],
        key=lambda m: m.volume_24h, reverse=True,
    )[:30]
    for m in unmatched_pm:
        results.append(_make_compared(m.id, m.title, m.category, m.resolution_date, {m.platform: m}, "single"))

    results.sort(key=lambda c: c.total_volume_24h, reverse=True)
    return results


# ── Helpers ───────────────────────────────────────────────────────────

def _invert(m: NormalizedMarket) -> NormalizedMarket:
    """Return a copy with YES/NO swapped (for polarity=inverted mappings)."""
    from dataclasses import replace
    return replace(
        m,
        yes_price=m.no_price,
        no_price=m.yes_price,
        best_bid=round(1.0 - m.best_ask, 4),
        best_ask=round(1.0 - m.best_bid, 4),
    )


def _make_compared(
    cid: str,
    title: str,
    category: str,
    resolution_date: Optional[datetime],
    platform_markets: dict[str, NormalizedMarket],
    source: str = "fuzzy",
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
        source=source,
    )
