"""PR 4 — ops API tests.

Covers the access gate (404 when disabled, 401 on bad/missing creds,
200 on good creds), run_id validation, and the three read routes.

The API module (`desk_ops_api`) lives at the repo root next to
`server.py`. Tests reach it by appending the repo root to `sys.path`.
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# `desk_ops_api` is a project-root module — add it to sys.path before
# the first import, just like the harness puts cwd at the project root
# when the server boots.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desk.ops import Recorder
from desk.ops.report import RunReport, run_id_for


def _build_app(monkeypatch: pytest.MonkeyPatch, ops_dir: Path) -> FastAPI:
    """Spin up an isolated FastAPI app with the ops router mounted.

    Point `DESK_OUTPUT_DIR` at the temp dir so the API's recorder reads
    from the right place; reload the desk.config + desk_ops_api modules
    so they pick up the new env. The reload ensures no stale OUTPUT_DIR
    leaks from a previous test.
    """
    monkeypatch.setenv("DESK_OUTPUT_DIR", str(ops_dir))
    # Reload so OUTPUT_DIR is re-read at import time (it's a module-level
    # constant in desk.config).
    import desk.config as _cfg
    importlib.reload(_cfg)
    if "desk_ops_api" in sys.modules:
        importlib.reload(sys.modules["desk_ops_api"])
    import desk_ops_api  # noqa: E402

    app = FastAPI()
    app.include_router(desk_ops_api.router)
    return app


def _persist_report(ops_root: Path, *, hour: int = 6,
                    status: str = "ok", picks: int = 0) -> RunReport:
    """Drop a minimal report into the recorder so the API has something
    to serve back."""
    rec = Recorder(root=ops_root / "ops")
    ts = datetime(2026, 5, 21, hour, 0, 0, tzinfo=timezone.utc)
    from desk.ops.report import StageCount, VerdictCounts
    r = RunReport(
        run_id=run_id_for(ts),
        started_at=ts,
        finished_at=ts,
        duration_s=0.0,
        trigger="manual",
        status=status,
        competitions=["wc26"],
        funnel=[StageCount(stage="published", n=picks)],
        verdicts=VerdictCounts(pick=picks),
    )
    rec.persist(r)
    return r


# ── Disabled-by-default (spec §9) ────────────────────────────────────

def test_disabled_returns_404_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Spec §9: when DESK_OPS_USER/DESK_OPS_PASS are unset the surface
    is invisible — 404, not 401. No acknowledgement it exists."""
    monkeypatch.delenv("DESK_OPS_USER", raising=False)
    monkeypatch.delenv("DESK_OPS_PASS", raising=False)
    app = _build_app(monkeypatch, tmp_path)
    client = TestClient(app)

    for path in ["/api/desk/ops/latest",
                 "/api/desk/ops/runs",
                 "/api/desk/ops/runs/run-20260521T060000Z"]:
        r = client.get(path)
        assert r.status_code == 404, (path, r.status_code, r.text)


def test_partial_env_still_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """USER set but PASS unset → treated as disabled, returns 404. Never
    auto-promote to authed-by-username-only."""
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.delenv("DESK_OPS_PASS", raising=False)
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/latest")
    assert r.status_code == 404


# ── 401 ladder ───────────────────────────────────────────────────────

def test_missing_creds_returns_401_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/latest")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower().startswith("basic")


def test_wrong_creds_returns_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/latest", auth=("ops", "wrong"))
    assert r.status_code == 401


# ── 200 / 400 / 404 with good creds ─────────────────────────────────

def test_latest_returns_most_recent_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _persist_report(tmp_path, hour=6, picks=1)
    _persist_report(tmp_path, hour=7, picks=3)

    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/latest", auth=("ops", "s3cret"))
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "run-20260521T070000Z"
    # `pass` (not `pass_`) confirms by-alias dump went through the API too.
    assert "pass" in body["verdicts"]


def test_latest_404_when_no_runs_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/latest", auth=("ops", "s3cret"))
    assert r.status_code == 404


def test_runs_lists_newest_first_with_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    for hour in [6, 7, 8]:
        _persist_report(tmp_path, hour=hour)

    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    client = TestClient(app)

    r = client.get("/api/desk/ops/runs", auth=("ops", "s3cret"))
    assert r.status_code == 200
    rows = r.json()["runs"]
    assert [row["run_id"] for row in rows] == [
        "run-20260521T080000Z",
        "run-20260521T070000Z",
        "run-20260521T060000Z",
    ]

    r2 = client.get("/api/desk/ops/runs?limit=1", auth=("ops", "s3cret"))
    assert r2.status_code == 200
    assert [row["run_id"] for row in r2.json()["runs"]] == ["run-20260521T080000Z"]


def test_run_by_id_returns_full_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _persist_report(tmp_path, hour=6, picks=2)

    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get(
        "/api/desk/ops/runs/run-20260521T060000Z",
        auth=("ops", "s3cret"),
    )
    assert r.status_code == 200
    assert r.json()["run_id"] == "run-20260521T060000Z"


def test_malformed_run_id_returns_400(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Defence-in-depth: a value that's in the path slot but isn't a
    valid run_id must be rejected before any filesystem lookup."""
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get(
        "/api/desk/ops/runs/not-a-valid-id",
        auth=("ops", "s3cret"),
    )
    assert r.status_code == 400


def test_unknown_run_id_returns_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get(
        "/api/desk/ops/runs/run-20991231T235959Z",
        auth=("ops", "s3cret"),
    )
    assert r.status_code == 404
