"""FastAPI router tests — gate, list, detail, transitions, bundle."""

from __future__ import annotations

import importlib
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desk.social import SocialQueue
from desk.social.models import DraftKind, DraftStatus
from desk.social.runner import draft_daily


def _build_app(monkeypatch: pytest.MonkeyPatch, *,
               db_path: Path, assets_dir: Path,
               user: str = "ops", pw: str = "secret") -> FastAPI:
    monkeypatch.setenv("DESK_OPS_USER",         user)
    monkeypatch.setenv("DESK_OPS_PASS",         pw)
    monkeypatch.setenv("DESK_SOCIAL_DB_PATH",   str(db_path))
    monkeypatch.setenv("DESK_SOCIAL_ASSETS_DIR", str(assets_dir))
    # Reload modules so they re-read env constants.
    if "desk_ops_api" in sys.modules:
        importlib.reload(sys.modules["desk_ops_api"])
    if "desk_social_api" in sys.modules:
        importlib.reload(sys.modules["desk_social_api"])
    import desk_social_api  # noqa: E402

    app = FastAPI()
    app.include_router(desk_social_api.router)
    return app


def _seed_pending(fra_mex_pick, tmp_path: Path) -> str:
    """Drop a pending draft into the queue via the drafter; return id."""
    with SocialQueue(tmp_path / "q.db") as q:
        d = draft_daily(
            queue=q, assets_dir=tmp_path / "assets",
            matches=[fra_mex_pick],
            now=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
        )
    assert d is not None
    return d.draft_id


# ── Gate ──────────────────────────────────────────────────────────────


def test_gate_404_when_creds_unset(monkeypatch: pytest.MonkeyPatch,
                                    tmp_path: Path) -> None:
    monkeypatch.delenv("DESK_OPS_USER", raising=False)
    monkeypatch.delenv("DESK_OPS_PASS", raising=False)
    monkeypatch.setenv("DESK_SOCIAL_DB_PATH",   str(tmp_path / "q.db"))
    monkeypatch.setenv("DESK_SOCIAL_ASSETS_DIR", str(tmp_path / "assets"))
    if "desk_social_api" in sys.modules:
        importlib.reload(sys.modules["desk_social_api"])
    import desk_social_api
    app = FastAPI()
    app.include_router(desk_social_api.router)
    client = TestClient(app)
    r = client.get("/api/desk/social/drafts")
    assert r.status_code == 404


