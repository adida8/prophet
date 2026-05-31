"""Tests for /api/desk/ops/schedules — the unified loop-control endpoints.

Uses FastAPI's TestClient + Basic auth env. The `desk_refresh` row is
special: its enabled state mirrors control.json (the existing Desk admin
tab's source of truth), so a flip via the new endpoint should land in
control.json, not schedules.json.
"""

from __future__ import annotations

import json
import os
from base64 import b64encode
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import desk_ops_api as api


def _basic_auth(user: str, pwd: str) -> dict[str, str]:
    creds = b64encode(f"{user}:{pwd}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DESK_OPS_DIR", str(tmp_path))
    monkeypatch.setenv("DESK_OPS_USER", "u")
    monkeypatch.setenv("DESK_OPS_PASS", "p")

    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_get_schedules_returns_every_registered_loop(client: TestClient) -> None:
    r = client.get("/api/desk/ops/schedules", headers=_basic_auth("u", "p"))
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {row["id"] for row in body["loops"]}
    # Must include every loop in the registry.
    from loop_registry import LOOPS
    assert ids == {ld.id for ld in LOOPS}


def test_ledger_starts_off_lineups_starts_off(client: TestClient) -> None:
    r = client.get("/api/desk/ops/schedules", headers=_basic_auth("u", "p"))
    rows = {row["id"]: row for row in r.json()["loops"]}
    assert rows["ledger_refresh"]["state"]["enabled"] is False
    assert rows["lineups_refresh"]["state"]["enabled"] is False


def test_toggle_ledger_persists_to_schedules_json(
    client: TestClient, tmp_path: Path,
) -> None:
    r = client.post(
        "/api/desk/ops/schedules/ledger_refresh/enabled",
        json={"enabled": True},
        headers=_basic_auth("u", "p"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    rows = {row["id"]: row for row in body["loops"]}
    assert rows["ledger_refresh"]["state"]["enabled"] is True

    # Hit disk: the row in schedules.json must show enabled=true.
    on_disk = json.loads((tmp_path / "schedules.json").read_text(encoding="utf-8"))
    assert on_disk["loops"]["ledger_refresh"]["enabled"] is True


def test_toggle_desk_refresh_writes_to_control_json(
    client: TestClient, tmp_path: Path,
) -> None:
    """`desk_refresh` is the one row that delegates to control.json so the
    existing Desk admin tab + the schedules page agree."""
    # Default state — control.json absent, treated as enabled=True. Turn it off.
    r = client.post(
        "/api/desk/ops/schedules/desk_refresh/enabled",
        json={"enabled": False},
        headers=_basic_auth("u", "p"),
    )
    assert r.status_code == 200
    body = r.json()
    rows = {row["id"]: row for row in body["loops"]}
    assert rows["desk_refresh"]["state"]["enabled"] is False

    # The write lands in control.json — schedules.json's desk_refresh row
    # is irrelevant for the enabled bit.
    control_on_disk = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert control_on_disk["enabled"] is False


def test_unknown_loop_id_404s(client: TestClient) -> None:
    r = client.post(
        "/api/desk/ops/schedules/not_a_loop/enabled",
        json={"enabled": True},
        headers=_basic_auth("u", "p"),
    )
    assert r.status_code == 404


def test_missing_enabled_in_body_400s(client: TestClient) -> None:
    r = client.post(
        "/api/desk/ops/schedules/ledger_refresh/enabled",
        json={},
        headers=_basic_auth("u", "p"),
    )
    assert r.status_code == 400


def test_auth_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_OPS_DIR", str(tmp_path))
    monkeypatch.setenv("DESK_OPS_USER", "u")
    monkeypatch.setenv("DESK_OPS_PASS", "p")
    app = FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    r = c.get("/api/desk/ops/schedules")
    assert r.status_code == 401


def test_disabled_when_creds_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without DESK_OPS_USER + DESK_OPS_PASS the whole surface 404s."""
    monkeypatch.setenv("DESK_OPS_DIR", str(tmp_path))
    monkeypatch.delenv("DESK_OPS_USER", raising=False)
    monkeypatch.delenv("DESK_OPS_PASS", raising=False)
    app = FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    r = c.get("/api/desk/ops/schedules")
    assert r.status_code == 404
