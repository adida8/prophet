"""Server-side adapter for The Desk's ops dashboard.

Mounted at /api/desk/ops/* by server.py. Read-only — serves the
`RunReport` JSON the runner persists to `desk/data/output/ops/runs/`.

This module lives at the project root next to `desk_api.py` for the
same architectural reason: the server runs from project root and
`desk/` ships as an independent Python package that is NOT pip-
installed in the Railway deploy. We therefore can't `from desk.* import …`
from this file — both routers do pure filesystem reads.

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

GET /api/desk/ops/runs/{run_id}
    Full run report for one run. 400 on a malformed id, 404 if absent.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

log = logging.getLogger("desk_ops_api")

router = APIRouter(prefix="/api/desk/ops", tags=["desk-ops"])
_basic = HTTPBasic(auto_error=False)

# desk/data/output/ops/ — `desk/` is a sibling of this file. Same
# convention as desk_api.py. Tests + non-default deploys can override
# the root by exporting DESK_OUTPUT_DIR — same env var the runner reads
# in desk/desk/config.py, so writer + API always agree on a path.
_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_OUTPUT = _PROJECT_ROOT / "desk" / "data" / "output"


def _ops_root() -> Path:
    return Path(os.getenv("DESK_OUTPUT_DIR") or _DEFAULT_OUTPUT) / "ops"


def _runs_dir() -> Path:
    return _ops_root() / "runs"


def _index_path() -> Path:
    return _ops_root() / "index.json"

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
    return {
        "runs":       runs[:limit],
        "updated_at": manifest.get("updated_at"),
    }


@router.get("/runs/{run_id}", dependencies=[Depends(_gate)])
def get_run(run_id: str) -> dict:
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="malformed run_id")
    return _read_run(run_id)
