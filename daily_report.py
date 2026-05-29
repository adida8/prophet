"""Odds Primer — Daily Report.

Builds a one-page HTML + PDF brief covering the previous UTC day's
audience activity (views, votes, CTA clicks, sentiment) and the latest
Desk pipeline tick (verdicts published, cost, errors), then emails it to
the configured recipients via SMTP.

Reads:
  - Railway Postgres (activity tables: match_views / match_reactions /
    match_aggregates / cta_clicks) — all queries filter `seeded = false`
    so seed traffic never appears in the report.
  - desk/data/output/football/{id}.json — to label the top-N matches.
  - {DESK_OPS_DIR}/runs/*.json  — latest RunReport for desk health.
  - {DESK_OPS_DIR}/tick-totals.jsonl — per-run cost row.

Writes:
  - {ops_root}/daily_report/last_sent.json — idempotency marker; one
    send per report_date (override with --force).

Run:
  python daily_report.py --once --dry-run                # local smoke
  python daily_report.py --once                          # send for yesterday
  python daily_report.py --once --date 2026-05-28        # send a specific day
  python daily_report.py --once --force                  # bypass already-sent

Wired into the asyncio app via daily_report_loop.py (hourly tick, fires
at DAILY_REPORT_HOUR UTC).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import smtplib
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("daily_report")

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
DESK_OUTPUT_FOOTBALL = ROOT / "desk" / "data" / "output" / "football"


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Config:
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    mail_from: str
    mail_to: tuple[str, ...]
    daily_report_hour: int
    env_label: str
    ops_root: Path
    desk_output_dir: Path
    database_url: Optional[str]
    starttls: bool = True

    @property
    def state_path(self) -> Path:
        return self.ops_root / "daily_report" / "last_sent.json"


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if v is not None else default


def _resolve_ops_root() -> Path:
    """Mirror desk/desk/ops/cost.py:_ops_root resolution."""
    ops_dir_env = _env("DESK_OPS_DIR")
    if ops_dir_env:
        return Path(ops_dir_env)
    out_env = _env("DESK_OUTPUT_DIR")
    if out_env:
        return Path(out_env) / "ops"
    return ROOT / "desk" / "data" / "output" / "ops"


def load_config() -> Config:
    """Read env vars + fail loud on missing-required when enabled.

    DAILY_REPORT_ENABLED gates everything. When 0 (default), missing
    SMTP / recipient config is allowed so a fresh deploy doesn't break.
    When 1, every required field must be set or this raises.
    """
    enabled = _env("DAILY_REPORT_ENABLED", "0") in {"1", "true", "yes", "on"}

    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    mail_from = _env("DAILY_REPORT_FROM") or smtp_user
    mail_to_raw = _env("DAILY_REPORT_TO")
    mail_to = tuple(addr.strip() for addr in mail_to_raw.split(",") if addr.strip())
    hour = int(_env("DAILY_REPORT_HOUR", "8") or "8")
    env_label = _env("DAILY_REPORT_ENV", "staging") or "staging"
    database_url = _env("DATABASE_URL") or None

    if enabled:
        missing = []
        if not smtp_host: missing.append("SMTP_HOST")
        if not smtp_user: missing.append("SMTP_USER")
        if not smtp_pass: missing.append("SMTP_PASS")
        if not mail_from: missing.append("DAILY_REPORT_FROM (or SMTP_USER)")
        if not mail_to:   missing.append("DAILY_REPORT_TO")
        if missing:
            raise RuntimeError(
                "daily report enabled but missing required env: "
                + ", ".join(missing)
            )

    return Config(
        enabled=enabled,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        mail_from=mail_from,
        mail_to=mail_to,
        daily_report_hour=hour,
        env_label=env_label,
        ops_root=_resolve_ops_root(),
        desk_output_dir=ROOT / (_env("DESK_OUTPUT_DIR") or "desk/data/output"),
        database_url=database_url,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Window math
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Window:
    start: datetime  # inclusive (UTC midnight)
    end:   datetime  # exclusive (next UTC midnight)
    label_date: date  # the day the report covers

    @property
    def prior(self) -> "Window":
        prior_date = self.label_date - timedelta(days=1)
        return window_for(prior_date)


def window_for(report_date: date) -> Window:
    start = datetime.combine(report_date, time(0, 0, 0), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return Window(start=start, end=end, label_date=report_date)


def yesterday_utc(now: Optional[datetime] = None) -> date:
    now = now or datetime.now(timezone.utc)
    return (now.date() - timedelta(days=1))


# ─────────────────────────────────────────────────────────────────────────────
# Async query helpers
# ─────────────────────────────────────────────────────────────────────────────
#
# Each helper takes a conn (asyncpg connection) + window. All queries filter
# `seeded = false`. The CTA helpers wrap in try/except so a missing
# cta_clicks table (pre-migration) just returns zero counts.


async def q_views(conn: Any, w: Window) -> int:
    return int(await conn.fetchval(
        "SELECT count(*) FROM match_views "
        "WHERE seeded = false AND viewed_at >= $1 AND viewed_at < $2",
        w.start, w.end,
    ) or 0)


async def q_unique_anons(conn: Any, w: Window) -> int:
    return int(await conn.fetchval(
        "SELECT count(DISTINCT anon_id) FROM match_views "
        "WHERE seeded = false AND viewed_at >= $1 AND viewed_at < $2",
        w.start, w.end,
    ) or 0)


async def q_votes(conn: Any, w: Window) -> int:
    return int(await conn.fetchval(
        "SELECT count(*) FROM match_reactions "
        "WHERE seeded = false AND voted_at >= $1 AND voted_at < $2",
        w.start, w.end,
    ) or 0)


async def q_new_vs_returning(conn: Any, w: Window) -> tuple[int, int]:
    """Returns (new_count, returning_count). A reader is 'new' if their
    first ever view (any time) falls inside the window. Else returning.
    """
    rows = await conn.fetch(
        "SELECT anon_id, MIN(viewed_at) AS first_seen "
        "FROM match_views WHERE seeded = false GROUP BY anon_id "
        "HAVING MAX(viewed_at) >= $1 AND MIN(viewed_at) < $2",
        w.start, w.end,
    )
    new_ct = 0
    ret_ct = 0
    for r in rows:
        fs = r["first_seen"]
        if fs >= w.start and fs < w.end:
            new_ct += 1
        else:
            ret_ct += 1
    return new_ct, ret_ct


async def q_busiest_hour(conn: Any, w: Window) -> Optional[int]:
    row = await conn.fetchrow(
        "SELECT EXTRACT(HOUR FROM viewed_at)::int AS h, count(*) AS n "
        "FROM match_views "
        "WHERE seeded = false AND viewed_at >= $1 AND viewed_at < $2 "
        "GROUP BY h ORDER BY n DESC LIMIT 1",
        w.start, w.end,
    )
    if row is None:
        return None
    return int(row["h"])


async def q_cta_total(conn: Any, w: Window) -> int:
    try:
        return int(await conn.fetchval(
            "SELECT count(*) FROM cta_clicks "
            "WHERE seeded = false AND clicked_at >= $1 AND clicked_at < $2",
            w.start, w.end,
        ) or 0)
    except Exception:  # noqa: BLE001
        # Migration not yet applied — treat as zero so the first send works.
        return 0


async def q_cta_by_venue(conn: Any, w: Window) -> dict[str, int]:
    out = {"polymarket": 0, "kalshi": 0}
    try:
        rows = await conn.fetch(
            "SELECT venue, count(*) AS n FROM cta_clicks "
            "WHERE seeded = false AND clicked_at >= $1 AND clicked_at < $2 "
            "GROUP BY venue",
            w.start, w.end,
        )
        for r in rows:
            out[str(r["venue"])] = int(r["n"])
    except Exception:  # noqa: BLE001
        pass
    return out


async def q_reactions_breakdown(conn: Any, w: Window) -> dict[str, int]:
    rows = await conn.fetch(
        "SELECT reaction, count(*) AS n FROM match_reactions "
        "WHERE seeded = false AND voted_at >= $1 AND voted_at < $2 "
        "GROUP BY reaction",
        w.start, w.end,
    )
    out = {"sharp_call": 0, "fair_call": 0, "off_mark": 0, "wait_see": 0}
    for r in rows:
        out[str(r["reaction"])] = int(r["n"])
    return out


async def q_top_matches(conn: Any, w: Window, limit: int = 5) -> list[dict]:
    """Top-N matches by views inside the window. Each row carries views,
    votes (lifetime, not windowed — reactions are sparse), and aligned_pct
    from match_aggregates when present."""
    rows = await conn.fetch(
        "SELECT match_id, count(*) AS views FROM match_views "
        "WHERE seeded = false AND viewed_at >= $1 AND viewed_at < $2 "
        "GROUP BY match_id ORDER BY views DESC LIMIT $3",
        w.start, w.end, limit,
    )
    out: list[dict] = []
    for r in rows:
        mid = str(r["match_id"])
        agg = await conn.fetchrow(
            "SELECT votes_total, aligned_pct FROM match_aggregates "
            "WHERE match_id = $1",
            mid,
        )
        out.append({
            "match_id": mid,
            "views": int(r["views"]),
            "votes": int(agg["votes_total"]) if agg else 0,
            "aligned_pct": int(agg["aligned_pct"]) if agg and agg["aligned_pct"] is not None else None,
        })
    return out


async def q_zero_click_picks(
    conn: Any, w: Window, pick_match_ids: set[str], limit: int = 5,
) -> list[str]:
    """Match ids that are live Picks AND had ≥1 view yesterday AND zero
    CTA clicks. Sorted by views desc."""
    if not pick_match_ids:
        return []
    try:
        rows = await conn.fetch(
            "SELECT v.match_id, count(*) AS views "
            "FROM match_views v "
            "WHERE v.seeded = false AND v.viewed_at >= $1 AND v.viewed_at < $2 "
            "  AND v.match_id = ANY($3::text[]) "
            "  AND NOT EXISTS ( "
            "    SELECT 1 FROM cta_clicks c "
            "    WHERE c.match_id = v.match_id "
            "      AND c.seeded = false "
            "      AND c.clicked_at >= $1 AND c.clicked_at < $2 "
            "  ) "
            "GROUP BY v.match_id ORDER BY views DESC LIMIT $4",
            w.start, w.end, list(pick_match_ids), limit,
        )
    except Exception:  # noqa: BLE001
        # No cta_clicks table yet — every viewed pick is "zero-click".
        rows = await conn.fetch(
            "SELECT match_id, count(*) AS views FROM match_views "
            "WHERE seeded = false AND viewed_at >= $1 AND viewed_at < $2 "
            "  AND match_id = ANY($3::text[]) "
            "GROUP BY match_id ORDER BY views DESC LIMIT $4",
            w.start, w.end, list(pick_match_ids), limit,
        )
    return [str(r["match_id"]) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Enrichment readers (desk match JSON, ops RunReport, tick-totals)
# ─────────────────────────────────────────────────────────────────────────────


def resolve_match_label(match_id: str, *, root: Optional[Path] = None) -> dict:
    """Read desk/data/output/football/{match_id}.json and return display
    metadata. Falls back to a derived label when the file is missing."""
    root = root or DESK_OUTPUT_FOOTBALL
    path = root / f"{match_id}.json"
    if not path.exists():
        return {
            "label": match_id,
            "verdict_state": "unknown",
            "verdict_label": "—",
            "edge_pp": None,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "label": match_id,
            "verdict_state": "unknown",
            "verdict_label": "—",
            "edge_pp": None,
        }
    team_a = data.get("team_a") or "?"
    team_b = data.get("team_b") or "?"
    v = data.get("verdict") or {}
    state = (v.get("state") or "unknown").lower()
    side = v.get("side")
    edge_pp = v.get("edge_pp")
    if state == "pick" and side:
        verdict_label = f"Pick · {side}"
    elif state == "pass":
        verdict_label = "Pass"
    elif state == "avoid":
        verdict_label = "Avoid"
    else:
        verdict_label = "—"
    return {
        "label": f"{team_a} vs {team_b}",
        "verdict_state": state,
        "verdict_label": verdict_label,
        "edge_pp": float(edge_pp) if edge_pp is not None else None,
    }


def list_live_pick_match_ids(*, root: Optional[Path] = None) -> set[str]:
    """Set of match_ids whose published JSON carries verdict.state == 'pick'."""
    root = root or DESK_OUTPUT_FOOTBALL
    if not root.exists():
        return set()
    out: set[str] = set()
    for p in root.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        v = data.get("verdict") or {}
        if (v.get("state") or "").lower() == "pick":
            mid = data.get("match_id") or p.stem
            out.add(str(mid))
    return out


def read_latest_run_report(*, ops_root: Optional[Path] = None) -> Optional[dict]:
    """Read the most-recent {ops_root}/runs/*.json by mtime. Returns the
    parsed dict, or None when there are no runs yet."""
    ops_root = ops_root or _resolve_ops_root()
    runs_dir = ops_root / "runs"
    if not runs_dir.exists():
        return None
    candidates = sorted(runs_dir.glob("run-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    try:
        return json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_tick_total_for(run_id: str, *, ops_root: Optional[Path] = None) -> Optional[dict]:
    """Find the tick-totals row whose run_id matches. Tail-scans the
    jsonl — file is small (one row per tick, ops dashboard retention)."""
    ops_root = ops_root or _resolve_ops_root()
    path = ops_root / "tick-totals.jsonl"
    if not path.exists():
        return None
    matched: Optional[dict] = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("run_id") == run_id:
                    matched = row
    except OSError:
        return None
    return matched


# ─────────────────────────────────────────────────────────────────────────────
# Context builder + status line
# ─────────────────────────────────────────────────────────────────────────────


def _delta_label(curr: int, prev: int) -> tuple[str, str]:
    """Returns ('▲ +N%', 'up') | ('▼ -N%', 'down') | ('flat vs yesterday', '')."""
    if prev <= 0:
        if curr > 0:
            return ("▲ new vs yesterday", "up")
        return ("flat vs yesterday", "")
    delta = curr - prev
    pct = round(delta / prev * 100)
    if pct > 0:
        return (f"▲ +{pct}% vs yesterday", "up")
    if pct < 0:
        return (f"▼ {pct}% vs yesterday", "down")
    return ("flat vs yesterday", "")


def status_line(*, views: int, votes: int, cta_total: int, desk_status: str) -> dict:
    """Compose the one-line top-of-report banner."""
    if desk_status == "fail":
        return {
            "color": "red",
            "label": "Pipeline failed",
            "line": "The Desk's last tick failed. Verdicts may be stale — investigate before reading further.",
        }
    if views == 0 and votes == 0 and cta_total == 0:
        return {
            "color": "amber",
            "label": "Quiet day",
            "line": "No reader activity recorded yesterday. Either traffic was zero or the activity logger wasn't running.",
        }
    if views < 25:
        return {
            "color": "amber",
            "label": "Low traffic",
            "line": f"{views} views, {votes} votes, {cta_total} CTA clicks. Under launch-rate floor.",
        }
    return {
        "color": "green",
        "label": "Healthy",
        "line": f"{views} views, {votes} votes, {cta_total} CTA clicks. Pipeline {desk_status}.",
    }


def _venue_label(venue: str) -> str:
    return {"polymarket": "Polymarket", "kalshi": "Kalshi"}.get(venue, venue)


def _hour_label(h: Optional[int]) -> str:
    if h is None:
        return "—"
    return f"{h:02d}:00–{(h+1) % 24:02d}:00"


CHIP_META: list[dict[str, Any]] = [
    {"key": "sharp_call", "emoji": "🐂", "label": "Bullish",    "positive": True},
    {"key": "fair_call",  "emoji": "💎", "label": "Value",      "positive": True},
    {"key": "wait_see",   "emoji": "💸", "label": "Overpriced", "positive": False},
    {"key": "off_mark",   "emoji": "🪤", "label": "Trap line",  "positive": False},
]


def build_sentiment(reactions: dict[str, int]) -> dict:
    total = sum(reactions.values())
    rows: list[dict] = []
    for meta in CHIP_META:
        n = int(reactions.get(meta["key"], 0))
        pct = round(n / total * 100) if total else 0
        rows.append({
            "label": meta["label"],
            "emoji": meta["emoji"],
            "positive": meta["positive"],
            "count": n,
            "pct": pct,
        })
    aligned = reactions.get("sharp_call", 0) + reactions.get("fair_call", 0)
    aligned_pct = round(aligned / total * 100) if total else 0
    return {"total": total, "rows": rows, "aligned_pct": aligned_pct}


def build_funnel(views: int, votes: int, cta_total: int) -> dict:
    """Audience funnel — Views → Voters → CTA clicks. Bars sized vs top."""
    steps = [
        ("Match pages viewed", views),
        ("Voted on a match",   votes),
        ("Clicked a market CTA", cta_total),
    ]
    top = max((n for _, n in steps), default=0)
    rows = []
    for label, n in steps:
        pct = round(n / top * 100) if top else 0
        rows.append({"label": label, "value": n, "pct": pct})
    return {"rows": rows, "top": top}


def build_desk_section(report: Optional[dict], tick_total: Optional[dict]) -> dict:
    """Render-ready dict for the Desk health section."""
    out: dict[str, Any] = {
        "last_run_at": None,
        "last_run_status": None,
        "last_run_trigger": None,
        "last_run_duration": "—",
        "published": 0,
        "picks": 0,
        "passes": 0,
        "avoids": 0,
        "tick_usd": 0.0,
        "tick_calls": 0,
        "changes": 0,
        "funnel": [],
    }
    if report:
        out["last_run_at"]      = report.get("finished_at") or report.get("started_at")
        out["last_run_status"]  = report.get("status")
        out["last_run_trigger"] = report.get("trigger")
        dur = report.get("duration_s")
        if isinstance(dur, (int, float)):
            out["last_run_duration"] = f"{dur:.1f}s"
        funnel = report.get("funnel") or []
        out["funnel"] = funnel
        out["published"] = next(
            (int(s.get("n") or 0) for s in funnel if s.get("stage") == "published"), 0,
        )
        verdicts = report.get("verdicts") or {}
        out["picks"]  = int(verdicts.get("pick") or 0)
        # JSON dumps with by_alias=True writes `pass`; Pydantic field is `pass_`.
        out["passes"] = int(verdicts.get("pass") or verdicts.get("pass_") or 0)
        out["avoids"] = int(verdicts.get("avoid") or 0)
        out["changes"] = len(report.get("changes") or [])
    if tick_total:
        out["tick_usd"]   = float(tick_total.get("total_usd") or 0.0)
        out["tick_calls"] = int(tick_total.get("calls") or 0)
    return out


async def build_context(cfg: Config, conn: Any, w: Window) -> dict:
    # Audience numbers (current + prior window deltas).
    views_curr = await q_views(conn, w)
    views_prev = await q_views(conn, w.prior)
    uniques_curr = await q_unique_anons(conn, w)
    uniques_prev = await q_unique_anons(conn, w.prior)
    votes_curr = await q_votes(conn, w)
    votes_prev = await q_votes(conn, w.prior)
    cta_curr = await q_cta_total(conn, w)
    cta_prev = await q_cta_total(conn, w.prior)

    new_ct, ret_ct = await q_new_vs_returning(conn, w)
    nv_total = new_ct + ret_ct
    new_pct = round(new_ct / nv_total * 100) if nv_total else 0
    ret_pct = 100 - new_pct if nv_total else 0

    busiest_hour = await q_busiest_hour(conn, w)
    cta_by_venue_map = await q_cta_by_venue(conn, w)
    reactions = await q_reactions_breakdown(conn, w)
    top = await q_top_matches(conn, w, limit=5)

    pick_ids = list_live_pick_match_ids()
    zc_ids = await q_zero_click_picks(conn, w, pick_ids, limit=5)

    # Enrich top + zero-click picks with desk JSON labels.
    for m in top:
        m.update(resolve_match_label(m["match_id"]))
    zero_click_rows: list[dict] = []
    for mid in zc_ids:
        meta = resolve_match_label(mid)
        # Pull view count for the row.
        views = next((m["views"] for m in top if m["match_id"] == mid), 0)
        if not views:
            row = await conn.fetchrow(
                "SELECT count(*) AS n FROM match_views "
                "WHERE seeded = false AND match_id = $1 AND viewed_at >= $2 AND viewed_at < $3",
                mid, w.start, w.end,
            )
            views = int(row["n"]) if row else 0
        zero_click_rows.append({
            "match_id": mid,
            "label": meta["label"],
            "edge_pp": meta["edge_pp"],
            "views": views,
        })

    cta_by_venue = [
        {"venue": k, "label": _venue_label(k), "count": v}
        for k, v in cta_by_venue_map.items() if v
    ]
    cta_by_venue.sort(key=lambda r: r["count"], reverse=True)

    run = read_latest_run_report(ops_root=cfg.ops_root)
    tick_total = None
    if run and run.get("run_id"):
        tick_total = read_tick_total_for(run["run_id"], ops_root=cfg.ops_root)

    desk = build_desk_section(run, tick_total)
    sentiment = build_sentiment(reactions)
    funnel = build_funnel(views_curr, votes_curr, cta_curr)

    views_delta, views_cls       = _delta_label(views_curr, views_prev)
    uniques_delta, uniques_cls   = _delta_label(uniques_curr, uniques_prev)
    votes_delta, votes_cls       = _delta_label(votes_curr, votes_prev)
    cta_delta, cta_cls           = _delta_label(cta_curr, cta_prev)

    status = status_line(
        views=views_curr, votes=votes_curr, cta_total=cta_curr,
        desk_status=(desk["last_run_status"] or "unknown"),
    )

    return {
        "report_date":      w.label_date.isoformat(),
        "report_date_long": w.label_date.strftime("%A, %d %B %Y"),
        "env_label":        cfg.env_label,
        "generated_at":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window_start":     w.start.isoformat(),
        "window_end":       w.end.isoformat(),
        "status":           status,
        "kpi": {
            "views":              views_curr,
            "views_delta":        views_delta,
            "views_delta_cls":    views_cls,
            "uniques":            uniques_curr,
            "uniques_delta":      uniques_delta,
            "uniques_delta_cls":  uniques_cls,
            "votes":              votes_curr,
            "votes_delta":        votes_delta,
            "votes_delta_cls":    votes_cls,
            "cta_total":          cta_curr,
            "cta_delta":          cta_delta,
            "cta_delta_cls":      cta_cls,
        },
        "audience": {
            "new_pct":       new_pct,
            "returning_pct": ret_pct,
            "busiest_hour":  _hour_label(busiest_hour),
        },
        "cta_by_venue":     cta_by_venue,
        "top_matches":      top,
        "sentiment":        sentiment,
        "zero_click_picks": zero_click_rows,
        "funnel":           funnel,
        "desk":             desk,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────


def render_html(ctx: dict, *, template_dir: Optional[Path] = None) -> str:
    """Jinja2 render of templates/daily_report.html."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    td = template_dir or TEMPLATE_DIR
    env = Environment(
        loader=FileSystemLoader(str(td)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("daily_report.html")
    return tpl.render(**ctx)


def render_pdf(html: str) -> Optional[bytes]:
    """Render HTML → PDF bytes via WeasyPrint. Returns None on any failure
    so the email send path can fall back to HTML-only.
    """
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError as e:
        log.warning("WeasyPrint not installed (%s); sending HTML-only email", e)
        return None
    try:
        buf = io.BytesIO()
        HTML(string=html, base_url=str(ROOT)).write_pdf(buf)
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        log.warning("WeasyPrint render failed: %s; sending HTML-only email", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────────────────────────────────────


def build_email(
    cfg: Config, *, subject: str, html: str, pdf: Optional[bytes], report_date: date,
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = cfg.mail_from
    msg["To"]      = ", ".join(cfg.mail_to)
    msg.set_content(
        "Your email client did not render the HTML version. "
        "The PDF attachment carries the same content."
    )
    msg.add_alternative(html, subtype="html")
    if pdf:
        msg.add_attachment(
            pdf,
            maintype="application",
            subtype="pdf",
            filename=f"odds-primer-daily-{report_date.isoformat()}.pdf",
        )
    return msg


def send_email(cfg: Config, msg: EmailMessage) -> None:
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as s:
        s.ehlo()
        if cfg.starttls:
            s.starttls()
            s.ehlo()
        if cfg.smtp_user and cfg.smtp_pass:
            s.login(cfg.smtp_user, cfg.smtp_pass)
        s.send_message(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────────────


def _read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def already_sent(cfg: Config, report_date: date) -> bool:
    state = _read_state(cfg.state_path)
    return state.get("last_sent_date") == report_date.isoformat()


def mark_sent(cfg: Config, report_date: date) -> None:
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    state = _read_state(cfg.state_path)
    state["last_sent_date"] = report_date.isoformat()
    state["sent_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cfg.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def _open_pg_conn(database_url: str):
    """Lightweight single-connection context — the daily report runs
    once a day, so the activity-pool overhead is not worth it."""
    import asyncpg
    conn = await asyncpg.connect(dsn=database_url, timeout=5.0, command_timeout=15.0)
    try:
        yield conn
    finally:
        await conn.close()


async def run_once(
    cfg: Config,
    *,
    report_date: Optional[date] = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """One report send. Returns a small status dict.

    `force=True` bypasses the already_sent guard.
    `dry_run=True` renders HTML + builds the EmailMessage but does NOT send.
    """
    if not cfg.enabled:
        log.info("daily_report: DAILY_REPORT_ENABLED=0; skipping")
        return {"sent": False, "reason": "disabled"}

    rd = report_date or yesterday_utc()
    if (not force) and already_sent(cfg, rd):
        log.info("daily_report: already sent for %s; skipping", rd.isoformat())
        return {"sent": False, "reason": "already_sent", "report_date": rd.isoformat()}

    if not cfg.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. The daily report reads the activity "
            "tables; without Postgres there is nothing to send."
        )

    w = window_for(rd)
    log.info("daily_report: building for %s (%s → %s)", rd.isoformat(), w.start.isoformat(), w.end.isoformat())

    async with _open_pg_conn(cfg.database_url) as conn:
        ctx = await build_context(cfg, conn, w)

    html = render_html(ctx)
    pdf  = render_pdf(html)
    subject = f"Odds Primer — Daily Report ({rd.isoformat()})"
    msg = build_email(cfg, subject=subject, html=html, pdf=pdf, report_date=rd)

    if dry_run:
        log.info("daily_report: dry-run, not sending. html_bytes=%d pdf_bytes=%s",
                 len(html), len(pdf) if pdf else 0)
        return {"sent": False, "reason": "dry_run", "report_date": rd.isoformat(),
                "html_bytes": len(html), "pdf_bytes": len(pdf) if pdf else 0}

    send_email(cfg, msg)
    mark_sent(cfg, rd)
    log.info("daily_report: sent %s to %s", rd.isoformat(), ", ".join(cfg.mail_to))
    return {"sent": True, "report_date": rd.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Odds Primer — Daily Report")
    p.add_argument("--once", action="store_true", help="Run a single send and exit.")
    p.add_argument("--force", action="store_true", help="Bypass the already-sent guard.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="Build + render but do not send (no SMTP touch).")
    p.add_argument("--date", default=None,
                   help="Report date (YYYY-MM-DD). Defaults to yesterday UTC.")
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-18s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    args = _parse_args(argv)
    cfg = load_config()
    rd = date.fromisoformat(args.date) if args.date else None
    result = asyncio.run(run_once(cfg, report_date=rd, force=args.force, dry_run=args.dry_run))
    log.info("daily_report: result=%s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
