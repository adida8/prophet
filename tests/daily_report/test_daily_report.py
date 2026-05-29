"""Tests for the Odds Primer daily report.

Mocks the Postgres layer (a substring-matched fake `conn`), the SMTP
client (a captured-messages stand-in), and uses tmp_path fixtures for
the desk match JSON + ops RunReport on-disk readers.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest

import daily_report as dr


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _make_cfg(tmp_path: Path, *, enabled: bool = True) -> dr.Config:
    return dr.Config(
        enabled=enabled,
        smtp_host="smtp.test.local",
        smtp_port=587,
        smtp_user="reporter@example.com",
        smtp_pass="hunter2",
        mail_from="reporter@example.com",
        mail_to=("aaron@oddsprimer.com", "adi.dagan@gmail.com"),
        daily_report_hour=8,
        env_label="staging",
        ops_root=tmp_path / "ops",
        desk_output_dir=tmp_path / "desk_out",
        database_url="postgresql://user:pass@host/db",
        starttls=True,
    )


def _write_match_json(root: Path, match_id: str, *, team_a: str, team_b: str,
                      state: str = "pick", side: Optional[str] = None,
                      edge_pp: Optional[float] = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "match_id": match_id,
        "team_a": team_a, "team_b": team_b,
        "kickoff_utc": "2026-06-12T19:00:00Z",
        "verdict": {"state": state, "side": side, "edge_pp": edge_pp},
    }
    (root / f"{match_id}.json").write_text(json.dumps(payload), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Config validation
# ─────────────────────────────────────────────────────────────────────


def test_load_config_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("DAILY_REPORT_ENABLED", "SMTP_HOST", "SMTP_USER", "SMTP_PASS",
              "DAILY_REPORT_TO", "DAILY_REPORT_FROM"):
        monkeypatch.delenv(k, raising=False)
    cfg = dr.load_config()
    assert cfg.enabled is False
    assert cfg.mail_to == ()


def test_load_config_enabled_requires_smtp_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_REPORT_ENABLED", "1")
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "DAILY_REPORT_TO", "DAILY_REPORT_FROM"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError) as exc:
        dr.load_config()
    msg = str(exc.value)
    assert "SMTP_HOST" in msg
    assert "SMTP_USER" in msg
    assert "DAILY_REPORT_TO" in msg


def test_load_config_enabled_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_REPORT_ENABLED", "1")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "adi.dagan@gmail.com")
    monkeypatch.setenv("SMTP_PASS", "xxxx")
    monkeypatch.setenv("DAILY_REPORT_FROM", "adi.dagan@gmail.com")
    monkeypatch.setenv("DAILY_REPORT_TO", "aaron@oddsprimer.com, adi.dagan@gmail.com")
    cfg = dr.load_config()
    assert cfg.enabled is True
    assert cfg.smtp_port == 587
    assert cfg.mail_to == ("aaron@oddsprimer.com", "adi.dagan@gmail.com")


# ─────────────────────────────────────────────────────────────────────
# Window math
# ─────────────────────────────────────────────────────────────────────


def test_window_for_is_utc_midnight_inclusive() -> None:
    w = dr.window_for(date(2026, 5, 28))
    assert w.start == datetime(2026, 5, 28, tzinfo=timezone.utc)
    assert w.end   == datetime(2026, 5, 29, tzinfo=timezone.utc)
    assert w.label_date == date(2026, 5, 28)


def test_window_prior_is_one_day_back() -> None:
    w = dr.window_for(date(2026, 5, 28))
    prior = w.prior
    assert prior.label_date == date(2026, 5, 27)
    assert prior.start == datetime(2026, 5, 27, tzinfo=timezone.utc)


def test_yesterday_utc() -> None:
    now = datetime(2026, 5, 29, 4, 0, tzinfo=timezone.utc)
    assert dr.yesterday_utc(now) == date(2026, 5, 28)


# ─────────────────────────────────────────────────────────────────────
# Status line
# ─────────────────────────────────────────────────────────────────────


def test_status_line_failed_pipeline_overrides_traffic() -> None:
    s = dr.status_line(views=2000, votes=500, cta_total=120, desk_status="fail")
    assert s["color"] == "red"
    assert "failed" in s["line"].lower()


def test_status_line_quiet_day() -> None:
    s = dr.status_line(views=0, votes=0, cta_total=0, desk_status="ok")
    assert s["color"] == "amber"
    assert "quiet" in s["label"].lower()


def test_status_line_low_traffic() -> None:
    s = dr.status_line(views=10, votes=2, cta_total=1, desk_status="ok")
    assert s["color"] == "amber"
    assert "10 views" in s["line"]


def test_status_line_healthy() -> None:
    s = dr.status_line(views=500, votes=50, cta_total=20, desk_status="ok")
    assert s["color"] == "green"
    assert "500 views" in s["line"]


def test_delta_label_up_down_flat_new() -> None:
    assert dr._delta_label(150, 100)[0].startswith("▲")
    assert dr._delta_label(75, 100)[0].startswith("▼")
    assert "flat" in dr._delta_label(100, 100)[0]
    assert "new" in dr._delta_label(5, 0)[0]


# ─────────────────────────────────────────────────────────────────────
# Enrichment readers (desk JSON / RunReport / tick-totals)
# ─────────────────────────────────────────────────────────────────────


def test_resolve_match_label_full(tmp_path: Path) -> None:
    _write_match_json(tmp_path, "fb-wc26-fra-mex-20260612",
                      team_a="France", team_b="Mexico",
                      state="pick", side="France", edge_pp=4.2)
    out = dr.resolve_match_label("fb-wc26-fra-mex-20260612", root=tmp_path)
    assert out["label"] == "France vs Mexico"
    assert out["verdict_state"] == "pick"
    assert out["verdict_label"] == "Pick · France"
    assert out["edge_pp"] == pytest.approx(4.2)


def test_resolve_match_label_missing_file(tmp_path: Path) -> None:
    out = dr.resolve_match_label("fb-wc26-zzz-yyy-20990101", root=tmp_path)
    assert out["label"] == "fb-wc26-zzz-yyy-20990101"
    assert out["verdict_state"] == "unknown"


def test_list_live_pick_match_ids(tmp_path: Path) -> None:
    _write_match_json(tmp_path, "fb-wc26-aaa-bbb-20260612",
                      team_a="A", team_b="B", state="pick", side="A", edge_pp=5.0)
    _write_match_json(tmp_path, "fb-wc26-ccc-ddd-20260612",
                      team_a="C", team_b="D", state="pass")
    picks = dr.list_live_pick_match_ids(root=tmp_path)
    assert picks == {"fb-wc26-aaa-bbb-20260612"}


def test_read_latest_run_report_picks_newest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir(parents=True)
    (runs / "run-20260528T060000Z.json").write_text(
        json.dumps({"run_id": "run-20260528T060000Z", "status": "ok"}),
        encoding="utf-8",
    )
    (runs / "run-20260529T060000Z.json").write_text(
        json.dumps({"run_id": "run-20260529T060000Z", "status": "ok"}),
        encoding="utf-8",
    )
    out = dr.read_latest_run_report(ops_root=tmp_path)
    assert out is not None
    assert out["run_id"] == "run-20260529T060000Z"


def test_read_latest_run_report_none(tmp_path: Path) -> None:
    assert dr.read_latest_run_report(ops_root=tmp_path) is None


def test_read_tick_total_for_match(tmp_path: Path) -> None:
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "tick-totals.jsonl").write_text(
        '{"run_id":"run-20260528T060000Z","total_usd":0.012,"calls":34}\n'
        '{"run_id":"run-20260529T060000Z","total_usd":0.045,"calls":71}\n',
        encoding="utf-8",
    )
    row = dr.read_tick_total_for("run-20260529T060000Z", ops_root=tmp_path)
    assert row is not None
    assert row["total_usd"] == pytest.approx(0.045)
    assert row["calls"] == 71


def test_read_tick_total_missing_returns_none(tmp_path: Path) -> None:
    assert dr.read_tick_total_for("run-99999999T000000Z", ops_root=tmp_path) is None


def test_build_desk_section_with_report_and_tick() -> None:
    report = {
        "run_id": "run-20260528T060000Z",
        "started_at": "2026-05-28T06:00:00Z",
        "finished_at": "2026-05-28T06:01:34Z",
        "duration_s": 94.2,
        "status": "ok",
        "trigger": "scheduled",
        "funnel": [
            {"stage": "raw_events", "n": 200, "note": None},
            {"stage": "published", "n": 72, "note": None},
        ],
        "verdicts": {"pick": 10, "pass": 60, "avoid": 2},
        "changes": [{"x": 1}, {"x": 2}, {"x": 3}],
    }
    tick = {"run_id": "run-20260528T060000Z", "total_usd": 0.21, "calls": 81}
    out = dr.build_desk_section(report, tick)
    assert out["published"] == 72
    assert out["picks"] == 10 and out["passes"] == 60 and out["avoids"] == 2
    assert out["tick_usd"] == pytest.approx(0.21)
    assert out["tick_calls"] == 81
    assert out["changes"] == 3
    assert out["last_run_status"] == "ok"


def test_build_desk_section_with_no_report() -> None:
    out = dr.build_desk_section(None, None)
    assert out["published"] == 0
    assert out["tick_usd"] == 0.0
    assert out["funnel"] == []


def test_build_sentiment_percentages() -> None:
    s = dr.build_sentiment({"sharp_call": 40, "fair_call": 10, "off_mark": 30, "wait_see": 20})
    assert s["total"] == 100
    assert s["aligned_pct"] == 50
    # Each row carries its percentage of total.
    pcts = {r["label"]: r["pct"] for r in s["rows"]}
    assert pcts["Bullish"] == 40 and pcts["Value"] == 10
    assert pcts["Trap line"] == 30 and pcts["Overpriced"] == 20


def test_build_funnel_scales_to_top() -> None:
    f = dr.build_funnel(views=200, votes=20, cta_total=4)
    assert f["top"] == 200
    pcts = {r["label"]: r["pct"] for r in f["rows"]}
    assert pcts["Match pages viewed"] == 100
    assert pcts["Voted on a match"] == 10
    assert pcts["Clicked a market CTA"] == 2


# ─────────────────────────────────────────────────────────────────────
# Fake Postgres connection — substring-matched
# ─────────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    """Row that supports both r["k"] and r.k attribute-style access — asyncpg
    Records support both. Daily-report code uses bracket access only."""


class _FakeConn:
    """Substring-routed fake conn. Each query is matched on a key fragment
    and pulls from the test fixture's `state` dict.

    The same query helper is called twice per run (current window + prior),
    so we route by date range — args[0] is always the window start.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self._wprior_start = state["w_prior_start"]
        self._wcurr_start = state["w_curr_start"]

    def _bucket(self, args: tuple) -> str:
        # First arg is always window.start.
        if args and args[0] == self._wcurr_start:
            return "curr"
        return "prior"

    async def fetchval(self, sql: str, *args: Any) -> Any:
        s = sql.lower()
        b = self._bucket(args)
        if "count(*) from match_views" in s and "viewed_at" in s:
            return self.state[b]["views"]
        if "count(distinct anon_id) from match_views" in s:
            return self.state[b]["uniques"]
        if "count(*) from match_reactions" in s and "voted_at" in s:
            return self.state[b]["votes"]
        if "count(*) from cta_clicks" in s and "clicked_at" in s and "venue" not in s:
            return self.state[b]["cta"]
        return 0

    async def fetchrow(self, sql: str, *args: Any) -> Optional[dict]:
        s = sql.lower()
        if "from match_aggregates" in s:
            mid = args[0]
            return self.state["aggregates"].get(mid)
        if "extract(hour from viewed_at)" in s:
            return self.state[self._bucket(args)]["busiest_hour_row"]
        if "count(*) as n from match_views" in s and "match_id = $1" in s:
            mid = args[0]
            views = next(
                (m["views"] for m in self.state[self._bucket(args[1:3])]["top"] if m["match_id"] == mid),
                self.state["per_match_view_fallback"].get(mid, 0),
            )
            return _FakeRow({"n": views})
        return None

    async def fetch(self, sql: str, *args: Any) -> list[dict]:
        s = sql.lower()
        b = self._bucket(args)
        if "anon_id, min(viewed_at)" in s:
            return self.state[b]["nvr_rows"]
        if "venue, count(*) as n from cta_clicks" in s:
            return [_FakeRow(r) for r in self.state[b]["cta_by_venue"]]
        if "reaction, count(*) as n from match_reactions" in s:
            return [_FakeRow(r) for r in self.state[b]["reactions_rows"]]
        if "from match_views" in s and "group by match_id order by views desc" in s and "not exists" not in s:
            return [_FakeRow({"match_id": m["match_id"], "views": m["views"]})
                    for m in self.state[b]["top"]]
        if "not exists" in s:
            return [_FakeRow({"match_id": mid, "views": self.state["per_match_view_fallback"].get(mid, 0)})
                    for mid in self.state[b]["zero_click_ids"]]
        return []


