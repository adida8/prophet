"""Entry point — `python main.py [--port N]`.

Runs the stub FastAPI app (read-only desk routes + background refresh /
drain loops) under uvicorn. Railway passes $PORT; default 8000 locally.
"""

from __future__ import annotations

import argparse
import logging
import os

import uvicorn


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="desk-stub")
    parser.add_argument(
        "--port", type=int,
        default=int(os.getenv("PORT", "8000")),
        help="port to bind (Railway sets $PORT)",
    )
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    # Import as a string so uvicorn owns the app lifecycle (lifespan loops).
    uvicorn.run("stubdesk.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
