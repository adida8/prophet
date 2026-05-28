"""Server-side adapter for The Desk's social-automation queue.

Mounted at /api/desk/social/* by server.py. Same architectural pattern
as `desk_api.py` + `desk_ops_api.py`: lives at the project root next to
the other API shims so we don't `from desk.*` from FastAPI (the `desk/`
package is not pip-installed in production — runs as a subprocess).
Filesystem + sqlite is the only shared surface.

Auth: re-uses the existing `_gate` dependency from `desk_ops_api.py`,
so the same HTTP Basic creds (DESK_OPS_USER / DESK_OPS_PASS) protect
the social routes too. When those env vars are unset the gate raises
404 so the surface looks like it doesn't exist.

Routes
------
GET    /api/desk/social/drafts                       — list (filter by status, kind, limit)
GET    /api/desk/social/drafts/{draft_id}             — detail
POST   /api/desk/social/drafts/{draft_id}/edit-caption — caption editor
POST   /api/desk/social/drafts/{draft_id}/approve
POST   /api/desk/social/drafts/{draft_id}/reject
POST   /api/desk/social/drafts/{draft_id}/skip
GET    /api/desk/social/drafts/{draft_id}/bundle.zip — PNGs + caption .txt files (+ meta.json)
POST   /api/desk/social/drafts/{draft_id}/mark-posted — phase 1 hand-off
GET    /api/desk/social/drafts/{draft_id}/slides/{slide_no}.png — preview slide
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBasicCredentials

from desk_ops_api import _basic, _creds_from_env, _gate  # auth re-use

log = logging.getLogger("desk_social_api")

router = APIRouter(prefix="/api/desk/social", tags=["desk-social"])


# ── Paths ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_DB     = _PROJECT_ROOT / "desk" / "data" / "social.db"
_DEFAULT_ASSETS = _PROJECT_ROOT / "desk" / "data" / "social_assets"


def _db_path() -> Path:
    env = os.getenv("DESK_SOCIAL_DB_PATH")
    return Path(env) if env else _DEFAULT_DB


def _assets_dir() -> Path:
    env = os.getenv("DESK_SOCIAL_ASSETS_DIR")
    return Path(env) if env else _DEFAULT_ASSETS


# ── Auth (re-use ops creds) ───────────────────────────────────────────
# We import `_gate` from desk_ops_api — same Basic-auth gate, same
# 404-when-unconfigured semantics, so the social surface inherits the
# "ops creds or nothing" posture.


def _username_or_none(credentials: HTTPBasicCredentials | None) -> Optional[str]:
    """Best-effort username extraction for audit logging. We never trust
    this for auth — that's done by `_gate`."""
    if credentials is None:
        return None
    return credentials.username


# ── DB helpers ────────────────────────────────────────────────────────


def _open_readonly() -> Optional[sqlite3.Connection]:
    p = _db_path()
    if not p.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=2.0)
    except sqlite3.Error as e:
        log.warning("social db open (ro) failed: %s", e)
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _open_readwrite() -> sqlite3.Connection:
    p = _db_path()
    if not p.is_file():
        # When the file's missing entirely we surface 404 — no queue at
        # all is functionally equivalent to "no such draft".
        raise HTTPException(status_code=404, detail="no social queue")
    conn = sqlite3.connect(str(p), isolation_level=None, timeout=2.0)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema mirrors (kept in sync by hand with desk/desk/social/queue.py) ─


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending":        {"approved", "rejected", "skipped"},
    "approved":       {"published", "publish_failed"},
    "publish_failed": {"approved", "published"},
}


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _row_to_summary(r: sqlite3.Row, *, costs_join: Optional[dict] = None) -> dict[str, Any]:
    return {
        "draft_id":        r["draft_id"],
        "kind":            r["kind"],
        "match_id":        r["match_id"],
        "week_starting":   r["week_starting"],
        "status":          r["status"],
        "created_at":      r["created_at"],
        "decided_at":      r["decided_at"],
        "decided_by":      r["decided_by"],
        "ig_permalink":    r["ig_permalink"],
        "x_tweet_id":      r["x_tweet_id"],
        "published_at":    r["published_at"],
        "publish_error":   r["publish_error"],
    }


