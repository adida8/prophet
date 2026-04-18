"""
Prophet-MVP-v1 — Dashboard Server

A FastAPI app that:
  1. Serves the React frontend (static files)
  2. Exposes a WebSocket at /ws/dashboard that broadcasts trades,
     order updates, safety alerts, and periodic portfolio snapshots
  3. Exposes REST endpoints for settings, mode toggle, kill switch,
     orders, positions, and live balance
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core.logger import get_portfolio_summary
from models.order import ExecutionMode, Order, OrderStatus, SafetyError

log = logging.getLogger("prophet.server")

SETTINGS_PATH = config.DATA_DIR / "settings.json"
SETTINGS_DEFAULTS = {"yes_ceiling": 0.42, "no_floor": 0.58, "min_edge": 0.03}


class SettingsUpdate(BaseModel):
    yes_ceiling: Optional[float] = None
    no_floor: Optional[float] = None
    min_edge: Optional[float] = None


class ModeUpdate(BaseModel):
    mode: str
    confirm: bool = False


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


# ── Executor binding (wired by main.py on startup) ───────────────────
_executor = None


def bind_executor(executor) -> None:
    """Called by main.py so the server can read/command the executor."""
    global _executor
    _executor = executor


def _require_executor():
    if _executor is None:
        raise HTTPException(503, "Executor not initialised yet")
    return _executor


# ── Connected dashboard clients ───────────────────────────────────────
_clients: set[WebSocket] = set()
_trade_history: list[dict[str, Any]] = []


async def broadcast(event: dict) -> None:
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
    _trade_history.append(trade)
    await broadcast({"type": "trade", "data": trade})


async def push_heartbeat() -> None:
    summary = get_portfolio_summary()
    payload = {
        **summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trade_count": len(_trade_history),
    }
    if _executor is not None:
        payload["mode"] = _executor.mode.value
    await broadcast({"type": "heartbeat", "data": payload})


async def push_order(order: Order) -> None:
    await broadcast({"type": "order_update", "data": order.to_dict()})


async def push_safety(err: SafetyError) -> None:
    _append_safety_log(err)
    await broadcast({
        "type": "safety_alert",
        "data": {
            "rule": err.rule,
            "message": err.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })


async def push_mode_change(new_mode: ExecutionMode) -> None:
    await broadcast({
        "type": "mode_change",
        "data": {
            "mode": new_mode.value,
            "changed_at": datetime.now(timezone.utc).isoformat(),
        },
    })


def _append_safety_log(err: SafetyError) -> None:
    path = config.SAFETY_LOG_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "rule", "message"])
        w.writerow([
            datetime.now(timezone.utc).isoformat(),
            err.rule,
            err.message,
        ])


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


# ── Execution-mode & safety endpoints ────────────────────────────────

@app.get("/api/mode")
async def api_get_mode():
    executor = _require_executor()
    return {
        "mode": executor.mode.value,
        "limits": {
            "max_trade_dollars": config.MAX_TRADE_DOLLARS,
            "daily_loss_limit": config.DAILY_LOSS_LIMIT,
            "max_trades_per_day": config.MAX_TRADES_PER_DAY,
        },
    }


@app.post("/api/mode")
async def api_set_mode(body: ModeUpdate):
    executor = _require_executor()
    try:
        requested = ExecutionMode(body.mode.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid mode '{body.mode}'. Use 'paper' or 'live'.")

    if requested == executor.mode:
        return {"mode": executor.mode.value, "changed": False}

    # Paper → live requires explicit confirmation
    if requested == ExecutionMode.LIVE and not body.confirm:
        raise HTTPException(
            400,
            "Switching to LIVE requires confirm=true. "
            "The client should show a warning before enabling live trading.",
        )

    executor.set_mode(requested)
    await push_mode_change(requested)
    return {"mode": executor.mode.value, "changed": True}


@app.post("/api/kill")
async def api_kill():
    executor = _require_executor()
    cancelled = await executor.kill()
    await push_mode_change(executor.mode)
    return {
        "mode": executor.mode.value,
        "cancelled_order_ids": [o.id for o in cancelled],
    }


@app.get("/api/orders")
async def api_orders():
    executor = _require_executor()
    return [o.to_dict() for o in executor.orders[-100:]]


@app.get("/api/positions")
async def api_positions():
    executor = _require_executor()
    return [p.to_dict() for p in executor.positions.values()]


@app.get("/api/balance/live")
async def api_live_balance():
    executor = _require_executor()
    if executor.mode != ExecutionMode.LIVE:
        # Still try — useful for seeing your Kalshi demo balance even in paper mode
        pass
    try:
        data = await executor.client.get_balance()
    except Exception as e:
        raise HTTPException(502, f"Kalshi balance fetch failed: {e}")
    return data


# ── WebSocket ────────────────────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    log.info("Dashboard client connected (%d total)", len(_clients))
    try:
        init = {
            "type": "init",
            "data": {
                "summary": get_portfolio_summary(),
                "trades": _trade_history,
                "mode": _executor.mode.value if _executor else "paper",
                "orders": [o.to_dict() for o in (_executor.orders[-50:] if _executor else [])],
                "positions": [p.to_dict() for p in (_executor.positions.values() if _executor else [])],
                "limits": {
                    "max_trade_dollars": config.MAX_TRADE_DOLLARS,
                    "daily_loss_limit": config.DAILY_LOSS_LIMIT,
                    "max_trades_per_day": config.MAX_TRADES_PER_DAY,
                },
            },
        }
        await ws.send_text(json.dumps(init))
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