@pytest.fixture
def fake_state(tmp_path: Path) -> dict:
    w = dr.window_for(date(2026, 5, 28))
    return {
        "w_curr_start": w.start,
        "w_prior_start": w.prior.start,
        "curr": {
            "views":   320,
            "uniques": 180,
            "votes":   42,
            "cta":     17,
            "busiest_hour_row": _FakeRow({"h": 19, "n": 80}),
            "nvr_rows": [
                _FakeRow({"anon_id": "a", "first_seen": w.start}),
                _FakeRow({"anon_id": "b", "first_seen": w.start.replace(hour=4)}),
                _FakeRow({"anon_id": "c", "first_seen": w.prior.start}),
            ],
            "cta_by_venue": [
                {"venue": "polymarket", "n": 12},
                {"venue": "kalshi",      "n": 5},
            ],
            "reactions_rows": [
                {"reaction": "sharp_call", "n": 20},
                {"reaction": "fair_call",  "n": 10},
                {"reaction": "off_mark",   "n": 8},
                {"reaction": "wait_see",   "n": 4},
            ],
            "top": [
                {"match_id": "fb-wc26-fra-mex-20260612", "views": 120},
                {"match_id": "fb-wc26-arg-alg-20260617", "views": 90},
            ],
            "zero_click_ids": ["fb-wc26-bra-mar-20260613"],
        },
        "prior": {
            "views":   240,
            "uniques": 150,
            "votes":   30,
            "cta":     12,
            "busiest_hour_row": _FakeRow({"h": 20, "n": 50}),
            "nvr_rows": [],
            "cta_by_venue": [],
            "reactions_rows": [],
            "top": [],
            "zero_click_ids": [],
        },
        "aggregates": {
            "fb-wc26-fra-mex-20260612": _FakeRow({"votes_total": 22, "aligned_pct": 70}),
            "fb-wc26-arg-alg-20260617": _FakeRow({"votes_total": 12, "aligned_pct": None}),
        },
        "per_match_view_fallback": {"fb-wc26-bra-mar-20260613": 33},
    }


