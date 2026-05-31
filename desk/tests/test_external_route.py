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


def _sample_outright() -> dict:
    """A published-on-disk outright dict (build_payload shape): verdict +
    copy + a `model` block carrying a nested hard_signal_adjustments."""
    return {
        "outright_id": "fb-wc26-winner",
        "sport": "football",
        "competition": {"code": "wc26", "label": "FIFA World Cup 2026",
                        "stage": "pre_tournament"},
        "market_label": "World Cup 2026 — outright winner",
        "market_venue": "polymarket",
        "market_url": "https://polymarket.com/event/2026-fifa-world-cup-winner-595",
        "candidate": "Argentina",
        "resolves_at": "2026-07-20T00:00:00Z",
        "asof": "2026-05-28T17:44:23Z",
        "verdict": {"state": "pick", "candidate": "YES Argentina", "side": "YES",
                    "team": "Argentina", "edge_pp": 10.33, "lower_edge_pp": 3.35,
                    "model_p": 0.1878, "model_p_lower": 0.118, "model_p_upper": 0.254,
                    "market_p": 0.0845, "market_venue": "polymarket",
                    "market_url": "https://polymarket.com/event/x", "price": "+1083"},
        "copy": {"title": "t", "summary": "s", "blurb": "b", "drivers": ["d"]},
        "model": {"sims": 10000, "bootstrap_samples": 100, "seed": 42,
                  "overround_pp": 3.5,
                  "hard_signal_adjustments": [
                      {"team": "USA", "delta_elo": -8.0, "capped": False,
                       "reason": "injury", "signal_type": "injury",
                       "signal_url": "https://espn.com/x", "source_id": "espn-soccer",
                       "source_name": "ESPN (soccer)", "published_at": "2026-05-21T15:58:17Z"},
                  ]},
        "ladder": [{"team": "Argentina", "model_p": 0.1878, "model_p_lower": 0.118,
                    "model_p_upper": 0.254, "yes_market_p": 0.0845, "no_market_p": 0.9155,
                    "yes_edge_pp": 10.33, "no_edge_pp": -10.33, "yes_lower_edge_pp": 3.35,
                    "no_lower_edge_pp": -16.95, "verdict": "pick", "pick_side": "YES"}],
        "updated_at": "2026-05-28T17:44:38Z",
    }


def _seed_outright(output_dir: Path, published: dict) -> None:
    out = output_dir / "outrights"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{published['outright_id']}.json").write_text(
        __import__("json").dumps(published), encoding="utf-8"
    )


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


# ── External outright GET ─────────────────────────────────────────────


def test_outright_get_returns_wire_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Happy path: the pull returns the wire shape, not the raw on-disk
    JSON — content_type added + hard_signal_adjustments lifted to top."""
    _seed_outright(tmp_path, _sample_outright())
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            "/api/desk/external/outright/fb-wc26-winner",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 200
    payload = r.json()
    assert payload["content_type"] == "outright"
    assert payload["outright_id"] == "fb-wc26-winner"
    # lifted to top level, removed from model
    assert payload["hard_signal_adjustments"][0]["team"] == "USA"
    assert "hard_signal_adjustments" not in payload["model"]
    assert len(payload["ladder"]) == 1


def test_outright_get_matches_canonical_push_transform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """LOCKSTEP guard: the inlined route transform must be byte-identical
    to the canonical push transform. If they drift, this fails."""
    from desk.distribute.outright import outright_wire_payload

    published = _sample_outright()
    _seed_outright(tmp_path, published)
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            "/api/desk/external/outright/fb-wc26-winner",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 200
    assert r.json() == outright_wire_payload(published)


def test_outright_get_requires_bearer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _seed_outright(tmp_path, _sample_outright())
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get("/api/desk/external/outright/fb-wc26-winner")
    assert r.status_code == 401


def test_unknown_outright_returns_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            "/api/desk/external/outright/fb-wc26-nope",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 404


def test_malformed_outright_id_returns_400(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    app = _build_app(monkeypatch, tmp_path, token="dtk_correct-1")
    with TestClient(app) as client:
        r = client.get(
            "/api/desk/external/outright/NOT_A_VALID_ID",
            headers={"Authorization": "Bearer dtk_correct-1"},
        )
    assert r.status_code == 400
