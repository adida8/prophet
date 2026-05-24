"""Server-side adapter for The Desk's ops dashboard.

Mounted at /api/desk/ops/* by server.py. Read-mostly — serves the
`RunReport` JSON the runner persists to `desk/data/output/ops/runs/`
plus a small read/write `control.json` (enable/disable + a list of
UTC hours at which to fire daily) that the refresh loop polls on each
scheduling decision.

This module lives at the project root next to `desk_api.py` for the
same architectural reason: the server runs from project root and
`desk/` ships as an independent Python package that is NOT pip-
installed in the Railway deploy. We therefore can't `from desk.* import …`
from this file — both routers do pure filesystem I/O against the same
artefacts the desk subprocesses produce.

Access is gated by HTTP Basic auth with credentials from env:

    DESK_OPS_USER
    DESK_OPS_PASS

When either env var is unset the dashboard is **disabled**: every
route returns 404 (not 401), so an unset deployment doesn't even
acknowledge that the surface exists. Once both are set, requests need
to authenticate or they get 401.

Routes
------
GET /api/desk/ops/latest
    The most recent run report.

GET /api/desk/ops/runs?limit=50
    Manifest of recent runs (newest first), one compact row per run.
    Each row carries `cost_usd` joined from tick-totals.jsonl.

GET /api/desk/ops/runs/{run_id}
    Full run report for one run. 400 on a malformed id, 404 if absent.

GET /api/desk/ops/control
    Current refresh-loop control state (enabled, hours).

PUT /api/desk/ops/control  body: { enabled?, hours?: [int 0..23] }
    Update control state. `hours` is a list of UTC hours at which the
    refresh tick fires (e.g. [6, 14, 22] = three runs per day). The
    refresh loop picks up changes on its next scheduling decision —
    no restart needed.

GET /api/desk/ops/distribute?limit=25
    Read-only view of the MTA push outbox (sqlite). Returns
    push_enabled / pending_count / dead_count + the most recent dead
    rows with last_error. Never 500s — a missing DB returns empty
    counts. Owned by desk/desk/distribute/outbox.py; we read it
    here with stdlib sqlite3 to preserve the no-imports-from-desk
    invariant.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

log = logging.getLogger("desk_ops_api")

router = APIRouter(prefix="/api/desk/ops", tags=["desk-ops"])
_basic = HTTPBasic(auto_error=False)

# desk/data/output/ops/ — `desk/` is a sibling of this file. Same
# convention as desk_api.py. Tests + non-default deploys can override
# the root by exporting DESK_OUTPUT_DIR (or, for the ops history
# specifically, DESK_OPS_DIR — pointing this at a Railway volume is
# how the dashboard survives deploys). Both env vars match what the
# runner reads in desk/desk/config.py so writer + API agree on a path.
_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_OUTPUT = _PROJECT_ROOT / "desk" / "data" / "output"


def _ops_root() -> Path:
    ops_dir = os.getenv("DESK_OPS_DIR")
    if ops_dir:
        return Path(ops_dir)
    return Path(os.getenv("DESK_OUTPUT_DIR") or _DEFAULT_OUTPUT) / "ops"


def _runs_dir() -> Path:
    return _ops_root() / "runs"


def _index_path() -> Path:
    return _ops_root() / "index.json"


def _control_path() -> Path:
    return _ops_root() / "control.json"


def _tick_totals_path() -> Path:
    return _ops_root() / "tick-totals.jsonl"


# ── Control state ─────────────────────────────────────────────────────
# Mirrors the helpers in desk_refresh_loop.py — we keep the two in
# sync by hand because neither file can import from the other (the
# loop runs in main.py's asyncio task, the API runs inside FastAPI;
# both share the on-disk JSON file as the source of truth).
#
# Schema: { enabled: bool, hours: [int 0..23], updated_at: iso8601 }
# `hours` is the list of UTC clock hours at which the refresh tick
# fires once per day (e.g. [6, 14, 22] = three runs daily). Empty list
# means "no scheduled runs"; the loop idles until the operator adds one.

_DEFAULT_HOURS = [6]      # fresh install fires daily at 06:00 UTC


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _normalise_hours(raw: Any) -> list[int]:
    """Coerce input into a sorted, deduped list of valid UTC hours.

    Accepts list of int / str / float. Drops anything outside 0..23.
    Empty list is a valid state — means "schedule disabled" even when
    enabled=true. Cap at 24 entries (one per hour) — defence in depth
    against a runaway frontend.
    """
    if raw is None:
        return list(_DEFAULT_HOURS)
    if not isinstance(raw, (list, tuple)):
        raise ValueError("hours must be a list of integers")
    out: set[int] = set()
    for v in raw:
        try:
            h = int(v)
        except (TypeError, ValueError):
            continue
        if 0 <= h <= 23:
            out.add(h)
    return sorted(out)[:24]


def _read_control() -> dict[str, Any]:
    """Return the persisted control state, or defaults if missing."""
    path = _control_path()
    if not path.is_file():
        return {
            "enabled":    True,
            "hours":      list(_DEFAULT_HOURS),
            "updated_at": None,
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("control.json unreadable, returning defaults: %s", e)
        return {
            "enabled":    True,
            "hours":      list(_DEFAULT_HOURS),
            "updated_at": None,
        }
    try:
        hours = _normalise_hours(raw.get("hours"))
    except ValueError:
        hours = list(_DEFAULT_HOURS)
    return {
        "enabled":    bool(raw.get("enabled", True)),
        "hours":      hours,
        "updated_at": raw.get("updated_at"),
    }


def _write_control(patch: dict[str, Any]) -> dict[str, Any]:
    """Persist a patched control state atomically."""
    current = _read_control()
    new = {
        "enabled":    bool(patch.get("enabled", current["enabled"])),
        "hours":      _normalise_hours(patch["hours"]) if "hours" in patch else current["hours"],
        "updated_at": _now_iso(),
    }
    root = _ops_root()
    root.mkdir(parents=True, exist_ok=True)
    path = _control_path()
    tmp  = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(new, indent=2), encoding="utf-8")
    tmp.replace(path)
    return new


# ── Cost (tick totals join onto manifest by run_id) ───────────────────

def _load_tick_totals_by_run_id() -> dict[str, dict[str, Any]]:
    """Read tick-totals.jsonl into a {run_id: row} index.

    Most-recent row wins if the same run_id appears more than once.
    Missing / unreadable file → empty dict (cost column simply shows
    nothing for those rows).
    """
    path = _tick_totals_path()
    out: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return out
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = row.get("run_id")
                if rid:
                    out[rid] = row
    except OSError as e:
        log.warning("tick-totals read failed: %s", e)
    return out


# Mirrors `desk/desk/ops/report.py:RUN_ID_RE`. Defence-in-depth: the
# writer guarantees this shape, but the API never trusts the URL path
# to match it.
_RUN_ID_RE = re.compile(r"^run-\d{8}T\d{6}Z$")


def _creds_from_env() -> tuple[str, str] | None:
    """Return the configured (user, pass) or None when disabled.

    Both vars must be set and non-empty. Partial config is treated as
    disabled — better to 404 than ship an unauthed surface because
    someone set USER but forgot PASS.
    """
    user = (os.getenv("DESK_OPS_USER") or "").strip()
    pwd  = (os.getenv("DESK_OPS_PASS") or "").strip()
    if not user or not pwd:
        return None
    return user, pwd


def _gate(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    """Auth dependency.

    Disabled → 404 (don't acknowledge the surface).
    Enabled, no creds  → 401 with WWW-Authenticate.
    Enabled, bad creds → 401.
    Enabled, good      → returns None, request proceeds.
    """
    cfg = _creds_from_env()
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth required",
            headers={"WWW-Authenticate": 'Basic realm="desk-ops"'},
        )
    user_ok = secrets.compare_digest(credentials.username, cfg[0])
    pwd_ok  = secrets.compare_digest(credentials.password, cfg[1])
    if not (user_ok and pwd_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad credentials",
            headers={"WWW-Authenticate": 'Basic realm="desk-ops"'},
        )


def _read_run(run_id: str) -> dict[str, Any]:
    path = _runs_dir() / f"{run_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no such run: {run_id}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("failed to read run %s: %s", run_id, e)
        raise HTTPException(status_code=500, detail="run log unreadable")


def _list_run_files() -> list[Path]:
    """All persisted run JSONs, sorted oldest → newest by name.

    Falls back to a directory scan when `index.json` is missing or
    malformed, so a single bad manifest doesn't blind the dashboard.
    """
    runs_dir = _runs_dir()
    if not runs_dir.exists():
        return []
    return sorted(
        f for f in runs_dir.iterdir()
        if f.is_file() and f.suffix == ".json" and _RUN_ID_RE.match(f.stem)
    )


def _load_manifest() -> dict[str, Any]:
    """Prefer the recorder-maintained index.json; fall back to a scan.

    Scan is the resilience path: if the recorder ever fails to update
    the manifest, the dashboard can still list runs that exist on disk.
    """
    index_path = _index_path()
    if index_path.is_file():
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("index.json unreadable, falling back to scan: %s", e)

    rows: list[dict[str, Any]] = []
    for f in reversed(_list_run_files()):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append({
            "run_id":       r.get("run_id", f.stem),
            "started_at":   r.get("started_at"),
            "finished_at":  r.get("finished_at"),
            "trigger":      r.get("trigger", "manual"),
            "status":       r.get("status", "ok"),
            "published":    _published_count(r),
            "picks":        (r.get("verdicts") or {}).get("pick", 0),
            "change_count": len(r.get("changes") or []),
        })
    return {
        "runs":       rows,
        "updated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _published_count(report: dict[str, Any]) -> int:
    for row in (report.get("funnel") or []):
        if row.get("stage") == "published":
            return int(row.get("n") or 0)
    return 0


@router.get("/latest", dependencies=[Depends(_gate)])
def get_latest() -> dict:
    files = _list_run_files()
    if not files:
        raise HTTPException(status_code=404, detail="no runs recorded yet")
    # File names are timestamp-prefixed, so name-sort == time-sort.
    return _read_run(files[-1].stem)


@router.get("/runs", dependencies=[Depends(_gate)])
def list_runs(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    manifest = _load_manifest()
    runs = manifest.get("runs") or []
    # Join cost from tick-totals.jsonl. The refresh loop writes one row
    # per tick keyed by the matches RunReport's run_id, so this is an
    # in-memory dict lookup — no scan per row.
    costs = _load_tick_totals_by_run_id()
    enriched = []
    for row in runs[:limit]:
        rid  = row.get("run_id")
        cost = costs.get(rid) if rid else None
        enriched.append({
            **row,
            "cost_usd":   (cost or {}).get("total_usd"),
            "cost_calls": (cost or {}).get("calls"),
        })
    return {
        "runs":       enriched,
        "updated_at": manifest.get("updated_at"),
    }


@router.get("/runs/{run_id}", dependencies=[Depends(_gate)])
def get_run(run_id: str) -> dict:
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="malformed run_id")
    body = _read_run(run_id)
    cost = _load_tick_totals_by_run_id().get(run_id)
    if cost:
        body["cost"] = {
            "total_usd": cost.get("total_usd"),
            "calls":     cost.get("calls"),
            "breakdown": cost.get("breakdown") or {},
        }
    return body


# ── Control: enable/disable + frequency ───────────────────────────────

@router.get("/control", dependencies=[Depends(_gate)])
def get_control() -> dict:
    return _read_control()


@router.put("/control", dependencies=[Depends(_gate)])
def put_control(payload: dict = Body(default_factory=dict)) -> dict:
    # Accept enabled + hours; ignore unknowns so a future UI revision
    # can send extra fields without breaking older servers.
    patch: dict[str, Any] = {}
    if "enabled" in payload:
        patch["enabled"] = bool(payload["enabled"])
    if "hours" in payload:
        try:
            patch["hours"] = _normalise_hours(payload["hours"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return _write_control(patch)


# ── Distribute (MTA push wire) visibility ─────────────────────────────
# Read-only view of the outbox owned by `desk/desk/distribute/`. The
# project-root API never imports from `desk/` (see desk_api.py header),
# so we read the SQLite file directly with stdlib. Schema is owned by
# `desk/desk/distribute/outbox.py::_SCHEMA` — keep the column list in
# sync if it ever changes.

# Default DB path mirrors `desk.distribute.config._PACKAGE_DB_PATH`.
_DEFAULT_DISTRIBUTE_DB = _PROJECT_ROOT / "desk" / "data" / "distribute.db"
_DEAD_LIMIT_DEFAULT    = 25
_DEAD_LIMIT_MAX        = 200


def _distribute_db_path() -> Path:
    env = os.getenv("DESK_DISTRIBUTE_DB_PATH")
    return Path(env) if env else _DEFAULT_DISTRIBUTE_DB


def _empty_distribute_state(*, db_path: Path) -> dict[str, Any]:
    return {
        "push_enabled":  os.getenv("DESK_DISTRIBUTE_PUSH", "0") == "1",
        "db_path":       str(db_path),
        "db_exists":     False,
        "pending_count": 0,
        "dead_count":    0,
        "recent_dead":   [],
    }


def _read_distribute_state(*, dead_limit: int) -> dict[str, Any]:
    """Open the outbox read-only, return counts + recent dead rows.

    Resilient: a missing DB, an unreadable file, or a schema mismatch
    all collapse to the empty state with `db_exists=False`. The endpoint
    must not 500 just because push has never been enabled.
    """
    db_path = _distribute_db_path()
    state = _empty_distribute_state(db_path=db_path)
    if not db_path.is_file():
        return state

    state["db_exists"] = True
    # `uri=True` + `mode=ro` opens read-only — guarantees we never
    # take a write lock against the runner / drain process.
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
    except sqlite3.Error as e:
        log.warning("distribute db open failed: %s", e)
        return state

    try:
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT "
                "  SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending, "
                "  SUM(CASE WHEN status = 'dead'    THEN 1 ELSE 0 END) AS dead "
                "FROM push_queue"
            ).fetchone()
            state["pending_count"] = int(row["pending"] or 0)
            state["dead_count"]    = int(row["dead"]    or 0)
        except sqlite3.Error as e:
            log.warning("distribute count query failed: %s", e)
            return state

        try:
            dead_rows = conn.execute(
                "SELECT id, match_id, updated_at, attempts, last_error, created_at "
                "FROM push_queue WHERE status = 'dead' "
                "ORDER BY id DESC LIMIT ?",
                (dead_limit,),
            ).fetchall()
            state["recent_dead"] = [
                {
                    "id":         int(r["id"]),
                    "match_id":   r["match_id"],
                    "updated_at": r["updated_at"],
                    "attempts":   int(r["attempts"] or 0),
                    "last_error": r["last_error"] or "",
                    "created_at": int(r["created_at"] or 0),
                }
                for r in dead_rows
            ]
        except sqlite3.Error as e:
            log.warning("distribute dead query failed: %s", e)
    finally:
        conn.close()

    return state


@router.get("/distribute", dependencies=[Depends(_gate)])
def get_distribute_state(
    limit: int = Query(default=_DEAD_LIMIT_DEFAULT, ge=1, le=_DEAD_LIMIT_MAX),
) -> dict[str, Any]:
    """Read-only view of the MTA push outbox.

    Surfaces:
      * `push_enabled` — whether DESK_DISTRIBUTE_PUSH=1 right now (env
        flip survives without a redeploy as the loop subprocess re-reads).
      * `pending_count` / `dead_count` — at-a-glance health.
      * `recent_dead` — newest-first list of dead-lettered rows with the
        last error string, so the operator can read WHY they died
        without `sqlite3` shelling into the volume.

    Never 500s — a missing DB or unreadable file returns empty counts.
    """
    return _read_distribute_state(dead_limit=limit)
