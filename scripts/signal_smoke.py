#!/usr/bin/env python3
"""
T1.5 smoke test — verify the signal_engine adapter integrates with the
existing SimpleArbStrategy without modifying strategies/ code.

Run from the project root:
    python scripts/signal_smoke.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from core.market_normalizer import NormalizedMarket
from services.signal_engine import evaluate_market, evaluate_matched_pair


def make_market(platform: str, yes_price: float, no_price: float, ticker: str = "TEST-A") -> NormalizedMarket:
    return NormalizedMarket(
        id=f"{platform}:{ticker}",
        title="Smoke-test Market",
        category="other",
        platform=platform,
        platform_id=ticker,
        yes_price=yes_price,
        no_price=no_price,
        best_bid=round(max(yes_price - 0.01, 0.0), 4),
        best_ask=round(min(yes_price + 0.01, 1.0), 4),
        volume_24h=10_000.0,
        resolution_date=None,
        last_updated=datetime.now(timezone.utc),
        url=f"https://kalshi.com/markets/{ticker}",
    )


def run() -> bool:
    passed = failed = 0

    def check(label: str, sig, expect_signal: bool) -> None:
        nonlocal passed, failed
        ok = (sig is not None) == expect_signal
        status = "PASS" if ok else "FAIL"
        result = f"signal({sig.side} @ {sig.price:.2f})" if sig else "no signal"
        print(f"  [{status}] {label}: {result}")
        if sig and ok:
            print(f"         {sig.reason}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("\n── Single-market evaluate_market ────────────────────────")

    check(
        "Strong imbalance  (yes=0.30, no=0.72)",
        evaluate_market(make_market("kalshi", 0.30, 0.72)),
        True,
    )
    check(
        "Balanced market   (yes=0.52, no=0.48)",
        evaluate_market(make_market("kalshi", 0.52, 0.48)),
        False,
    )
    check(
        "At yes ceiling    (yes=0.45, no=0.60) — boundary, no signal",
        evaluate_market(make_market("kalshi", 0.45, 0.60)),
        False,
    )
    check(
        "Just below ceiling (yes=0.44, no=0.61)",
        evaluate_market(make_market("kalshi", 0.44, 0.61)),
        True,
    )

    print("\n── Cross-platform evaluate_matched_pair ─────────────────")

    km = make_market("kalshi",     0.38, 0.65, ticker="KXBTC-A")
    pm = make_market("polymarket", 0.42, 0.62, ticker="poly-btc")
    sig = evaluate_matched_pair(km, pm)
    check("Cross-platform (kalshi=0.38, poly=0.42 → best_yes=0.38)", sig, True)
    if sig:
        print(f"         ticker={sig.ticker}  confidence={sig.confidence:.2f}")

    km2 = make_market("kalshi",     0.55, 0.46, ticker="KXBTC-B")
    pm2 = make_market("polymarket", 0.50, 0.51, ticker="poly-btc2")
    check("Balanced cross-platform (kalshi=0.55, poly=0.50 → best_yes=0.50)", evaluate_matched_pair(km2, pm2), False)

    print(f"\n── Result: {passed} passed, {failed} failed ─────────────────\n")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
