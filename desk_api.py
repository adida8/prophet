"""Server-side adapter for The Desk's published outputs.

Mounted at /api/desk/* by server.py. Read-only — serves the per-match
JSON and the per-sport index that the engine writes to
desk/data/output/{sport}/.

This module lives at the project root (not inside the `desk/` package)
because the Prophet server runs from project root and the `desk/`
directory ships as an independent Python package with its own
pyproject — it is not pip-installed in the deploy. Anything the server
needs to consume from the desk product gets a thin adapter here, the
same way `ledger/router.py` adapts the Ledger data layer.

Routes
------
GET /api/desk/matches?competition=wc26&sport=football
    List view. Returns one row per match (lightweight): match_id,
    teams, kickoff, competition, verdict.{state, side, edge_pp,
    market_venue, price, market_url}, copy.{title, summary}.

GET /api/desk/match/{match_id}?sport=football
    Full MatchOutput JSON for one fixture.

GET /api/desk/outrights
    Index of all outright winner markets (e.g. WC 2026 winner).

GET /api/desk/outright/{outright_id}
    Full outright JSON — model ladder, verdict, copy, snapshot meta.
"""

from __future__ import annotations

import copy
import hmac
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

log = logging.getLogger("desk_api")

router = APIRouter(prefix="/api/desk", tags=["desk"])
external_router = APIRouter(prefix="/api/desk/external", tags=["desk-external"])

# desk/data/output/{sport}/ — `desk/` is a sibling of this file. The
# root is resolved at call time (not import time) so DESK_OUTPUT_DIR
# can redirect reads, same convention as desk_ops_api._ops_root.
_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_OUTPUT_ROOT = _PROJECT_ROOT / "desk" / "data" / "output"

# Defence-in-depth: the writer guarantees this shape, but the API
# never trusts the URL path to match it.
_MATCH_ID_RE    = re.compile(r"^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$")
_OUTRIGHT_ID_RE = re.compile(r"^[a-z0-9]{2,8}-[a-z0-9-]{2,64}$")
_SPORT_RE       = re.compile(r"^[a-z]{2,16}$")
_OUTRIGHTS_DIR  = "outrights"


def _output_root() -> Path:
    env = os.getenv("DESK_OUTPUT_DIR")
    return Path(env) if env else _DEFAULT_OUTPUT_ROOT


def _sport_dir(sport: str) -> Path:
    if not _SPORT_RE.match(sport):
        raise HTTPException(status_code=400, detail="invalid sport")
    return _output_root() / sport


def _load_match(sport_dir: Path, match_id: str) -> dict[str, Any]:
    if not _MATCH_ID_RE.match(match_id):
        raise HTTPException(status_code=400, detail="invalid match_id")
    path = sport_dir / f"{match_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"match not found: {match_id}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/matches")
