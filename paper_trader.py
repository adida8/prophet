"""
Legacy paper-trading loop — extracted from original main.py.
Run with: python main.py --paper-trade
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import config
from core.client import KalshiClient, stream_tickers
from core.logger import get_portfolio_summary, record_trade
from risk_manager import size_position
import strategies.simple_arb as _arb_module

log = logging.getLogger("prophet.paper_trader")

_balance = config.STARTING_BALANCE


from dataclasses import dataclass

@dataclass
class _Signal:
    ticker: str
    side: str
    price: float
    confidence: float
    reason: str


class _StrategyShim:
    """Wraps the module-level evaluate() function to match the Strategy interface."""
    def evaluate(self, tick: dict):
        sig = _arb_module.evaluate(
            tick.get("market_ticker", ""),
            tick.get("yes_price", 0),
            tick.get("no_price", 0),
        )
        if sig is None:
            return None
        return _Signal(
            ticker=sig["ticker"],
            side=sig["side"],
            price=sig["price"],
            confidence=min(sig["edge"] / 0.1, 1.0),
            reason=sig["reason"],
        )


_strategy = _StrategyShim()


async def _preflight() -> list[str]:
    client = KalshiClient()
    try:
        status = await client.get_exchange_status()
        log.info("Exchange status: %s", status)

        resp = await client.get_markets(limit=100, status="open")
        markets = resp.get("markets", [])
        available = []
        for m in markets:
            ticker = m.get("ticker", "")
            event  = m.get("event_ticker", "")
            for prefix in config.WATCH_TICKERS:
                if event.startswith(prefix) or ticker.startswith(prefix):
                    available.append(ticker)
                    break

        if not available:
            available = [m["ticker"] for m in markets[:5]]
            log.warning("Watch-list tickers not found; using first 5: %s", available)
        else:
            log.info("Matched %d markets: %s", len(available), available)

        return available
    finally:
        await client.close()


async def run_paper_loop() -> None:
    global _balance

    tickers = await _preflight()
    if not tickers:
        log.error("No markets available for paper trading.")
        return

    tick_count   = 0
    signal_count = 0

    log.info("Paper-trading loop started | balance=$%.2f | tickers=%s", _balance, tickers)

    async for tick in stream_tickers(tickers):
        tick_count += 1

        if tick_count % 50 == 0:
            summary = get_portfolio_summary()
            log.info(
                "HEARTBEAT ticks=%d signals=%d trades=%d balance=$%.2f return=%.2f%%",
                tick_count, signal_count, summary["total_trades"],
                summary["current_balance"], summary["return_pct"],
            )

        signal = _strategy.evaluate(tick)
        if signal is None:
            continue

        signal_count += 1
        contracts = size_position(signal, _balance)
        if contracts <= 0:
            continue

        entry_cost = signal.price * contracts
        fee        = entry_cost * config.TRADING_FEE_PCT
        net_cost   = entry_cost + fee
        _balance  -= net_cost

        record_trade(
            ticker=signal.ticker,
            side=signal.side,
            entry_price=signal.price,
            contracts=contracts,
            fee=fee,
            net_cost=net_cost,
            balance_after=_balance,
        )

        try:
            from server import push_trade
            await push_trade({
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "ticker":      signal.ticker,
                "side":        signal.side,
                "entry_price": round(signal.price, 4),
                "contracts":   contracts,
                "fee":         round(fee, 4),
                "net_cost":    round(net_cost, 4),
                "balance_after": round(_balance, 2),
                "confidence":  round(signal.confidence, 4),
                "reason":      signal.reason,
            })
        except Exception:
            pass
