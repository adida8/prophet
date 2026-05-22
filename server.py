"""
Prophet — FastAPI server

Serves:
  - React frontend (static files from frontend/dist/)
  - REST endpoints for market data platform
  - /ws/live — real-time broadcast to dashboard clients
  - Legacy paper-trading endpoints (/ws/dashboard, /api/summary, etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from core.logger import get_portfolio_summary
from desk_api import router as desk_router
from desk_ops_api import router as desk_ops_router
from ledger import db as ledger_db
from ledger.router import router as ledger_router
from signup_api import router as signup_router

log = logging.getLogger("prophet.server")

# ── Shared scheduler instance (set by main.py after creation) ─────────
_scheduler = None


def set_scheduler(s) -> None:
    global _scheduler
    _scheduler = s


# ── WebSocket client sets ─────────────────────────────────────────────
_live_clients: set[WebSocket] = set()      # /ws/live  (data platform)
_dash_clients: set[WebSocket] = set()      # /ws/dashboard (legacy paper trading)

# Legacy paper-trade state
_trade_history: list[dict[str, Any]] = []


# ── Broadcast helpers ─────────────────────────────────────────────────

async def broadcast(payload: dict) -> None:
    """Broadcast to all /ws/live clients.  Called by scheduler."""
    text = json.dumps(payload, default=str)
    dead: list[WebSocket] = []
    for ws in list(_live_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _live_clients.discard(ws)


async def push_trade(trade: dict) -> None:
    """Legacy: push a simulated trade to /ws/dashboard clients."""
    _trade_history.append(trade)
    await _dash_broadcast({"type": "trade", "data": trade})


async def push_heartbeat() -> None:
    """Legacy: push portfolio snapshot to /ws/dashboard clients."""
    summary = get_portfolio_summary()
    await _dash_broadcast({
        "type": "heartbeat",
        "data": {**summary, "timestamp": datetime.now(timezone.utc).isoformat()},
    })


async def _dash_broadcast(event: dict) -> None:
    text = json.dumps(event)
    dead = []
    for ws in list(_dash_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _dash_clients.discard(ws)


# ── Legacy settings (paper trading strategy) ──────────────────────────
SETTINGS_PATH = config.DATA_DIR / "settings.json"
SETTINGS_DEFAULTS = {"yes_ceiling": 0.42, "no_floor": 0.58, "min_edge": 0.03}


def _read_settings() -> dict:
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(SETTINGS_DEFAULTS, indent=2))
        return dict(SETTINGS_DEFAULTS)
    try:
        return {**SETTINGS_DEFAULTS, **json.loads(SETTINGS_PATH.read_text())}
    except (json.JSONDecodeError, ValueError):
        return dict(SETTINGS_DEFAULTS)


# NOTE: settings writes are intentionally removed. The legacy
# `POST /api/settings` endpoint was an unauthenticated config write with
# no value bounds; nothing live consumes it. If a future paper-trade
# tuning surface needs to land, gate it behind a shared-secret header
# and clamp each float.


# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ledger: initialise SQLite tables on boot
    await ledger_db.init_db()
    # Periodic heartbeat for legacy dashboard
    task = asyncio.create_task(_heartbeat_loop())
    yield
    task.cancel()


async def _heartbeat_loop():
    while True:
        await asyncio.sleep(5)
        if _dash_clients:
            await push_heartbeat()


# ── FastAPI app ───────────────────────────────────────────────────────

app = FastAPI(title="Prophet — Prediction Market Intelligence", lifespan=lifespan)

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "https://oddsprimer.com,https://www.oddsprimer.com,http://localhost:5173",
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(ledger_router)
app.include_router(desk_router)
# Ops router goes before the SPA catch-all (which is registered later via
# `app.get("/", ...)` etc.) so `/api/desk/ops/*` resolves to the API
# adapter, not the React shell. Disabled-by-default — see desk_ops_api.
app.include_router(desk_ops_router)
app.include_router(signup_router)


# ─────────────────────────── REST endpoints ───────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "last_updated": _scheduler.last_updated.isoformat() if _scheduler and _scheduler.last_updated else None,
    }


# ── Data platform endpoints ───────────────────────────────────────────

@app.get("/api/markets")
async def api_markets(category: Optional[str] = None, platform: Optional[str] = None):
    if not _scheduler:
        return []
    markets = _scheduler.all_markets
    if category:
        markets = [m for m in markets if m.category == category]
    if platform:
        markets = [m for m in markets if m.platform == platform]
    return [m.to_dict() for m in markets]


@app.get("/api/compare")
async def api_compare(category: Optional[str] = None):
    if not _scheduler:
        return []
    compared = _scheduler.compared
    if category:
        compared = [c for c in compared if c.category == category]
    return [c.to_dict() for c in compared]


@app.get("/api/arbitrage")
async def api_arbitrage():
    if not _scheduler:
        return []
    return [a.to_dict() for a in _scheduler.arb_opps]


@app.get("/api/movers")
async def api_movers(window: str = "24h"):
    if not _scheduler:
        return []
    return _scheduler.movers_1h if window == "1h" else _scheduler.movers_24h


@app.get("/api/stats")
async def api_stats():
    return _scheduler.stats if _scheduler else {}


@app.get("/api/platforms")
async def api_platforms():
    return _scheduler.platform_stats if _scheduler else {}


@app.get("/api/snapshot")
async def api_snapshot():
    """Full snapshot — used by frontend on initial load."""
    if not _scheduler:
        return {"data": {}}
    return _scheduler.snapshot()


# ── Legacy paper-trading endpoints ────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    return _read_settings()


@app.get("/api/summary")
async def api_summary():
    return get_portfolio_summary()


@app.get("/api/trades")
async def api_trades():
    return _trade_history


# ── WebSockets ────────────────────────────────────────────────────────
# Both sockets are unauthenticated. Two guards apply before accept:
#   - Origin check against the CORS allowlist — refuses cross-site WS
#     handshakes from arbitrary hosts.
#   - Per-route connection cap — refuses with close code 1013 ("Try
#     Again Later") so the server can't be exhausted by parking
#     connections open.
MAX_WS_PER_ROUTE = int(os.getenv("MAX_WS_PER_ROUTE", "200"))


async def _ws_admit(ws: WebSocket, clients: set[WebSocket]) -> bool:
    """Run pre-accept guards. Returns True if the socket was accepted
    and added to `clients`; False if it was refused (already closed)."""
    origin = ws.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await ws.close(code=1008)  # policy violation
        return False
    if len(clients) >= MAX_WS_PER_ROUTE:
        await ws.close(code=1013)  # try again later
        return False
    await ws.accept()
    clients.add(ws)
    return True


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    if not await _ws_admit(ws, _live_clients):
        return
    log.info("Live client connected (%d total)", len(_live_clients))
    try:
        if _scheduler and _scheduler.last_updated:
            await ws.send_text(json.dumps(_scheduler.snapshot(), default=str))
        else:
            await ws.send_text(json.dumps({"type": "init", "data": {}}))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _live_clients.discard(ws)
        log.info("Live client disconnected (%d remaining)", len(_live_clients))


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    """Legacy paper-trading dashboard WebSocket."""
    if not await _ws_admit(ws, _dash_clients):
        return
    try:
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {"summary": get_portfolio_summary(), "trades": _trade_history},
        }))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _dash_clients.discard(ws)


# ── Backtest dashboard + workbook (read-only) ─────────────────────────
# The Desk's backtest harness writes desk_backtest_dashboard.html and
# desk_backtest.xlsx at the project root. Expose them at stable URLs so
# Faktor (and reviewers generally) can read the calibration story
# without checking out the repo.

PROJECT_ROOT = Path(__file__).parent
BACKTEST_HTML = PROJECT_ROOT / "desk_backtest_dashboard.html"
BACKTEST_XLSX = PROJECT_ROOT / "desk_backtest.xlsx"


@app.get("/backtest", include_in_schema=False)
@app.get("/backtest/", include_in_schema=False)
@app.get("/backtest/dashboard.html", include_in_schema=False)
async def backtest_dashboard():
    if not BACKTEST_HTML.exists():
        return {"error": "backtest dashboard not generated yet"}
    return FileResponse(BACKTEST_HTML, media_type="text/html")


@app.get("/backtest/dashboard.xlsx", include_in_schema=False)
@app.get("/backtest.xlsx", include_in_schema=False)
async def backtest_workbook():
    if not BACKTEST_XLSX.exists():
        return {"error": "backtest workbook not generated yet"}
    return FileResponse(
        BACKTEST_XLSX,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="desk_backtest.xlsx",
    )


# ── Odds Primer static site ───────────────────────────────────────────
# The Desk's per-match JSON output is rendered to a static HTML site by
# site/generate.py. The static site is the canonical surface for every
# editorial route (`/`, `/matches`, `/m/{id}`, `/outrights`, `/o/{id}`,
# `/about`, `/learn`, the trust pages). The React SPA only handles its
# own sub-products (`/ledger`, `/desk`, `/dashboard`).
# Daily workflow:
#     python -m desk run --once       # refresh JSONs
#     python site/generate.py         # rebuild static HTML
#     git commit -am 'site refresh' && git push   # Railway redeploys

SITE_PUBLIC = Path(__file__).parent / "site" / "public"


def _safe_path(base: Path, rel: str) -> Path | None:
    """Resolve base/rel and return it only if it stays inside base.
    Guards every static-file route against `../` traversal — without
    this, `_serve_site("../../core/auth.py")` resolves to a real file
    outside the web root and FileResponse will happily stream it."""
    base = base.resolve()
    try:
        full = (base / rel).resolve()
    except (ValueError, OSError):
        return None
    if full == base or base in full.parents:
        return full
    return None


def _site_not_found():
    """Return the on-brand 404 page when a static-site path is missing.
    Falls back to a minimal JSON 404 if the 404.html file isn't present."""
    p404 = SITE_PUBLIC / "404.html"
    if p404.is_file():
        return FileResponse(p404, media_type="text/html", status_code=404)
    return FileResponse(SITE_PUBLIC / "index.html", media_type="text/html", status_code=404) \
        if (SITE_PUBLIC / "index.html").is_file() else \
        {"error": "not found"}


