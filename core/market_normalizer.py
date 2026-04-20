"""
Normalize Kalshi and Polymarket API responses into a unified NormalizedMarket
schema, and fuzzy-match equivalent markets across platforms.
"""

from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import config

log = logging.getLogger("prophet.normalizer")

# ── Canonical category mapping ────────────────────────────────────────

_CATEGORY_MAP: dict[str, str] = {
    "sports": "sports", "sport": "sports",
    "politics": "politics", "political": "politics",
    "elections": "politics", "election": "politics",
    "geopolitics": "politics",
    "crypto": "crypto", "cryptocurrency": "crypto",
    "economics": "economy", "economy": "economy",
    "economic": "economy", "finance": "economy",
    "business": "economy", "business & finance": "economy",
    "culture": "culture", "entertainment": "culture",
    "pop culture": "culture", "technology": "culture",
    "science": "culture", "tech": "culture",
}

_STOP_WORDS = {
    "will", "the", "a", "an", "by", "on", "in", "at", "to", "for",
    "of", "be", "is", "are", "was", "were", "has", "have", "had",
    "or", "and", "its", "this", "that", "these", "those", "does",
    "above", "below", "between", "before", "after", "during",
}


def _norm_category(raw: str) -> str:
    key = (raw or "").lower().strip()
    return _CATEGORY_MAP.get(key, "other")


def _to_decimal(price: float) -> float:
    """Convert cents (0-100) to decimal (0-1) if needed."""
    return price / 100.0 if price > 1.0 else price


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Unified schema ────────────────────────────────────────────────────

@dataclass
class NormalizedMarket:
    id: str                          # "kalshi:{ticker}" or "polymarket:{id}"
    title: str
    category: str
    platform: str                    # "kalshi" | "polymarket"
    platform_id: str
    yes_price: float                 # 0.0 – 1.0
    no_price: float
    best_bid: float
    best_ask: float
    volume_24h: float                # USD
    resolution_date: Optional[datetime]
    last_updated: datetime
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "platform": self.platform,
            "platform_id": self.platform_id,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "volume_24h": self.volume_24h,
            "resolution_date": self.resolution_date.isoformat() if self.resolution_date else None,
            "last_updated": self.last_updated.isoformat(),
            "url": self.url,
        }


# ── Kalshi normalizer ─────────────────────────────────────────────────

def normalize_kalshi(market: dict) -> Optional[NormalizedMarket]:
    try:
        ticker = market.get("ticker", "")
        if not ticker:
            return None

        # T1.2: Skip markets that aren't open/active
        status = (market.get("status") or "").lower()
        if status and status not in ("active", "open"):
            return None

        close_time = _parse_dt(market.get("close_time") or market.get("expiration_time"))
        if close_time and close_time < _now():
            return None

        # T1.1: Mid-price from spread; fall back to last_price
        yes_bid = _to_decimal(float(market.get("yes_bid") or 0))
        yes_ask = _to_decimal(float(market.get("yes_ask") or 0))
        no_bid  = _to_decimal(float(market.get("no_bid") or 0))
        no_ask  = _to_decimal(float(market.get("no_ask") or 0))

        if yes_bid and yes_ask:
            yes_price = (yes_bid + yes_ask) / 2
        elif yes_bid or yes_ask:
            yes_price = yes_bid or yes_ask
        else:
            last = _to_decimal(float(market.get("last_price") or 0))
            yes_price = last

        if not yes_price:
            return None  # T1.1: drop markets with no price data

        no_price = (no_bid + no_ask) / 2 if (no_bid and no_ask) else (no_bid or no_ask)
        if not no_price:
            no_price = round(1.0 - yes_price, 4)

        volume_24h = float(market.get("volume_24h") or market.get("volume") or 0)
        volume_24h = volume_24h / 100.0  # Kalshi volumes are in cents

        # T1.3: Prefer yes_sub_title > title > ticker
        title = market.get("yes_sub_title") or market.get("title") or ticker

        # T1.4: UTM affiliate link
        event_ticker = market.get("event_ticker", ticker)
        url = f"https://kalshi.com/markets/{event_ticker}?{config.UTM_PARAMS}"

        return NormalizedMarket(
            id=f"kalshi:{ticker}",
            title=title,
            category=_norm_category(market.get("category", "")),
            platform="kalshi",
            platform_id=ticker,
            yes_price=round(yes_price, 4),
            no_price=round(no_price, 4),
            best_bid=round(yes_bid, 4),
            best_ask=round(yes_ask, 4),
            volume_24h=round(volume_24h, 2),
            resolution_date=close_time,
            last_updated=_now(),
            url=url,
        )
    except Exception as e:
        log.debug("normalize_kalshi failed for %s: %s", market.get("ticker"), e)
        return None