def _row_to_detail(r: sqlite3.Row) -> dict[str, Any]:
    summary = _row_to_summary(r)
    summary["source_json"]  = json.loads(r["source_json"])
    summary["slides"]       = json.loads(r["slides_json"])
    summary["caption_ig"]   = r["caption_ig"]
    summary["caption_x"]    = r["caption_x"]
    summary["edit_history"] = json.loads(r["edit_history_json"] or "[]")
    return summary


# ── Routes (read) ─────────────────────────────────────────────────────


@router.get("/drafts", dependencies=[Depends(_gate)])
def list_drafts(
    status: Optional[str] = Query(default=None),
    kind:   Optional[str] = Query(default=None),
    limit:  int = Query(default=100, ge=1, le=500),
) -> dict:
    conn = _open_readonly()
    if conn is None:
        return {"drafts": []}
    try:
        sql = "SELECT * FROM social_drafts"
        where: list[str] = []
        args: list[Any] = []
        if status:
            where.append("status = ?")
            args.append(status)
        if kind:
            where.append("kind = ?")
            args.append(kind)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(int(limit))
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return {"drafts": [_row_to_summary(r) for r in rows]}


@router.get("/drafts/{draft_id}", dependencies=[Depends(_gate)])
def get_draft(draft_id: str) -> dict:
    conn = _open_readonly()
    if conn is None:
        raise HTTPException(status_code=404, detail="no such draft")
    try:
        row = conn.execute(
            "SELECT * FROM social_drafts WHERE draft_id = ?", (draft_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="no such draft")
    return _row_to_detail(row)


@router.get(
    "/drafts/{draft_id}/slides/{slide_no}.png",
    dependencies=[Depends(_gate)],
)
def get_slide(draft_id: str, slide_no: int) -> FileResponse:
    if not (1 <= slide_no <= 4):
        raise HTTPException(status_code=400, detail="slide_no must be 1..4")
    detail = get_draft(draft_id)
    matched = [s for s in detail["slides"] if int(s["slide_no"]) == slide_no]
    if not matched:
        raise HTTPException(status_code=404, detail="slide not found")
    path = Path(matched[0]["png_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="slide file missing")
    return FileResponse(path, media_type="image/png")


@router.get(
    "/drafts/{draft_id}/bundle.zip",
    dependencies=[Depends(_gate)],
)
def get_bundle(draft_id: str) -> Response:
    detail = get_draft(draft_id)
    if detail["status"] not in {"approved", "published", "publish_failed"}:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "invalid_state",
                "from":  detail["status"],
                "to":    "bundle",
            },
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in detail["slides"]:
            png_path = Path(s["png_path"])
            if not png_path.is_file():
                raise HTTPException(
                    status_code=500,
                    detail=f"slide {s['slide_no']} missing on disk",
                )
            bytes_ = png_path.read_bytes()
            sha = hashlib.sha256(bytes_).hexdigest()
            if sha != s["png_sha256"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"slide {s['slide_no']} sha256 mismatch — disk corrupt",
                )
            zf.writestr(f"slide-{int(s['slide_no'])}.png", bytes_)
        zf.writestr("caption-ig.txt", detail["caption_ig"])
        zf.writestr("caption-x.txt",  detail["caption_x"])
        zf.writestr("meta.json", json.dumps(
            {
                "draft_id":      detail["draft_id"],
                "kind":          detail["kind"],
                "match_id":      detail["match_id"],
                "week_starting": detail["week_starting"],
                "created_at":    detail["created_at"],
                "decided_at":    detail["decided_at"],
                "decided_by":    detail["decided_by"],
            },
            indent=2,
        ))
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{draft_id}-bundle.zip"',
        },
    )


# ── Routes (write) ────────────────────────────────────────────────────


