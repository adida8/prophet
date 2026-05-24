"""Bearer-gated external GET route at /api/desk/external/match/{match_id}.

The route is mounted by server.py only when DESK_API_BEARER_TOKEN is set;
these tests construct the router directly so we can exercise the auth
branch without standing up the full server.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from desk.publish import MatchOutput, Publisher

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _build_app(monkeypatch: pytest.MonkeyPatch, output_dir: Path,
               *, token: str | None = "dtk_test-12345") -> FastAPI:
    """Reload desk_api with the env set, mount its external_router."""
    monkeypatch.setenv("DESK_OUTPUT_DIR", str(output_dir))
    if token is None:
        monkeypatch.delenv("DESK_API_BEARER_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DESK_API_BEARER_TOKEN", token)

    import desk.config as _cfg
    importlib.reload(_cfg)
    if "desk_api" in sys.modules:
        importlib.reload(sys.modules["desk_api"])
    import desk_api  # noqa: E402

    app = FastAPI()
    app.include_router(desk_api.external_router)
    return app


def _seed_match(output_dir: Path, match: MatchOutput) -> None:
    pub = Publisher(output_dir=output_dir)
    pub.write_match(match)


# ── Auth ──────────────────────────────────────────────────────────────


def test_missing_authorization_returns_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fra_mex_pick: MatchOutput,
) -> None:
    _seed_match(tmp_path, fra_mex_pick)
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(f"/api/desk/external/match/{fra_mex_pick.match_id}")
    assert r.status_code == 401
    assert "missing" in r.json()["detail"].lower()


def test_invalid_bearer_returns_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fra_mex_pick: MatchOutput,
) -> None:
    _seed_match(tmp_path, fra_mex_pick)
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            f"/api/desk/external/match/{fra_mex_pick.match_id}",
            headers={"Authorization": "Bearer dtk_wrong-token"},
        )
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


def test_wrong_scheme_returns_401(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fra_mex_pick: MatchOutput,
) -> None:
    """An Authorization header that's not `Bearer …` is rejected."""
    _seed_match(tmp_path, fra_mex_pick)
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            f"/api/desk/external/match/{fra_mex_pick.match_id}",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
    assert r.status_code == 401


def test_unset_token_returns_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fra_mex_pick: MatchOutput,
) -> None:
    """Defence-in-depth — if server.py wrongly mounts the router with no
    token, the dependency still refuses (503 not 200)."""
    _seed_match(tmp_path, fra_mex_pick)
    app = _build_app(monkeypatch, tmp_path, token=None)
    with TestClient(app) as client:
        r = client.get(
            f"/api/desk/external/match/{fra_mex_pick.match_id}",
            headers={"Authorization": "Bearer anything"},
        )
    assert r.status_code == 503


# ── Happy path ────────────────────────────────────────────────────────


def test_valid_bearer_returns_full_match_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fra_mex_pick: MatchOutput,
) -> None:
    _seed_match(tmp_path, fra_mex_pick)
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            f"/api/desk/external/match/{fra_mex_pick.match_id}",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 200
    payload = r.json()
    assert payload["match_id"] == fra_mex_pick.match_id
    assert payload["verdict"]["state"] == "pick"
    assert payload["verdict"]["side"] == "France"
    # Reconstructs back into a MatchOutput — proof the payload is
    # contract-shaped (not a trimmed list-view).
    MatchOutput.model_validate(payload)


# ── 404 ────────────────────────────────────────────────────────────────


def test_unknown_match_returns_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            "/api/desk/external/match/fb-wc26-aaa-bbb-20260601",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 404


def test_malformed_match_id_returns_400(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            "/api/desk/external/match/NOT-A-VALID-ID",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 400


# ── Constant-time compare ─────────────────────────────────────────────


def test_compare_resists_length_differences(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fra_mex_pick: MatchOutput,
) -> None:
    """A token of wildly different length should fail cleanly (not raise)."""
    _seed_match(tmp_path, fra_mex_pick)
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            f"/api/desk/external/match/{fra_mex_pick.match_id}",
            headers={"Authorization": "Bearer x"},
        )
    assert r.status_code == 401
