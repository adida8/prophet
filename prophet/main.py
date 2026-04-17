"""
Prophet-MVP-v1 — Market Feed

Serves a live Kalshi market feed dashboard.

Usage:
    python main.py              # start feed server on port 8000
    python main.py --port 3000  # custom port
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("prophet.main")


def main():
    parser = argparse.ArgumentParser(description="Prophet Market Feed")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--dashboard", action="store_true", help="(ignored, always on)")
    args = parser.parse_args()

    import uvicorn
    from server import app

    log.info("Starting Prophet Market Feed on http://localhost:%d", args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
