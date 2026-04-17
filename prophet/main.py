"""
Prophet-MVP-v1 — Paper-Trading Main Loop

Connects the real-time Kalshi Demo WebSocket feed → strategy engine →
risk manager → CSV logger → live dashboard.

Usage:
    cd prophet/
    python main.py              # headless (no dashboard)
    python main.py --dashboard  # with live browser dashboard on :8000
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

import config
from core.client import KalshiClient, stream_tickers
from core.logger import get_portfolio_summary, record_trade
from risk_manager import size_position
from strategies.simple_arb import SimpleArbStrategy

# ── Logging Setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("prophet.main")


# ── State ─────────────────────────────────────────────────────────────
balance = config.STARTING_BALANCE
strategy = SimpleArbStrategy()


async def preflight() -> list[str]:
    """
    Hit the REST API to verify credentials and discover which of
    our watch-list tickers actually have open markets right now.
    Returns the list of valid market tickers.
    """
    client = KalshiClient()
    try:
        status = await client.get_exchange_status()
        log.info("Exchange status: %s", status)

        resp = await client.get_markets(limit=100, status="open")
        markets = resp.get("markets", [])
        available = []
        for m in markets:
            ticker = m.get("ticker", "")
            event = m.get("event_ticker", "")
            for prefix in config.WATCH_TICKERS:
                if event.startswith(prefix) or ticker.startswith(prefix):
                    available.append(ticker)
                    break

        if not available:
            available = [m["ticker"] for m in markets[:5]]
            log.warning(
                "None of our watch-list tickers found. "
                "Falling back to first 5 open markets: %s",
                available,
            )
        else:
            log.info("Matched %d markets from watch list: %s", len(available), available)

        return available
    finally:
        await client.close()


async def run_paper_loop(tickers: list[str], dashboard: bool = False) -> None:
    """
    Stream ticks → evaluate strategy → size via Kelly → log to CSV.
    If dashboard=True, also push events to connected browsers.
    """
    global balance

    push_trade = None
    push_heartbeat = None
    if dashboard:
        from server import push_trade, push_heartbeat  # noqa: F811

    tick_count = 0
    signal_count = 0

    log.info(
        "Starting paper-trading loop  |  balance=$%.2f  |  tickers=%s",
        balance, tickers,
    )

    async for tick in stream_tickers(tickers):
        tick_count += 1

        # Periodic heartbeat every 50 ticks
        if tick_count % 50 == 0:
            summary = get_portfolio_summary()
            log.info(
                "HEARTBEAT  ticks=%d  signals=%d  trades=%d  balance=$%.2f  return=%.2f%%",
                tick_count,
                signal_count,
                summary["total_trades"],
                summary["current_balance"],
                summary["return_pct"],
            )
            if push_heartbeat:
                await push_heartbeat()

        # Evaluate strategy
        signal = strategy.evaluate(tick)
        if signal is None:
            continue

        signal_count += 1

        # Size the position (Kelly + hard cap)
        contracts = size_position(signal, balance)
        if contracts <= 0:
            log.info("SKIP  %s  — Kelly says no bet", signal.ticker)
            continue

        # Compute costs
        entry_cost = signal.price * contracts
        fee = entry_cost * config.TRADING_FEE_PCT
        net_cost = entry_cost + fee
        balance -= net_cost

        # Record the simulated trade
        record_trade(
            ticker=signal.ticker,
            side=signal.side,
            entry_price=signal.price,
            contracts=contracts,
            fee=fee,
            net_cost=net_cost,
            balance_after=balance,
        )

        # Push to dashboard
        if push_trade:
            await push_trade({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": signal.ticker,
                "side": signal.side,
                "entry_price": round(signal.price, 4),
                "contracts": contracts,
                "fee": round(fee, 4),
                "net_cost": round(net_cost, 4),
                "balance_after": round(balance, 2),
                "confidence": round(signal.confidence, 4),
                "reason": signal.reason,
            })


async def main(dashboard: bool = False) -> None:
    log.info("=" * 60)
    log.info("  PROPHET-MVP-v1  —  Paper Trading Engine")
    log.info("  Environment : Kalshi DEMO")
    log.info("  Dashboard   : %s", "http://localhost:8000" if dashboard else "off")
    log.info("  Balance     : $%.2f", config.STARTING_BALANCE)
    log.info("  Fee         : %.1f%%", config.TRADING_FEE_PCT * 100)
    log.info("  Max bet     : %.0f%% of balance (Kelly-capped)", config.MAX_BET_PCT * 100)
    log.info("=" * 60)

    tasks = []

    # Optionally start the dashboard server
    if dashboard:
        import uvicorn
        from server import app

        uv_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(uv_config)
        tasks.append(asyncio.create_task(server.serve()))
        log.info("Dashboard server starting on http://localhost:8000")

    tickers = await preflight()
    if not tickers:
        log.error("No markets available. Exiting.")
        return

    tasks.append(asyncio.create_task(run_paper_loop(tickers, dashboard=dashboard)))

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        pass
    finally:
        summary = get_portfolio_summary()
        log.info("=" * 60)
        log.info("  SESSION SUMMARY")
        log.info("  Trades     : %d", summary["total_trades"])
        log.info("  Total fees : $%.4f", summary["total_fees"])
        log.info("  Balance    : $%.2f", summary["current_balance"])
        log.info("  Return     : %.2f%%", summary["return_pct"])
        log.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prophet Paper Trader")
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Launch live dashboard on http://localhost:8000",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(dashboard=args.dashboard))
    except KeyboardInterrupt:
        log.info("Shut down by user.")