# ── Polymarket normalizer ─────────────────────────────────────────────

def normalize_polymarket(market: dict) -> Optional[NormalizedMarket]:
    try:
        market_id = str(market.get("id", ""))
        if not market_id:
            return None

        # T1.2: Drop closed or inactive markets
        if market.get("closed") or not market.get("active"):
            return None

        end_date = _parse_dt(market.get("endDate") or market.get("end_date_iso"))
        if end_date and end_date < _now():
            return None

        # outcomePrices is a JSON string like '["0.67","0.33"]'
        raw_prices = market.get("outcomePrices", "[]")
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices

        raw_outcomes = market.get("outcomes", '["Yes","No"]')
        outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes

        yes_idx, no_idx = 0, 1
        for i, o in enumerate(outcomes):
            s = str(o).lower()
            if s in ("yes", "true"):
                yes_idx = i
            elif s in ("no", "false"):
                no_idx = i

        yes_price = float(prices[yes_idx]) if len(prices) > yes_idx else 0.5
        no_price  = float(prices[no_idx])  if len(prices) > no_idx  else 0.5

        volume_24h = float(market.get("volume24hr") or market.get("volume24h") or 0)

        category_raw = market.get("category") or market.get("tag") or ""
        if isinstance(category_raw, dict):
            category_raw = category_raw.get("label", "")

        # T1.3: question is the canonical readable title
        title = market.get("question") or market.get("title") or ""

        # T1.4: UTM affiliate link
        slug = market.get("slug", market_id)
        url = f"https://polymarket.com/event/{slug}?{config.UTM_PARAMS}"

        return NormalizedMarket(
            id=f"polymarket:{market_id}",
            title=title,
            category=_norm_category(category_raw),
            platform="polymarket",
            platform_id=market_id,
            yes_price=round(yes_price, 4),
            no_price=round(no_price, 4),
            best_bid=round(max(yes_price - 0.01, 0.0), 4),
            best_ask=round(min(yes_price + 0.01, 1.0), 4),
            volume_24h=round(volume_24h, 2),
            resolution_date=end_date,
            last_updated=_now(),
            url=url,
        )
    except Exception as e:
        log.debug("normalize_polymarket failed for %s: %s", market.get("id"), e)
        return None


# ── Fuzzy title matching ──────────────────────────────────────────────

def _tokenize(title: str) -> frozenset[str]:
    tokens = re.findall(r"\b\w+\b", title.lower())
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 2)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_markets(
    kalshi: list[NormalizedMarket],
    polymarket: list[NormalizedMarket],
    threshold: float = 0.30,
) -> list[tuple[NormalizedMarket, NormalizedMarket, float]]:
    """
    Greedily match Kalshi markets to Polymarket markets by Jaccard title similarity.
    Each market is matched at most once.  Returns (kalshi_m, poly_m, score) tuples.
    """
    poly_tokens = [(m, _tokenize(m.title)) for m in polymarket]
    used_poly: set[str] = set()
    candidates: list[tuple[NormalizedMarket, NormalizedMarket, float]] = []

    for km in kalshi:
        kt = _tokenize(km.title)
        best_score = 0.0
        best_pm: Optional[NormalizedMarket] = None
        for pm, pt in poly_tokens:
            if pm.id in used_poly:
                continue
            score = _jaccard(kt, pt)
            if score > best_score:
                best_score = score
                best_pm = pm
        if best_score >= threshold and best_pm:
            candidates.append((km, best_pm, best_score))
            used_poly.add(best_pm.id)

    return candidates


# ── Helpers ───────────────────────────────────────────────────────────

def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