def test_gate_401_on_no_creds(monkeypatch: pytest.MonkeyPatch,
                                tmp_path: Path) -> None:
    app = _build_app(monkeypatch,
                       db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.get("/api/desk/social/drafts")
    assert r.status_code == 401


def test_gate_401_on_bad_creds(monkeypatch: pytest.MonkeyPatch,
                                  tmp_path: Path) -> None:
    app = _build_app(monkeypatch,
                       db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.get("/api/desk/social/drafts", auth=("ops", "wrong"))
    assert r.status_code == 401


# ── Read routes ───────────────────────────────────────────────────────


def test_list_empty_when_no_db(monkeypatch: pytest.MonkeyPatch,
                                tmp_path: Path) -> None:
    app = _build_app(monkeypatch,
                       db_path=tmp_path / "nope.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.get("/api/desk/social/drafts", auth=("ops", "secret"))
    assert r.status_code == 200
    assert r.json() == {"drafts": []}


def test_list_and_detail(monkeypatch: pytest.MonkeyPatch, fra_mex_pick,
                          tmp_path: Path) -> None:
    db_path    = tmp_path / "q.db"
    assets_dir = tmp_path / "assets"
    draft_id = _seed_pending(fra_mex_pick, tmp_path)

    # Drafter wrote q.db at tmp_path/q.db; point the API there.
    app = _build_app(monkeypatch, db_path=db_path,
                       assets_dir=assets_dir)
    client = TestClient(app)

    r = client.get("/api/desk/social/drafts", auth=("ops", "secret"))
    assert r.status_code == 200
    assert len(r.json()["drafts"]) == 1
    assert r.json()["drafts"][0]["draft_id"] == draft_id

    r2 = client.get(f"/api/desk/social/drafts/{draft_id}",
                     auth=("ops", "secret"))
    assert r2.status_code == 200
    body = r2.json()
    assert body["caption_ig"]
    assert body["caption_x"]
    assert len(body["slides"]) == 4


def test_get_unknown_draft_returns_404(monkeypatch: pytest.MonkeyPatch,
                                         fra_mex_pick,
                                         tmp_path: Path) -> None:
    _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.get("/api/desk/social/drafts/nope",
                    auth=("ops", "secret"))
    assert r.status_code == 404


# ── Transitions ───────────────────────────────────────────────────────


def test_approve_and_mark_posted(monkeypatch: pytest.MonkeyPatch,
                                   fra_mex_pick,
                                   tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)

    r = client.post(f"/api/desk/social/drafts/{draft_id}/approve",
                     auth=("ops", "secret"))
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r2 = client.post(f"/api/desk/social/drafts/{draft_id}/mark-posted",
                      auth=("ops", "secret"),
                      json={"ig_permalink": "https://ig/p/xyz",
                            "x_tweet_id":   "42"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "published"
    assert body["ig_permalink"] == "https://ig/p/xyz"
    assert body["x_tweet_id"] == "42"


def test_invalid_transition_returns_409(monkeypatch: pytest.MonkeyPatch,
                                          fra_mex_pick,
                                          tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)

    # Pending → mark-posted (would be APPROVED → PUBLISHED) is illegal
    # from pending.
    r = client.post(f"/api/desk/social/drafts/{draft_id}/mark-posted",
                     auth=("ops", "secret"), json={})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_state"
    assert detail["from"]  == "pending"


def test_edit_caption_updates_text(monkeypatch: pytest.MonkeyPatch,
                                     fra_mex_pick,
                                     tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)

    r = client.post(
        f"/api/desk/social/drafts/{draft_id}/edit-caption",
        auth=("ops", "secret"),
        json={"platform": "ig", "text": "rewritten by hand"},
    )
    assert r.status_code == 200
    assert r.json()["caption_ig"] == "rewritten by hand"
    assert len(r.json()["edit_history"]) == 1


def test_edit_caption_rejects_bad_platform(monkeypatch: pytest.MonkeyPatch,
                                             fra_mex_pick,
                                             tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.post(
        f"/api/desk/social/drafts/{draft_id}/edit-caption",
        auth=("ops", "secret"),
        json={"platform": "tiktok", "text": "hi"},
    )
    assert r.status_code == 400


# ── Bundle ────────────────────────────────────────────────────────────


def test_bundle_zip_round_trip(monkeypatch: pytest.MonkeyPatch,
                                 fra_mex_pick,
                                 tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)

    # Bundle download is only legal when status >= approved.
    r_pending = client.get(f"/api/desk/social/drafts/{draft_id}/bundle.zip",
                            auth=("ops", "secret"))
    assert r_pending.status_code == 409

    client.post(f"/api/desk/social/drafts/{draft_id}/approve",
                  auth=("ops", "secret"))

    r = client.get(f"/api/desk/social/drafts/{draft_id}/bundle.zip",
                    auth=("ops", "secret"))
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert names == {
        "slide-1.png", "slide-2.png", "slide-3.png", "slide-4.png",
        "caption-ig.txt", "caption-x.txt", "meta.json",
    }


def test_slide_preview_route(monkeypatch: pytest.MonkeyPatch,
                                fra_mex_pick,
                                tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.get(f"/api/desk/social/drafts/{draft_id}/slides/1.png",
                     auth=("ops", "secret"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")


def test_slide_route_bad_slide_no(monkeypatch: pytest.MonkeyPatch,
                                    fra_mex_pick,
                                    tmp_path: Path) -> None:
    draft_id = _seed_pending(fra_mex_pick, tmp_path)
    app = _build_app(monkeypatch, db_path=tmp_path / "q.db",
                       assets_dir=tmp_path / "assets")
    client = TestClient(app)
    r = client.get(f"/api/desk/social/drafts/{draft_id}/slides/9.png",
                     auth=("ops", "secret"))
    assert r.status_code == 400
