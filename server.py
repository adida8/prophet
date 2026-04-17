"""
Prophet-MVP-v1 — Dashboard Server

A lightweight FastAPI app that:
  1. Serves the React frontend (static files)
  2. Exposes a WebSocket at /ws/dashboard that broadcasts every
     simulated trade + periodic portfolio snapshots to connected browsers
  3. Exposes REST endpoints for initial page load (trade history, summary)
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from typing import Optional

from pydantic import BaseModel

import config
from core.logger import get_portfolio_summary

log = logging.getLogger("prophet.server")

SETTINGS_PATH = config.DATA_DIR / "settings.json"
SETTINGS_DEFAULTS = {"yes_ceiling": 0.42, "no_floor": 0.58, "min_edge": 0.03}


class SettingsUpdate(BaseModel):
    yes_ceiling: Optional[float] = None
    no_floor: Optional[float] = None
    min_edge: Optional[float] = None


def _read_settings() -> dict:
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(SETTINGS_DEFAULTS, indent=2))
        return dict(SETTINGS_DEFAULTS)
    try:
        return {**SETTINGS_DEFAULTS, **json.loads(SETTINGS_PATH.read_text())}
    except (json.JSONDecodeError, ValueError):
        return dict(SETTINGS_DEFAULTS)


def _write_settings(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))

# ── Connected dashboard clients ───────────────────────────────────────
_clients: set[WebSocket] = set()
_trade_history: list[dict[str, Any]] = []  # in-memory mirror of CSV rows


async def broadcast(event: dict) -> None:
    """Send a JSON event to every connected dashboard client."""
    payload = json.dumps(event)
    dead: list[WebSocket] = []
    for ws in _clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def push_trade(trade: dict) -> None:
    """Called by the trading loop whenever a sim-trade is recorded."""
    _trade_history.append(trade)
    await broadcast({"type": "trade", "data": trade})


async def push_heartbeat() -> None:
    """Push a portfolio summary snapshot to all clients."""
    summary = get_portfolio_summary()
    await broadcast({
        "type": "heartbeat",
        "data": {
            **summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trade_count": len(_trade_history),
        },
    })


# ── Periodic heartbeat task ──────────────────────────────────────────
async def _heartbeat_loop():
    while True:
        await asyncio.sleep(5)
        if _clients:
            await push_heartbeat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_heartbeat_loop())
    yield
    task.cancel()


# ── FastAPI App ───────────────────────────────────────────────────────
app = FastAPI(title="Prophet Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/settings")
async def get_settings():
    return _read_settings()


@app.post("/api/settings")
async def update_settings(body: SettingsUpdate):
    current = _read_settings()
    if body.yes_ceiling is not None:
        current["yes_ceiling"] = body.yes_ceiling
    if body.no_floor is not None:
        current["no_floor"] = body.no_floor
    if body.min_edge is not None:
        current["min_edge"] = body.min_edge
    _write_settings(current)
    log.info("Settings updated: %s", current)
    return current


@app.get("/api/summary")
async def api_summary():
    return get_portfolio_summary()


@app.get("/api/trades")
async def api_trades():
    return _trade_history


@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    log.info("Dashboard client connected (%d total)", len(_clients))
    try:
        # Send current state on connect
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {
                "summary": get_portfolio_summary(),
                "trades": _trade_history,
            },
        }))
        # Keep alive — the client only listens
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        log.info("Dashboard client disconnected (%d remaining)", len(_clients))


# ── Mount static frontend (built files) ──────────────────────────────
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