if (SITE_PUBLIC / "index.html").exists():

    def _serve_site(rel_path: str):
        p = _safe_path(SITE_PUBLIC, rel_path)
        if p is None or not p.is_file():
            return _site_not_found()
        return FileResponse(p, media_type="text/html")

    @app.get("/", include_in_schema=False)
    async def site_home():
        return _serve_site("index.html")

    @app.get("/matches", include_in_schema=False)
    @app.get("/matches/", include_in_schema=False)
    async def site_matches():
        return _serve_site("matches/index.html")

    @app.get("/m/{match_id}", include_in_schema=False)
    async def site_match(match_id: str):
        match_id = match_id.removesuffix("/").removesuffix(".html")
        return _serve_site(f"m/{match_id}.html")

    # Outright pages are hidden from the public site until a tournament-
    # winner market produces a real Pick / Avoid. Every /outrights and
    # /o/{id} request falls through to the on-brand 404 page.
    @app.get("/outrights", include_in_schema=False)
    @app.get("/outrights/", include_in_schema=False)
    @app.get("/outrights/wc26", include_in_schema=False)
    @app.get("/outrights/wc26/", include_in_schema=False)
    async def site_outrights():
        return _site_not_found()

    @app.get("/o/{outright_id}", include_in_schema=False)
    async def site_outright(outright_id: str):  # noqa: ARG001
        return _site_not_found()

    # ── Editorial / trust pages (sourced from handover-v4) ────────────
    # `learn` and `world-cup` are intentionally absent: the React SPA owns
    # both (see SPA_PREFIXES below). The static `site/public/learn.html`
    # is the older long-form layout — kept as a fossil but no longer
    # routed, so the SPA's LearnIndex + primer tree owns /learn end-to-end.
    _EDITORIAL_PAGES = (
        "about",
        "method", "methodology",
        "responsible-use", "affiliate-disclosure", "corrections",
        "terms", "privacy", "cookies",
        "404",
    )

    def _make_editorial_route(name: str):
        async def handler():
            return _serve_site(f"{name}.html")
        handler.__name__ = f"site_editorial_{name.replace('-', '_')}"
        return handler

    for _name in _EDITORIAL_PAGES:
        _h = _make_editorial_route(_name)
        app.get(f"/{_name}",       include_in_schema=False)(_h)
        app.get(f"/{_name}/",      include_in_schema=False)(_h)
        app.get(f"/{_name}.html",  include_in_schema=False)(_h)

    @app.get("/colors_and_type.css", include_in_schema=False)
    async def site_colors_css():
        return FileResponse(SITE_PUBLIC / "colors_and_type.css", media_type="text/css")

    @app.get("/favicon.svg", include_in_schema=False)
    async def site_favicon_svg():
        return FileResponse(SITE_PUBLIC / "favicon.svg", media_type="image/svg+xml")

    @app.get("/favicon-{size}.png", include_in_schema=False)
    async def site_favicon_png(size: str):
        p = _safe_path(SITE_PUBLIC, f"favicon-{size}.png")
        if p is None or not p.is_file():
            return FileResponse(SITE_PUBLIC / "favicon-32.png", media_type="image/png", status_code=404)
        return FileResponse(p, media_type="image/png")

    @app.get("/favicon.ico", include_in_schema=False)
    async def site_favicon_ico():
        return FileResponse(SITE_PUBLIC / "favicon-32.png", media_type="image/png")

    @app.get("/sitemap.xml", include_in_schema=False)
    async def site_sitemap():
        p = SITE_PUBLIC / "sitemap.xml"
        if p.is_file():
            return FileResponse(p, media_type="application/xml")
        return _site_not_found()

    @app.get("/robots.txt", include_in_schema=False)
    async def site_robots():
        p = SITE_PUBLIC / "robots.txt"
        if p.is_file():
            return FileResponse(p, media_type="text/plain")
        return _site_not_found()


