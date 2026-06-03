"""Read-only HTTP surface for MTAI — copied from the live Desk's desk_api.py.

Two routers:
  * `router`          — internal /api/desk/* reads (matches, outrights).
                        Mount this if the stub also fronts a public site;
                        MTAI itself only needs the external pair below.
  * `external_router` — bearer-gated /api/desk/external/* reads. This is
                        the surface MTAI's "Refresh from desk" button hits.
                        Mounted only when DESK_API_BEARER_TOKEN is set.

Both serve the frozen JSON in `output_root()` byte-for-byte. The external
routes return the exact wire shape the push delivers (matches raw;
outrights reshaped via `_outright_wire_shape`).
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

from stubdesk.config import output_root

log = logging.getLogger("stubdesk.api")

router = APIRouter(prefix="/api/desk", tags=["desk"])
external_router = APIRouter(prefix="/api/desk/external", tags=["desk-external"])

_MATCH_ID_RE    = re.compile(r"^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$")
_OUTRIGHT_ID_RE = re.compile(r"^[a-z0-9]{2,8}-[a-z0-9-]{2,64}$")
_SPORT_RE       = re.compile(r"^[a-z]{2,16}$")
_OUTRIGHTS_DIR  = "outrights"


def _sport_dir(sport: str) -> Path:
    if not _SPORT_RE.match(sport):
        raise HTTPException(status_code=400, detail="invalid sport")
    return output_root() / sport


def _outrights_dir() -> Path:
    return output_root() / _OUTRIGHTS_DIR


def _load_match(sport_dir: Path, match_id: str) -> dict[str, Any]:
    if not _MATCH_ID_RE.match(match_id):
        raise HTTPException(status_code=400, detail="invalid match_id")
    path = sport_dir / f"{match_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"match not found: {match_id}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── internal reads ───────────────────────────────────────────────────────

@router.get("/matches")
async def list_matches(
    sport: str = "football",
    competition: str | None = Query(default=None),
) -> dict[str, Any]:
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
        copy_blk = full.get("copy") or {}
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
                "title":   copy_blk.get("title", ""),
                "summary": copy_blk.get("summary", ""),
            },
        })
    return {"sport": sport, "matches": rows, "updated_at": index.get("updated_at")}


@router.get("/match/{match_id}")
async def get_match(match_id: str, sport: str = "football") -> dict[str, Any]:
    return _load_match(_sport_dir(sport), match_id)


@router.get("/outrights")
async def list_outrights() -> dict[str, Any]:
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


# ── external (bearer-gated) — the MTAI safety-net GETs ────────────────────

def _expected_token() -> str | None:
    tok = os.getenv("DESK_API_BEARER_TOKEN")
    return tok or None


def _require_bearer(authorization: str | None = Header(default=None)) -> str:
    expected = _expected_token()
    if expected is None:
        raise HTTPException(status_code=503, detail="bearer auth not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    presented = authorization[len("Bearer "):].strip()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return presented


@external_router.get("/match/{match_id}", dependencies=[Depends(_require_bearer)])
async def external_get_match(match_id: str, sport: str = "football") -> dict[str, Any]:
    """Latest published payload for one match_id — same shape the push wire delivers."""
    return _load_match(_sport_dir(sport), match_id)


def _outright_wire_shape(published: dict[str, Any]) -> dict[str, Any]:
    """Reshape on-disk outright JSON into the MTA wire payload: add
    `content_type: "outright"` and lift `model.hard_signal_adjustments`
    to a top-level list. Kept in lockstep with `wire.outright_wire_payload`.
    """
    wire = copy.deepcopy(published)
    wire["content_type"] = "outright"
    model = wire.get("model")
    hsa = model.pop("hard_signal_adjustments", []) if isinstance(model, dict) else []
    wire["hard_signal_adjustments"] = hsa or []
    return wire


@external_router.get("/outright/{outright_id}", dependencies=[Depends(_require_bearer)])
async def external_get_outright(outright_id: str) -> dict[str, Any]:
    if not _OUTRIGHT_ID_RE.match(outright_id):
        raise HTTPException(status_code=400, detail="invalid outright_id")
    path = _outrights_dir() / f"{outright_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"outright not found: {outright_id}")
    published = json.loads(path.read_text(encoding="utf-8"))
    return _outright_wire_shape(published)
