"""SQLite-backed draft queue.

Sync stdlib sqlite3 for the same reasons as `desk.distribute.outbox` —
operations are sub-millisecond and called from request handlers that
already block on disk I/O. async buys nothing here and adds a dep.

Idempotency: two partial-unique indexes prevent double-drafts on the
same surface — one per match_id (kind=daily), one per week_starting
(kind=weekly_roundup). The selector relies on this: it asks the queue
whether a draft exists before paying the cost of rendering one.

State transitions are enforced by `desk.social.models.can_transition`.
The queue raises `InvalidTransition` on a bad move so the router can
turn that into a typed 409 with `{from, to}`.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from desk.social.models import (
    ALLOWED_TRANSITIONS,
    DraftKind,
    DraftStatus,
    SlideAsset,
)

SCHEMA_VERSION = 1


_SCHEMA = """
CREATE TABLE IF NOT EXISTS social_drafts (
    draft_id          TEXT PRIMARY KEY,
    kind              TEXT NOT NULL,
    match_id          TEXT,
    week_starting     TEXT,

    source_json       TEXT NOT NULL,

    slides_json       TEXT NOT NULL,
    caption_ig        TEXT NOT NULL,
    caption_x         TEXT NOT NULL,

    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    decided_at        TEXT,
    decided_by        TEXT,
    edit_history_json TEXT,

    ig_permalink      TEXT,
    x_tweet_id        TEXT,
    published_at      TEXT,
    publish_error     TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_daily
    ON social_drafts(match_id) WHERE kind = 'daily';

CREATE UNIQUE INDEX IF NOT EXISTS uq_weekly
    ON social_drafts(week_starting) WHERE kind = 'weekly_roundup';

CREATE INDEX IF NOT EXISTS ix_status
    ON social_drafts(status, created_at DESC);
"""


class InvalidTransition(ValueError):
    """`current_status → new_status` is not in ALLOWED_TRANSITIONS."""

    def __init__(self, draft_id: str, frm: DraftStatus, to: DraftStatus):
        super().__init__(
            f"draft {draft_id}: invalid transition {frm.value} → {to.value}",
        )
        self.draft_id = draft_id
        self.from_status = frm
        self.to_status   = to


class DraftNotFound(LookupError):
    pass


@dataclass(frozen=True)
class Draft:
    draft_id:        str
    kind:            DraftKind
    match_id:        Optional[str]
    week_starting:   Optional[str]
    source_json:     dict
    slides:          list[SlideAsset]
    caption_ig:      str
    caption_x:       str
    status:          DraftStatus
    created_at:      str
    decided_at:      Optional[str]
    decided_by:      Optional[str]
    edit_history:    list[dict] = field(default_factory=list)
    ig_permalink:    Optional[str] = None
    x_tweet_id:      Optional[str] = None
    published_at:    Optional[str] = None
    publish_error:   Optional[str] = None


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _slides_to_json(slides: list[SlideAsset]) -> str:
    return json.dumps(
        [
            {
                "slide_no":   s.slide_no,
                "png_path":   str(s.png_path),
                "png_sha256": s.png_sha256,
            }
            for s in slides
        ],
        separators=(",", ":"),
    )


def _slides_from_json(raw: str) -> list[SlideAsset]:
    return [
        SlideAsset(
            slide_no=int(r["slide_no"]),
            png_path=Path(r["png_path"]),
            png_sha256=r["png_sha256"],
        )
        for r in json.loads(raw)
    ]


def _row_to_draft(row: sqlite3.Row) -> Draft:
    return Draft(
        draft_id      = row["draft_id"],
        kind          = DraftKind(row["kind"]),
        match_id      = row["match_id"],
        week_starting = row["week_starting"],
        source_json   = json.loads(row["source_json"]),
        slides        = _slides_from_json(row["slides_json"]),
        caption_ig    = row["caption_ig"],
        caption_x     = row["caption_x"],
        status        = DraftStatus(row["status"]),
        created_at    = row["created_at"],
        decided_at    = row["decided_at"],
        decided_by    = row["decided_by"],
        edit_history  = json.loads(row["edit_history_json"] or "[]"),
        ig_permalink  = row["ig_permalink"],
        x_tweet_id    = row["x_tweet_id"],
        published_at  = row["published_at"],
        publish_error = row["publish_error"],
    )


class SocialQueue:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cur = self._conn.execute("PRAGMA user_version").fetchone()
        existing = cur[0] if cur else 0
        if existing == SCHEMA_VERSION:
            return
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SocialQueue":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── reads ──────────────────────────────────────────────────────────

    def get(self, draft_id: str) -> Optional[Draft]:
        row = self._conn.execute(
            "SELECT * FROM social_drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        return _row_to_draft(row) if row else None

    def get_or_raise(self, draft_id: str) -> Draft:
        d = self.get(draft_id)
        if d is None:
            raise DraftNotFound(draft_id)
        return d

    def has_daily_for_match(self, match_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM social_drafts WHERE kind = 'daily' AND match_id = ?",
            (match_id,),
        ).fetchone()
        return row is not None

    def has_weekly_for(self, week_starting: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM social_drafts WHERE kind = 'weekly_roundup' "
            "AND week_starting = ?",
            (week_starting,),
        ).fetchone()
        return row is not None

    def list_by_status(
        self, *, status: Optional[DraftStatus] = None,
        kind: Optional[DraftKind] = None,
        limit: int = 100,
    ) -> list[Draft]:
        where: list[str] = []
        args:  list[Any] = []
        if status is not None:
            where.append("status = ?")
            args.append(status.value)
        if kind is not None:
            where.append("kind = ?")
            args.append(kind.value)
        sql = "SELECT * FROM social_drafts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(int(limit))
        return [_row_to_draft(r) for r in self._conn.execute(sql, args).fetchall()]

    def list_recent(self, *, limit: int = 100) -> list[Draft]:
        return self.list_by_status(limit=limit)

    # ── inserts ────────────────────────────────────────────────────────

    def insert(
        self, *,
        draft_id:      str,
        kind:          DraftKind,
        match_id:      Optional[str],
        week_starting: Optional[str],
        source_json:   dict,
        slides:        list[SlideAsset],
        caption_ig:    str,
        caption_x:     str,
        now:           Optional[str] = None,
    ) -> Draft:
        if kind == DraftKind.DAILY and not match_id:
            raise ValueError("daily drafts require match_id")
        if kind == DraftKind.WEEKLY_ROUNDUP and not week_starting:
            raise ValueError("weekly_roundup drafts require week_starting")
        if len(slides) != 4:
            raise ValueError(f"expected 4 slides, got {len(slides)}")
        now_iso = now or _now_iso()
        self._conn.execute(
            "INSERT INTO social_drafts ("
            "draft_id, kind, match_id, week_starting, "
            "source_json, slides_json, caption_ig, caption_x, "
            "status, created_at, edit_history_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, '[]')",
            (
                draft_id, kind.value, match_id, week_starting,
                json.dumps(source_json, separators=(",", ":")),
                _slides_to_json(slides),
                caption_ig, caption_x,
                now_iso,
            ),
        )
        return self.get_or_raise(draft_id)

    # ── transitions ────────────────────────────────────────────────────

    def transition(
        self, draft_id: str, *,
        to: DraftStatus,
        by: Optional[str] = None,
        publish_error: Optional[str] = None,
        ig_permalink: Optional[str] = None,
        x_tweet_id: Optional[str] = None,
    ) -> Draft:
        d = self.get_or_raise(draft_id)
        if to not in ALLOWED_TRANSITIONS.get(d.status, frozenset()):
            raise InvalidTransition(draft_id, d.status, to)
        now_iso = _now_iso()
        sets = ["status = ?", "decided_at = ?", "decided_by = ?"]
        args: list[Any] = [to.value, now_iso, by]
        if to == DraftStatus.PUBLISHED:
            sets.append("published_at = ?")
            args.append(now_iso)
            if ig_permalink is not None:
                sets.append("ig_permalink = ?")
                args.append(ig_permalink)
            if x_tweet_id is not None:
                sets.append("x_tweet_id = ?")
                args.append(x_tweet_id)
            # Successful publish clears any previous failure context.
            sets.append("publish_error = NULL")
        elif to == DraftStatus.PUBLISH_FAILED:
            sets.append("publish_error = ?")
            args.append(publish_error or "publish failed")
        args.append(draft_id)
        self._conn.execute(
            f"UPDATE social_drafts SET {', '.join(sets)} WHERE draft_id = ?",
            args,
        )
        return self.get_or_raise(draft_id)

    # ── caption edits ──────────────────────────────────────────────────

    def edit_caption(
        self, draft_id: str, *,
        platform: str,            # "ig" | "x"
        new_text: str,
        by: Optional[str] = None,
    ) -> Draft:
        if platform not in ("ig", "x"):
            raise ValueError(f"platform must be 'ig' or 'x', got {platform!r}")
        d = self.get_or_raise(draft_id)
        if d.status in {DraftStatus.PUBLISHED, DraftStatus.REJECTED,
                        DraftStatus.SKIPPED}:
            raise InvalidTransition(draft_id, d.status, d.status)
        column = "caption_ig" if platform == "ig" else "caption_x"
        before = d.caption_ig if platform == "ig" else d.caption_x
        history = list(d.edit_history)
        history.append({
            "at":       _now_iso(),
            "by":       by,
            "field":    column,
            "before":   before,
            "after":    new_text,
        })
        self._conn.execute(
            f"UPDATE social_drafts SET {column} = ?, edit_history_json = ? "
            "WHERE draft_id = ?",
            (new_text, json.dumps(history, separators=(",", ":")), draft_id),
        )
        return self.get_or_raise(draft_id)
