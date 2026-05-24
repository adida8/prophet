"""Tests for GET /api/desk/ops/distribute — the MTA push-wire visibility panel.

Mirrors the test_ops_api.py shape (project-root `desk_ops_api` module,
sys.path injection, env reload). Covers:

  * Auth: 404 when ops disabled, 401 with bad creds (same _gate the
    other ops routes use).
  * 200 with no DB: empty counts, db_exists=False, no 500.
  * 200 with pending rows only: counts correct, recent_dead empty.
  * 200 with a dead row: counts + recent_dead populated with last_error.
  * push_enabled flag is read from DESK_DISTRIBUTE_PUSH at call time.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desk.distribute import Outbox


def _build_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FastAPI:
    """Spin up an isolated FastAPI app with the ops router mounted.

    Points DESK_OUTPUT_DIR at tmp + DESK_DISTRIBUTE_DB_PATH at a fresh
    db file under tmp so each test is hermetic.
    """
    monkeypatch.setenv("DESK_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("DESK_DISTRIBUTE_DB_PATH", str(tmp_path / "distribute.db"))
    import desk.config as _cfg
    importlib.reload(_cfg)
    if "desk_ops_api" in sys.modules:
        importlib.reload(sys.modules["desk_ops_api"])
    import desk_ops_api  # noqa: E402

    app = FastAPI()
    app.include_router(desk_ops_api.router)
    return app


def _enable_ops(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    monkeypatch.setenv("DESK_OPS_USER", "ops")
    monkeypatch.setenv("DESK_OPS_PASS", "s3cret")
    return ("ops", "s3cret")


# ── Auth ──────────────────────────────────────────────────────────────


def test_distribute_404_when_ops_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv("DESK_OPS_USER", raising=False)
    monkeypatch.delenv("DESK_OPS_PASS", raising=False)
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute")
    assert r.status_code == 404


def test_distribute_401_with_bad_creds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _enable_ops(monkeypatch)
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute", auth=("ops", "wrong"))
    assert r.status_code == 401


# ── 200 — empty / pending / dead ──────────────────────────────────────


def test_distribute_no_db_returns_empty_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Fresh deploy — push has never run, no DB yet. Endpoint must
    return zeros, not 500."""
    auth = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "0")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute", auth=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["push_enabled"]   is False
    assert body["db_exists"]      is False
    assert body["pending_count"]  == 0
    assert body["dead_count"]     == 0
    assert body["recent_dead"]    == []
    assert body["db_path"].endswith("distribute.db")


def test_distribute_pending_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    auth = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "1")
    db = tmp_path / "distribute.db"
    with Outbox(db) as ob:
        ob.enqueue(match_id="fb-wc26-fra-mex-20260612", updated_at="2026-06-12T17:00:00Z",
                   body=b'{"x":1}', now=100)
        ob.enqueue(match_id="fb-wc26-arg-bra-20260619", updated_at="2026-06-19T17:00:00Z",
                   body=b'{"x":2}', now=200)

    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute", auth=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["push_enabled"]   is True
    assert body["db_exists"]      is True
    assert body["pending_count"]  == 2
    assert body["dead_count"]     == 0
    assert body["recent_dead"]    == []


def test_distribute_dead_row_surfaces_last_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    auth = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "1")
    db = tmp_path / "distribute.db"
    with Outbox(db) as ob:
        ob.enqueue(match_id="fb-wc26-good-mat-20260612",
                   updated_at="2026-06-12T17:00:00Z",
                   body=b'p', now=100)
        rid = ob.enqueue(match_id="fb-wc26-dead-mat-20260620",
                         updated_at="2026-06-20T17:00:00Z",
                         body=b'q', now=200)
        ob.mark_dead(rid, reason="permanent: status 413: Payload Too Large")

    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute", auth=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["pending_count"] == 1
    assert body["dead_count"]    == 1
    assert len(body["recent_dead"]) == 1
    dead = body["recent_dead"][0]
    assert dead["match_id"]   == "fb-wc26-dead-mat-20260620"
    assert dead["attempts"]   == 1
    assert "413" in dead["last_error"]
    assert dead["updated_at"] == "2026-06-20T17:00:00Z"


def test_distribute_recent_dead_is_newest_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Multiple dead rows — newest first (matches the list_dead contract)."""
    auth = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "1")
    db = tmp_path / "distribute.db"
    with Outbox(db) as ob:
        for i in range(3):
            rid = ob.enqueue(match_id=f"fb-wc26-dead-m{i}-20260612",
                             updated_at=f"2026-06-12T17:0{i}:00Z",
                             body=b'x', now=100 + i)
            ob.mark_dead(rid, reason=f"err{i}")

    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute", auth=auth)
    body = r.json()
    assert [d["match_id"] for d in body["recent_dead"]] == [
        "fb-wc26-dead-m2-20260612",
        "fb-wc26-dead-m1-20260612",
        "fb-wc26-dead-m0-20260612",
    ]


def test_distribute_limit_param_caps_dead_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    auth = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "1")
    db = tmp_path / "distribute.db"
    with Outbox(db) as ob:
        for i in range(5):
            rid = ob.enqueue(match_id=f"fb-wc26-d{i}-mat-20260612",
                             updated_at="2026-06-12T17:00:00Z",
                             body=b'x', now=100 + i)
            ob.mark_dead(rid, reason=f"err{i}")

    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/distribute?limit=2", auth=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["dead_count"]       == 5
    assert len(body["recent_dead"]) == 2


def test_distribute_push_enabled_reads_env_at_call_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The flag is env-driven; flipping DESK_DISTRIBUTE_PUSH without a
    restart changes the next response."""
    auth = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "0")
    app = _build_app(monkeypatch, tmp_path)

    r1 = TestClient(app).get("/api/desk/ops/distribute", auth=auth)
    assert r1.json()["push_enabled"] is False

    monkeypatch.setenv("DESK_DISTRIBUTE_PUSH", "1")
    r2 = TestClient(app).get("/api/desk/ops/distribute", auth=auth)
    assert r2.json()["push_enabled"] is True
