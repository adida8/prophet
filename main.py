"""
Prophet — Prediction Market Intelligence Platform

Entry point.  Always starts:
  - FastAPI server (REST + WebSocket)
  - Market data scheduler (Kalshi + Polymarket fetch loop)

Optional:
  --paper-trade   Also run the paper-trading loop (legacy)

Usage:
    python main.py                        # data platform only
    python main.py --paper-trade          # + paper trading loop
    python main.py --port 9000            # override port
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import uvicorn

import config
from activity_refresh_loop import run_activity_loop
from desk_distribute_loop import run_distribute_loop
from desk_refresh_loop import run_desk_loop
from ledger.refresh_loop import run_refresh_loop as run_ledger_refresh_loop
from social_weekly_cron import run_weekly_loop as run_social_weekly_loop
from scheduler import Scheduler
from server import app, set_scheduler, broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("prophet.main")


async def main(port: int, paper_trade: bool) -> None:
    log.info("=" * 64)
    log.info("  PROPHET — Prediction Market Intelligence")
    log.info("  Dashboard : http://0.0.0.0:%d", port)
    log.info("  Kalshi    : %s", "enabled" if config.API_KEY else "no API key — skipped")
    log.info("  Polymarket: enabled (public API)")
    log.info("=" * 64)

    scheduler = Scheduler(broadcast_fn=broadcast)
    set_scheduler(scheduler)

    uv_config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server    = uvicorn.Server(uv_config)

    tasks = [
        asyncio.create_task(scheduler.run(),         name="scheduler"),
        asyncio.create_task(server.serve(),          name="server"),
        asyncio.create_task(run_ledger_refresh_loop(), name="ledger_refresh"),
        asyncio.create_task(run_desk_loop(),         name="desk_refresh"),
        asyncio.create_task(run_distribute_loop(),   name="desk_distribute"),
        asyncio.create_task(run_activity_loop(),     name="activity_refresh"),
        asyncio.create_task(run_social_weekly_loop(), name="social_weekly"),
    ]

    if paper_trade:
        from paper_trader import run_paper_loop
        tasks.append(asyncio.create_task(run_paper_loop(), name="paper_trader"))
        log.info("Paper-trading loop enabled")

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prophet — Prediction Market Intelligence")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--dashboard", action="store_true", help="(deprecated — dashboard is always on)")
    parser.add_argument("--paper-trade", action="store_true", dest="paper_trade")
    args = parser.parse_args()

    try:
        asyncio.run(main(port=args.port, paper_trade=args.paper_trade))
    except KeyboardInterrupt:
        log.info("Shutdown.")