# ── Static frontend ───────────────────────────────────────────────────
# The React SPA owns the sub-products only: /ledger, /desk, /dashboard
# (plus their sub-paths). Everything else either matches an explicit
# static-site / API / backtest route above, or it's a real 404.
# The frontend/public/v4/ mockups are retired (was the source of stale
# "PredictionEdge" branding leaking into shared URLs); they are no
# longer served from any route.

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

SPA_PREFIXES = ("/ledger", "/desk", "/dashboard", "/world-cup", "/learn")


def _is_spa_path(path: str) -> bool:
    p = "/" + path.lstrip("/")
    return any(p == prefix or p.startswith(prefix + "/") for prefix in SPA_PREFIXES)


if FRONTEND_DIST.exists():
    # Serve assets/ directly so JS/CSS hashed bundles work.
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Ops dashboard SPA route — gated by the same HTTP Basic dependency
    # the /api/desk/ops/* endpoints use, so the page itself doesn't
    # render unauthed (spec §9). When the env vars are unset, the gate
    # raises 404 and the route looks like it doesn't exist at all.
    from fastapi import Depends
    from desk_ops_api import _gate as _desk_ops_gate

    @app.get("/desk/ops", include_in_schema=False, dependencies=[Depends(_desk_ops_gate)])
    @app.get("/desk/ops/", include_in_schema=False, dependencies=[Depends(_desk_ops_gate)])
    async def desk_ops_spa():
        return FileResponse(FRONTEND_DIST / "index.html")

    # SPA fallback: serves the React app for /ledger, /desk, /dashboard
    # (and their sub-paths). Everything else — paths not matched by the
    # static-site, API, or backtest routes above — returns the on-brand
    # 404 page with a real 404 status (so /asdf doesn't silently render
    # the home with a 200).
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path:
            candidate = _safe_path(FRONTEND_DIST, full_path)
            if candidate is not None and candidate.is_file():
                return FileResponse(candidate)
        if _is_spa_path(full_path):
            return FileResponse(FRONTEND_DIST / "index.html")
        return _site_not_found()
