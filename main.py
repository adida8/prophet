"""
Prophet-MVP-v1 — Paper-Trading Main Loop

Connects the real-time Kalshi Demo WebSocket feed → strategy engine →
risk manager → Executor (paper or live) → CSV logger → live dashboard.

Usage:
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
from core.executor import Executor
from core.logger import get_portfolio_summary
from models.order import ExecutionMode, Order, OrderStatus, SafetyError
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


# ── Shared state (set in main()) ─────────────────────────────────────
strategy = SimpleArbStrategy()
executor: Executor | None = None


def get_executor() -> Executor | None:
    """Accessor so server.py can reach the running Executor."""
    return executor


async def preflight(client: KalshiClient) -> list[str]:
    """Discover which watch-list tickers have open markets right now."""
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


async def run_trading_loop(tickers: list[str], dashboard: bool = False) -> None:
    """Stream ticks → evaluate strategy → size → route through Executor."""
    global executor
    assert executor is not None, "Executor not initialised"

    push_trade = None
    push_heartbeat = None
    if dashboard:
        from server import push_trade, push_heartbeat  # noqa: F811

    tick_count = 0
    signal_count = 0

    log.info(
        "Trading loop started  |  mode=%s  |  paper_balance=$%.2f  |  tickers=%s",
        executor.mode.value, executor.paper_balance, tickers,
    )

    async for tick in stream_tickers(tickers):
        tick_count += 1

        if tick_count % 50 == 0:
            summary = get_portfolio_summary()
            log.info(
                "HEARTBEAT  ticks=%d  signals=%d  trades=%d  balance=$%.2f  return=%.2f%%  mode=%s",
                tick_count, signal_count, summary["total_trades"],
                summary["current_balance"], summary["return_pct"],
                executor.mode.value,
            )
            if push_heartbeat:
                await push_heartbeat()

        signal = strategy.evaluate(tick)
        if signal is None:
            continue
        signal_count += 1

        contracts = size_position(signal, executor.paper_balance)
        if contracts <= 0:
            log.info("SKIP  %s  — Kelly says no bet", signal.ticker)
            continue

        order = await executor.execute(signal, contracts)

        # Legacy paper-trade WS event (kept so the old trade table keeps working)
        if push_trade and order.status == OrderStatus.FILLED and order.mode == ExecutionMode.PAPER:
            await push_trade({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": signal.ticker,
                "side": signal.side,
                "entry_price": round(signal.price, 4),
                "contracts": contracts,
                "fee": round(order.fee_cents / 100, 4),
                "net_cost": round(signal.price * contracts + order.fee_cents / 100, 4),
                "balance_after": round(executor.paper_balance, 2),
                "confidence": round(signal.confidence, 4),
                "reason": signal.reason,
            })


async def main(dashboard: bool = False) -> None:
    global executor

    log.info("=" * 60)
    log.info("  PROPHET-MVP-v1  —  Trading Engine")
    log.info("  Environment : Kalshi DEMO")
    log.info("  Mode        : %s", config.EXECUTION_MODE.value.upper())
    log.info("  Dashboard   : %s", "http://localhost:8000" if dashboard else "off")
    log.info("  Balance     : $%.2f", config.STARTING_BALANCE)
    log.info("  Per-trade   : $%.2f cap", config.MAX_TRADE_DOLLARS)
    log.info("  Daily loss  : $%.2f limit", config.DAILY_LOSS_LIMIT)
    log.info("  Max/day     : %d trades", config.MAX_TRADES_PER_DAY)
    log.info("=" * 60)

    client = KalshiClient()
    executor = Executor(
        client=client,
        mode=config.EXECUTION_MODE,
        starting_balance=config.STARTING_BALANCE,
    )

    tasks = []

    if dashboard:
        import uvicorn
        from server import app, bind_executor, push_order, push_safety

        bind_executor(executor)
        executor.on_order = push_order
        executor.on_safety = push_safety

        uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, log_level="info")
        server = uvicorn.Server(uv_config)
        tasks.append(asyncio.create_task(server.serve()))
        log.info("Dashboard server starting on http://localhost:%d", config.PORT)

    try:
        tickers = await preflight(client)
        if not tickers:
            log.error("No markets available. Exiting.")
            return

        async def _loop_guard():
            try:
                await run_trading_loop(tickers, dashboard=dashboard)
            except Exception:
                log.exception("Trading loop crashed — dashboard will keep running")

        tasks.append(asyncio.create_task(_loop_guard()))
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
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prophet Trading Engine")
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Launch live dashboard on http://localhost:8000",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Override the dashboard port (otherwise uses $PORT or 8000)",
    )
    args = parser.parse_args()

    if args.port is not None:
        config.PORT = args.port

    try:
        asyncio.run(main(dashboard=args.dashboard))
    except KeyboardInterrupt:
        log.info("Shut down by user.")
