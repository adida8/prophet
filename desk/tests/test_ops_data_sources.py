"""Tests for GET /api/desk/ops/data-sources — external-providers panel.

Mirrors the test_ops_distribute.py shape (project-root `desk_ops_api`
module, sys.path injection, env reload). Covers:

  * Auth: 404 when ops disabled, 401 with bad creds (same _gate the
    other ops routes use).
  * 200 with no caches: empty counts, all `db_exists=False`, no 500.
  * 200 with api-football cache populated: counts surface correctly.
  * 200 with elo cache populated: counts surface correctly.
  * openweathermap: surfaces `key_configured` + `data_flow_status`
    honestly as `not_wired` (B.2 deferred).
  * Flag env vars (DESK_RANK_FORM_FETCH, DESK_INJURY_FETCH,
    DESK_ELO_FETCH) read at call time so an env flip survives.
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

from desk.data.api_football.cache import APIFootballCache
from desk.data.elo.cache import EloCache


def _build_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FastAPI:
    monkeypatch.setenv("DESK_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("DESK_API_FOOTBALL_DB_PATH", str(tmp_path / "api_football.db"))
    monkeypatch.setenv("DESK_ELO_DB_PATH", str(tmp_path / "elo.db"))
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

def test_data_sources_404_when_ops_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("DESK_OPS_USER", raising=False)
    monkeypatch.delenv("DESK_OPS_PASS", raising=False)
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources")
    assert r.status_code == 404


def test_data_sources_401_with_bad_creds(monkeypatch, tmp_path):
    _enable_ops(monkeypatch)
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get(
        "/api/desk/ops/data-sources", auth=("ops", "wrong"),
    )
    assert r.status_code == 401


# ── Empty / fresh deploy ──────────────────────────────────────────────

def test_data_sources_200_with_no_caches(monkeypatch, tmp_path):
    creds = _enable_ops(monkeypatch)
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources", auth=creds)
    assert r.status_code == 200
    body = r.json()
    assert "now" in body
    af = body["api_football"]
    elo = body["elo"]
    ow = body["openweathermap"]
    assert af["db_exists"] is False
    assert af["team_count"] == 0
    assert af["form_delta_count"] == 0
    assert af["injury_penalty_count"] == 0
    assert af["fetches"] == []
    assert elo["db_exists"] is False
    assert elo["national_count"] == 0
    assert elo["club_count"] == 0
    assert ow["data_flow_status"] == "not_wired"


# ── api-football populated ────────────────────────────────────────────

def test_data_sources_with_api_football_data(monkeypatch, tmp_path):
    creds = _enable_ops(monkeypatch)
    db_path = tmp_path / "api_football.db"
    with APIFootballCache(db_path) as cache:
        cache.upsert_team_resolution("fra", 2, source_label="test")
        cache.upsert_team_resolution("bra", 6, source_label="test")
        cache.upsert_form_delta("fra", form_delta=0.3, sample_size=10)
        cache.mark_fetch("/fixtures?team=2&last=10", "ok")

    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources", auth=creds)
    assert r.status_code == 200
    af = r.json()["api_football"]
    assert af["db_exists"] is True
    assert af["team_count"] == 2
    assert af["form_delta_count"] == 1
    assert len(af["fetches"]) == 1
    assert af["fetches"][0]["endpoint"] == "/fixtures?team=2&last=10"
    assert af["fetches"][0]["last_status"] == "ok"


# ── elo populated ─────────────────────────────────────────────────────

def test_data_sources_with_elo_data(monkeypatch, tmp_path):
    creds = _enable_ops(monkeypatch)
    db_path = tmp_path / "elo.db"
    with EloCache(db_path) as cache:
        cache.upsert_national("fra", 2030.0,
                              source_id="eloratings", source_url="x")
        cache.upsert_club("epl-mci", 1825.0,
                          source_id="clubelo", source_url="x")
        cache.mark_fetch("eloratings", "ok")
        cache.mark_fetch("clubelo", "ok")

    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources", auth=creds)
    assert r.status_code == 200
    elo = r.json()["elo"]
    assert elo["db_exists"] is True
    assert elo["national_count"] == 1
    assert elo["club_count"] == 1
    source_ids = {f["source_id"] for f in elo["fetches"]}
    assert source_ids == {"eloratings", "clubelo"}


# ── Flag env vars surface ─────────────────────────────────────────────

def test_fetch_flag_env_vars_surface(monkeypatch, tmp_path):
    creds = _enable_ops(monkeypatch)
    monkeypatch.setenv("DESK_RANK_FORM_FETCH", "1")
    monkeypatch.setenv("DESK_INJURY_FETCH", "1")
    monkeypatch.setenv("DESK_ELO_FETCH", "1")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources", auth=creds)
    body = r.json()
    assert body["api_football"]["fetch_enabled"] is True
    assert body["api_football"]["injuries_enabled"] is True
    assert body["elo"]["fetch_enabled"] is True


def test_key_configured_surfaces_without_leaking(monkeypatch, tmp_path):
    creds = _enable_ops(monkeypatch)
    monkeypatch.setenv("API_FOOTBALL_KEY", "secret-do-not-echo")
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "secret-do-not-echo")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources", auth=creds)
    body = r.json()
    assert body["api_football"]["key_configured"] is True
    assert body["openweathermap"]["key_configured"] is True
    # Crucial: the actual key value must NEVER appear in the response.
    raw = r.text
    assert "secret-do-not-echo" not in raw


def test_openweathermap_status_is_honest(monkeypatch, tmp_path):
    """B.2 isn't wired beyond the probe. Dashboard surfaces that
    fact honestly rather than implying data is flowing."""
    creds = _enable_ops(monkeypatch)
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "anything")
    app = _build_app(monkeypatch, tmp_path)
    r = TestClient(app).get("/api/desk/ops/data-sources", auth=creds)
    ow = r.json()["openweathermap"]
    assert ow["key_configured"] is True
    assert ow["data_flow_status"] == "not_wired"
    assert "B.2" in ow["note"]