async def list_matches(
    sport: str = "football",
    competition: str | None = Query(default=None),
) -> dict[str, Any]:
    """Lightweight list view for the homepage. Filter by competition
    (e.g. `wc26`). Sort is index-driven (writer sorts by kickoff).
    """
    sport_dir  = _sport_dir(sport)
    index_path = sport_dir / "index.json"
    if not index_path.is_file():
        return {"sport": sport, "matches": [], "updated_at": None}

    index = json.loads(index_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for entry in index.get("matches", []):
        match_id = entry.get("match_id", "")
        if not _MATCH_ID_RE.match(match_id):
            continue
        try:
            full = _load_match(sport_dir, match_id)
        except HTTPException:
            continue
        comp_code = (full.get("competition") or {}).get("code", "")
        if competition and comp_code != competition:
            continue
        verdict = full.get("verdict") or {}
        copy    = full.get("copy") or {}
        rows.append({
            "match_id":    full["match_id"],
            "team_a":      full["team_a"],
            "team_b":      full["team_b"],
            "kickoff_utc": full["kickoff_utc"],
            "competition": full.get("competition"),
            "venue":       full.get("venue"),
            "verdict": {
                "state":        verdict.get("state"),
                "side":         verdict.get("side"),
                "edge_pp":      verdict.get("edge_pp"),
                "market_venue": verdict.get("market_venue"),
                "price":        verdict.get("price"),
                "market_url":   verdict.get("market_url"),
                "model_p":      verdict.get("model_p"),
                "market_p":     verdict.get("market_p"),
            },
            "copy": {
                "title":   copy.get("title", ""),
                "summary": copy.get("summary", ""),
            },
        })
    return {
        "sport":      sport,
        "matches":    rows,
        "updated_at": index.get("updated_at"),
    }


@router.get("/match/{match_id}")
async def get_match(match_id: str, sport: str = "football") -> dict[str, Any]:
    return _load_match(_sport_dir(sport), match_id)


# ── Outrights ────────────────────────────────────────────────────────
# Per `desk.outrights.run` the engine writes to
# `desk/data/output/outrights/{outright_id}.json` and maintains
# `index.json` in the same directory.

def _outrights_dir() -> Path:
    return _output_root() / _OUTRIGHTS_DIR


@router.get("/outrights")
async def list_outrights() -> dict[str, Any]:
    """Index of outright winner markets currently published."""
    index_path = _outrights_dir() / "index.json"
    if not index_path.is_file():
        return {"outrights": [], "updated_at": None}
    return json.loads(index_path.read_text(encoding="utf-8"))


@router.get("/outright/{outright_id}")
async def get_outright(outright_id: str) -> dict[str, Any]:
    if not _OUTRIGHT_ID_RE.match(outright_id):
        raise HTTPException(status_code=400, detail="invalid outright_id")
    path = _outrights_dir() / f"{outright_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"outright not found: {outright_id}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── External (bearer-gated) — single-match safety-net GET ─────────────
# Mounted only when DESK_API_BEARER_TOKEN is set (server.py). Used by
# external consumers (today: Market Tips AI) as a manual refresh path
# alongside the push wire. Push covers normal traffic; this is the
# operator-triggered fallback.
#
# The push wire and this route share the same on-disk artefact — the
# returned JSON is byte-equivalent to what the wire delivered (modulo
# httpx's encoding of whatever the writer wrote). See:
# `desk/desk/distribute/` for the push side.


def _expected_token() -> str | None:
    """Read the token at call time so a runtime env flip is honoured.

    Returns None when unset, which makes the dependency 503 — the route
    shouldn't be reachable in that state (server.py guards the mount)
    but defence-in-depth is cheap.
    """
    tok = os.getenv("DESK_API_BEARER_TOKEN")
    return tok or None


def _require_bearer(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: validate `Authorization: Bearer <token>`.

    Constant-time compare so timing leaks don't reveal the prefix. Returns
    the validated token (caller can ignore).
    """
    expected = _expected_token()
    if expected is None:
        raise HTTPException(status_code=503, detail="bearer auth not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    presented = authorization[len("Bearer "):].strip()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return presented


@external_router.get(
    "/match/{match_id}",
    dependencies=[Depends(_require_bearer)],
)
async def external_get_match(
    match_id: str,
    sport: str = "football",
) -> dict[str, Any]:
    """Latest published payload for one match_id.

    Returns the same JSON shape that the push wire delivers. 404 when
    no match has ever been published under this slug. 401 on missing /
    invalid bearer (handled by the dependency).
    """
    return _load_match(_sport_dir(sport), match_id)


def _outright_wire_shape(published: dict[str, Any]) -> dict[str, Any]:
    """Reshape the on-disk outright JSON into the MTA wire payload — the
    exact shape the push wire delivers: add `content_type: "outright"`
    and lift `model.hard_signal_adjustments` to a top-level list.

    Kept in LOCKSTEP with the canonical transform at
    `desk/desk/distribute/outright.py::outright_wire_payload`. The web
    process stays decoupled from the desk package (only `site/generate.py`
    bridges it), so this is inlined rather than imported — a test
    (`desk/tests/test_external_route.py`) asserts the two stay
    byte-identical so drift fails CI.
    """
    wire = copy.deepcopy(published)
    wire["content_type"] = "outright"
    model = wire.get("model")
    hsa = model.pop("hard_signal_adjustments", []) if isinstance(model, dict) else []
    wire["hard_signal_adjustments"] = hsa or []
    return wire


@external_router.get(
    "/outright/{outright_id}",
    dependencies=[Depends(_require_bearer)],
)
async def external_get_outright(outright_id: str) -> dict[str, Any]:
    """Latest published payload for one outright_id, in the same wire
    shape the push delivers (the `fb-wc26-winner.mta-sample.json` shape:
    `content_type: "outright"` + top-level `hard_signal_adjustments`).

    Lets MTA's "Refresh from desk" button pull an outright the same way
    it pulls a match. 404 when no outright has been published under this
    id. 400 on a malformed id. 401 on missing / invalid bearer.
    """
    if not _OUTRIGHT_ID_RE.match(outright_id):
        raise HTTPException(status_code=400, detail="invalid outright_id")
    path = _outrights_dir() / f"{outright_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"outright not found: {outright_id}")
    published = json.loads(path.read_text(encoding="utf-8"))
    return _outright_wire_shape(published)