def _transition_or_409(
    *, draft_id: str, to: str,
    by: Optional[str],
    publish_error: Optional[str] = None,
    ig_permalink: Optional[str] = None,
    x_tweet_id: Optional[str] = None,
) -> dict:
    conn = _open_readwrite()
    try:
        row = conn.execute(
            "SELECT status FROM social_drafts WHERE draft_id = ?", (draft_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="no such draft")
        current = row["status"]
        if to not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise HTTPException(
                status_code=409,
                detail={"error": "invalid_state", "from": current, "to": to},
            )
        now_iso = _now_iso()
        sets = ["status = ?", "decided_at = ?", "decided_by = ?"]
        args: list[Any] = [to, now_iso, by]
        if to == "published":
            sets.append("published_at = ?")
            args.append(now_iso)
            if ig_permalink:
                sets.append("ig_permalink = ?")
                args.append(ig_permalink)
            if x_tweet_id:
                sets.append("x_tweet_id = ?")
                args.append(x_tweet_id)
            sets.append("publish_error = NULL")
        elif to == "publish_failed":
            sets.append("publish_error = ?")
            args.append(publish_error or "publish failed")
        args.append(draft_id)
        conn.execute(
            f"UPDATE social_drafts SET {', '.join(sets)} WHERE draft_id = ?",
            args,
        )
        row = conn.execute(
            "SELECT * FROM social_drafts WHERE draft_id = ?", (draft_id,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_detail(row)


@router.post("/drafts/{draft_id}/approve", dependencies=[Depends(_gate)])
def approve(
    draft_id: str,
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> dict:
    return _transition_or_409(
        draft_id=draft_id, to="approved",
        by=_username_or_none(credentials),
    )


@router.post("/drafts/{draft_id}/reject", dependencies=[Depends(_gate)])
def reject(
    draft_id: str,
    payload: dict = Body(default_factory=dict),
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> dict:
    _ = payload.get("reason")  # accepted but not persisted in v0.1
    return _transition_or_409(
        draft_id=draft_id, to="rejected",
        by=_username_or_none(credentials),
    )


@router.post("/drafts/{draft_id}/skip", dependencies=[Depends(_gate)])
def skip(
    draft_id: str,
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> dict:
    return _transition_or_409(
        draft_id=draft_id, to="skipped",
        by=_username_or_none(credentials),
    )


@router.post("/drafts/{draft_id}/mark-posted", dependencies=[Depends(_gate)])
def mark_posted(
    draft_id: str,
    payload: dict = Body(default_factory=dict),
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> dict:
    """Phase 1 hand-off: operator posted manually and is reporting back.

    Accepts optional `ig_permalink` + `x_tweet_id` strings. Transitions
    approved → published.
    """
    return _transition_or_409(
        draft_id=draft_id, to="published",
        by=_username_or_none(credentials),
        ig_permalink=(payload.get("ig_permalink") or None),
        x_tweet_id=(payload.get("x_tweet_id") or None),
    )


@router.post("/drafts/{draft_id}/edit-caption", dependencies=[Depends(_gate)])
def edit_caption(
    draft_id: str,
    payload: dict = Body(default_factory=dict),
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> dict:
    platform = (payload.get("platform") or "").strip().lower()
    text     = payload.get("text")
    if platform not in ("ig", "x"):
        raise HTTPException(status_code=400, detail="platform must be 'ig' or 'x'")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="text must be a non-empty string")

    conn = _open_readwrite()
    try:
        row = conn.execute(
            "SELECT * FROM social_drafts WHERE draft_id = ?", (draft_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="no such draft")
        if row["status"] in {"published", "rejected", "skipped"}:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "invalid_state",
                    "from":  row["status"],
                    "to":    "edit",
                },
            )
        column = "caption_ig" if platform == "ig" else "caption_x"
        before = row[column]
        history = json.loads(row["edit_history_json"] or "[]")
        history.append({
            "at":     _now_iso(),
            "by":     _username_or_none(credentials),
            "field":  column,
            "before": before,
            "after":  text,
        })
        conn.execute(
            f"UPDATE social_drafts SET {column} = ?, edit_history_json = ? "
            "WHERE draft_id = ?",
            (text, json.dumps(history, separators=(",", ":")), draft_id),
        )
        row = conn.execute(
            "SELECT * FROM social_drafts WHERE draft_id = ?", (draft_id,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_detail(row)