# ─────────────────────────────────────────────────────────────────────
# build_context + render smoke
# ─────────────────────────────────────────────────────────────────────


def test_build_context_and_render_html(tmp_path: Path, fake_state: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio as _aio
    _aio.run(_build_context_and_render_html_inner(tmp_path, fake_state, monkeypatch))


async def _build_context_and_render_html_inner(tmp_path: Path, fake_state: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    desk_out = tmp_path / "desk_out"
    _write_match_json(desk_out, "fb-wc26-fra-mex-20260612",
                      team_a="France", team_b="Mexico", state="pick",
                      side="France", edge_pp=4.2)
    _write_match_json(desk_out, "fb-wc26-arg-alg-20260617",
                      team_a="Argentina", team_b="Algeria", state="pick",
                      side="Argentina", edge_pp=11.4)
    _write_match_json(desk_out, "fb-wc26-bra-mar-20260613",
                      team_a="Brazil", team_b="Morocco", state="pick",
                      side="Brazil", edge_pp=6.0)

    # Patch the module-level desk-output root + the resolver.
    monkeypatch.setattr(dr, "DESK_OUTPUT_FOOTBALL", desk_out)

    # Ops dir — empty: no run report yet.
    ops_root = tmp_path / "ops"
    cfg = replace(_make_cfg(tmp_path), ops_root=ops_root, desk_output_dir=tmp_path)

    conn = _FakeConn(fake_state)
    w = dr.window_for(date(2026, 5, 28))
    ctx = await dr.build_context(cfg, conn, w)

    assert ctx["report_date"] == "2026-05-28"
    assert ctx["kpi"]["views"] == 320
    assert "+33%" in ctx["kpi"]["views_delta"]
    assert ctx["kpi"]["cta_total"] == 17
    assert ctx["audience"]["new_pct"] == 67   # 2 of 3 first_seen in window
    assert ctx["audience"]["busiest_hour"] == "19:00–20:00"
    assert any(r["venue"] == "polymarket" and r["count"] == 12 for r in ctx["cta_by_venue"])
    assert ctx["top_matches"][0]["label"] == "France vs Mexico"
    assert ctx["sentiment"]["total"] == 42
    assert ctx["sentiment"]["aligned_pct"] == 71  # 30/42 rounded
    assert any(r["label"] == "Brazil vs Morocco" for r in ctx["zero_click_picks"])
    assert ctx["desk"]["published"] == 0  # no run report
    assert ctx["status"]["color"] == "green"

    html = dr.render_html(ctx)
    # Sample-PDF figures must all appear in the rendered HTML.
    for needle in [
        "320",            # views
        "180",            # uniques
        "42",             # votes
        "17",             # cta clicks
        "France vs Mexico",
        "Argentina vs Algeria",
        "Brazil vs Morocco",
        "Polymarket",
        "Kalshi",
        "19:00–20:00",
        "Odds Primer",
        "Daily report",
        "Audience",
        "Desk health",
    ]:
        assert needle in html, f"missing fragment: {needle!r}"


# ─────────────────────────────────────────────────────────────────────
# Idempotency round-trip
# ─────────────────────────────────────────────────────────────────────


def test_already_sent_round_trip(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    d = date(2026, 5, 28)
    assert dr.already_sent(cfg, d) is False
    dr.mark_sent(cfg, d)
    assert dr.already_sent(cfg, d) is True
    # Different day is still unsent.
    assert dr.already_sent(cfg, date(2026, 5, 29)) is False


# ─────────────────────────────────────────────────────────────────────
# Email assembly
# ─────────────────────────────────────────────────────────────────────


def test_build_email_has_alt_html_and_pdf(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    msg = dr.build_email(
        cfg, subject="Odds Primer — Daily Report (2026-05-28)",
        html="<html><body>hi</body></html>",
        pdf=b"%PDF-1.4 dummy", report_date=date(2026, 5, 28),
    )
    assert isinstance(msg, EmailMessage)
    assert msg["To"] == "aaron@oddsprimer.com, adi.dagan@gmail.com"
    assert "Daily Report" in msg["Subject"]
    # Plain + HTML alt.
    payloads = [p for p in msg.walk()]
    types = {p.get_content_type() for p in payloads}
    assert "text/html" in types
    assert "application/pdf" in types


def test_build_email_no_pdf_when_render_failed(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    msg = dr.build_email(
        cfg, subject="x", html="<html></html>", pdf=None,
        report_date=date(2026, 5, 28),
    )
    types = {p.get_content_type() for p in msg.walk()}
    assert "application/pdf" not in types
    assert "text/html" in types


# ─────────────────────────────────────────────────────────────────────
# run_once skip paths
# ─────────────────────────────────────────────────────────────────────


def test_run_once_disabled_returns_skip(tmp_path: Path) -> None:
    import asyncio as _aio
    cfg = _make_cfg(tmp_path, enabled=False)
    out = _aio.run(dr.run_once(cfg))
    assert out["sent"] is False
    assert out["reason"] == "disabled"


def test_run_once_already_sent_returns_skip(tmp_path: Path) -> None:
    import asyncio as _aio
    cfg = _make_cfg(tmp_path)
    d = date(2026, 5, 28)
    dr.mark_sent(cfg, d)
    out = _aio.run(dr.run_once(cfg, report_date=d))
    assert out["sent"] is False
    assert out["reason"] == "already_sent"


def test_run_once_raises_when_database_url_missing(tmp_path: Path) -> None:
    import asyncio as _aio
    cfg = replace(_make_cfg(tmp_path), database_url=None)
    with pytest.raises(RuntimeError) as exc:
        _aio.run(dr.run_once(cfg, force=True))
    assert "DATABASE_URL" in str(exc.value)
