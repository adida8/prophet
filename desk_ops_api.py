"""Server-side adapter for The Desk's ops dashboard.

Mounted at /api/desk/ops/* by server.py. Read-only — serves the
`RunReport` JSON the runner persists to `desk/data/output/ops/runs/`.

This module lives at the project root (not inside the `desk/` package)
for the same reason as `desk_api.py`: the server runs from project
root and `desk/` ships as an independent Python package.

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
    The most recent `RunReport`.

GET /api/desk/ops/runs?limit=50
    Manifest of recent runs (newest first), one compact row per run.

GET /api/desk/ops/runs/{run_id}
    Full `RunReport` for one run. 400 on a malformed id, 404 if absent.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from desk.config import OUTPUT_DIR
from desk.ops import Recorder
from desk.ops.report import RUN_ID_RE

log = logging.getLogger("desk_ops_api")

router = APIRouter(prefix="/api/desk/ops", tags=["desk-ops"])
_basic = HTTPBasic(auto_error=False)


def _creds_from_env() -> tuple[str, str] | None:
    """Return the configured (user, pass) or None when disabled.

    Both vars must be set, both must be non-empty. A partial config is
    treated as disabled — better to 404 than to ship an unauthed surface
    because someone set USER but forgot PASS.
    """
    user = (os.getenv("DESK_OPS_USER") or "").strip()
    pwd  = (os.getenv("DESK_OPS_PASS") or "").strip()
    if not user or not pwd:
        return None
    return user, pwd


def _recorder() -> Recorder:
    """Recorder rooted at the same `data/output/ops` the runner writes to."""
    return Recorder(root=Path(OUTPUT_DIR) / "ops")


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


@router.get("/latest", dependencies=[Depends(_gate)])
def get_latest() -> dict:
    report = _recorder().latest()
    if report is None:
        raise HTTPException(status_code=404, detail="no runs recorded yet")
    return report.model_dump(mode="json", by_alias=True)


@router.get("/runs", dependencies=[Depends(_gate)])
def list_runs(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    manifest = _recorder().manifest()
    rows = [e.model_dump(mode="json", by_alias=True) for e in manifest.runs[:limit]]
    return {
        "runs":       rows,
        "updated_at": manifest.updated_at.isoformat().replace("+00:00", "Z"),
    }


@router.get("/runs/{run_id}", dependencies=[Depends(_gate)])
def get_run(run_id: str) -> dict:
    # Defence-in-depth: never let an arbitrary string become a filesystem
    # lookup. Mirrors the `_MATCH_ID_RE` validator in `desk_api.py`.
    if not RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="malformed run_id")
    rec = _recorder()
    path = rec.runs_dir / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"no such run: {run_id}")
    return rec.read(run_id).model_dump(mode="json", by_alias=True)
