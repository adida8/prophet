"""Daily site QA smoke test.

Externally hits every public Odds Primer surface once a day, asserts each
route returns a healthy status AND renders the content it's supposed to
(not a blank SPA shell or an error page), then emails a PASS/FAIL brief to
the configured recipients.

This is a smoke test, not an E2E suite: it answers "is the live site up and
are its pages rendering?" — the 80/20 that catches a dead route, a broken
deploy, a cert problem, or an empty page. It does NOT click through
interaction flows (voting, wallet paste); that's a separate Playwright job.

Design mirrors daily_report.py deliberately:
  - same SMTP env vars (SMTP_HOST/PORT/USER/PASS) + STARTTLS send path
  - same fail-loud config when enabled but creds missing
  - same idempotency state file under {ops_root}
  - same CLI surface (--once / --force / --dry-run)

Gated behind SITE_QA_ENABLED=1 so a fresh deploy stays silent until the
operator opts in.

Run manually:
    python site_qa.py --once --dry-run   # render + print, no email, no state
    python site_qa.py --once             # run checks + email + record state
    python site_qa.py --once --force     # ignore "already sent today"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("site_qa")

# ─────────────────────────────────────────────────────────────────────────────
# What we check
# ─────────────────────────────────────────────────────────────────────────────
#
# Each Check: a GET against {base}{path}. `expect_status` is the set of
# acceptable HTTP codes (a 301/302 to the canonical path is fine for some
# routes). `must_contain` is a case-insensitive substring that proves the
# page actually rendered its content rather than a blank shell or an error
# page. `critical=True` means a failure here is a site-down-class problem
# (flips the whole run to FAIL in the subject line); non-critical failures
# are reported but keep the headline GREEN.

DEFAULT_BASE = os.getenv("SITE_QA_BASE_URL", "https://www.oddsprimer.com").rstrip("/")


@dataclass(frozen=True)
class Check:
    name: str
    path: str
    must_contain: tuple[str, ...] = ()
    expect_status: tuple[int, ...] = (200,)
    critical: bool = True
    follow_redirects: bool = True


# The editorial surfaces are server-rendered HTML — we can assert on real
# content. The SPA sub-products (/ledger, /desk) ship a React shell, so we
# only assert the shell loads (a 200 with the root div), not deep content.
CHECKS: tuple[Check, ...] = (
    Check("Home", "/", must_contain=("odds primer",)),
    Check("Matches", "/matches", must_contain=("match", "odds primer")),
    Check("Outrights", "/outrights/", must_contain=("odds primer",)),
    Check("Learn / methodology", "/methodology", must_contain=("odds primer",),
          expect_status=(200, 301, 302)),
    Check("About", "/about", must_contain=("odds primer",)),
    Check("Ledger (SPA shell)", "/ledger", must_contain=("<div id=\"root\"", "<body")),
    Check("Backtest dashboard", "/backtest", must_contain=("<html", "brier"),
          critical=False),
    Check("Health endpoint", "/health", must_contain=("status",)),
    # API surfaces the front-end depends on.
    Check("Desk matches API", "/api/desk/matches?competition=wc26",
          must_contain=("[", "{"), critical=True),
    Check("Desk outrights API", "/api/desk/outrights",
          must_contain=("[", "{"), critical=False),
)

# Bare apex is checked separately because the failure mode we care about is a
# TLS / cert-name problem, which is a connection-level error rather than an
# HTTP status. Reported as a non-critical warning.
APEX_URL = os.getenv("SITE_QA_APEX_URL", "https://oddsprimer.com/")


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Config:
    enabled: bool
    base_url: str
    qa_hour: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    starttls: bool
    mail_from: str
    mail_to: tuple[str, ...]
    env_label: str
    state_path: Path


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None else default


def _ops_root() -> Path:
    explicit = os.getenv("DESK_OPS_DIR")
    if explicit:
        return Path(explicit)
    output_dir = os.getenv("DESK_OUTPUT_DIR", "desk/data/output")
    return Path(output_dir) / "ops"


def load_config() -> Config:
    """Build config from env. When SITE_QA_ENABLED=1, fail loud on missing
    SMTP / recipient vars (same posture as daily_report). When disabled, a
    half-configured env is fine — the loop/CLI exit cleanly."""
    enabled = _env("SITE_QA_ENABLED", "0") == "1"

    base_url = _env("SITE_QA_BASE_URL", DEFAULT_BASE).rstrip("/")
    qa_hour = int(_env("SITE_QA_HOUR", "7") or "7")

    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    mail_from = _env("SITE_QA_FROM") or _env("DAILY_REPORT_FROM") or smtp_user
    to_raw = _env("SITE_QA_TO") or _env("DAILY_REPORT_TO")
    mail_to = tuple(addr.strip() for addr in to_raw.split(",") if addr.strip())
    env_label = _env("DAILY_REPORT_ENV", "staging")

    if enabled:
        missing = []
        if not smtp_host: missing.append("SMTP_HOST")
        if not smtp_user: missing.append("SMTP_USER")
        if not smtp_pass: missing.append("SMTP_PASS")
        if not mail_from: missing.append("SITE_QA_FROM (or SMTP_USER)")
        if not mail_to:   missing.append("SITE_QA_TO (or DAILY_REPORT_TO)")
        if missing:
            raise RuntimeError(
                "SITE_QA_ENABLED=1 but missing env: " + ", ".join(missing)
            )

    state_path = _ops_root() / "site_qa" / "last_sent.json"

    return Config(
        enabled=enabled,
        base_url=base_url,
        qa_hour=qa_hour,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        starttls=_env("SMTP_STARTTLS", "1") != "0",
        mail_from=mail_from,
        mail_to=mail_to,
        env_label=env_label,
        state_path=state_path,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Running the checks
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Result:
    name: str
    url: str
    ok: bool
    critical: bool
    status: Optional[int] = None
    detail: str = ""
    elapsed_ms: int = 0


async def _run_check(client: httpx.AsyncClient, base: str, chk: Check) -> Result:
    url = f"{base}{chk.path}"
    started = datetime.now(timezone.utc)
    try:
        resp = await client.get(url, follow_redirects=chk.follow_redirects)
    except Exception as exc:  # noqa: BLE001 — any transport error is a fail
        return Result(chk.name, url, ok=False, critical=chk.critical,
                      detail=f"request error: {type(exc).__name__}: {exc}")
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    if resp.status_code not in chk.expect_status:
        return Result(chk.name, url, ok=False, critical=chk.critical,
                      status=resp.status_code,
                      detail=f"status {resp.status_code} not in {chk.expect_status}",
                      elapsed_ms=elapsed_ms)

    body = resp.text.lower()
    for needle in chk.must_contain:
        if needle.lower() not in body:
            return Result(chk.name, url, ok=False, critical=chk.critical,
                          status=resp.status_code,
                          detail=f"missing expected content: {needle!r}",
                          elapsed_ms=elapsed_ms)

    return Result(chk.name, url, ok=True, critical=chk.critical,
                  status=resp.status_code, detail="ok", elapsed_ms=elapsed_ms)


async def _check_apex(client: httpx.AsyncClient, url: str) -> Result:
    """Bare apex check. A TLS/cert-name mismatch surfaces as a connection
    error here — exactly the failure we want to catch. Non-critical."""
    try:
        resp = await client.get(url, follow_redirects=True)
        return Result("Bare apex (TLS)", url, ok=True, critical=False,
                      status=resp.status_code, detail="ok")
    except ssl.SSLError as exc:
        return Result("Bare apex (TLS)", url, ok=False, critical=False,
                      detail=f"TLS/cert error: {exc}")
    except Exception as exc:  # noqa: BLE001
        return Result("Bare apex (TLS)", url, ok=False, critical=False,
                      detail=f"{type(exc).__name__}: {exc}")


async def run_checks(cfg: Config) -> list[Result]:
    timeout = httpx.Timeout(20.0, connect=10.0)
    headers = {"User-Agent": "OddsPrimer-SiteQA/1.0"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        tasks = [_run_check(client, cfg.base_url, c) for c in CHECKS]
        tasks.append(_check_apex(client, APEX_URL))
        return list(await asyncio.gather(*tasks))


# ─────────────────────────────────────────────────────────────────────────────
# Rendering the email
# ─────────────────────────────────────────────────────────────────────────────


def summarise(results: list[Result]) -> dict:
    total = len(results)
    failed = [r for r in results if not r.ok]
    critical_failed = [r for r in failed if r.critical]
    passed = total - len(failed)
    overall = "FAIL" if critical_failed else ("WARN" if failed else "PASS")
    return {
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "critical_failed": len(critical_failed),
        "overall": overall,
    }


def build_html(cfg: Config, results: list[Result], report_dt: datetime) -> str:
    s = summarise(results)
    badge_color = {"PASS": "#1a7f37", "WARN": "#9a6700", "FAIL": "#cf222e"}[s["overall"]]
    rows = []
    for r in sorted(results, key=lambda x: (x.ok, not x.critical, x.name)):
        dot = "#1a7f37" if r.ok else ("#cf222e" if r.critical else "#9a6700")
        status_txt = "PASS" if r.ok else ("FAIL" if r.critical else "WARN")
        code = r.status if r.status is not None else "—"
        rows.append(
            f"<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>"
            f"<span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
            f"background:{dot};margin-right:8px;'></span>{r.name}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-weight:600;"
            f"color:{dot};'>{status_txt}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>{code}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;color:#555;"
            f"font-family:monospace;font-size:12px;'>{r.detail}</td>"
            f"</tr>"
        )
    ts = report_dt.strftime("%a, %d %b %Y %H:%M UTC")
    return f"""\
<!doctype html><html><body style="margin:0;background:#faf9f6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;">
<div style="max-width:680px;margin:0 auto;padding:24px;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #1a1a1a;padding-bottom:8px;">
    <div style="font-weight:800;font-size:18px;">Odds Primer · Site QA</div>
    <div style="color:#777;font-size:12px;">{ts} · {cfg.env_label}</div>
  </div>
  <div style="margin:20px 0;display:flex;align-items:center;gap:14px;">
    <span style="background:{badge_color};color:#fff;font-weight:700;padding:6px 16px;border-radius:6px;font-size:16px;">{s['overall']}</span>
    <span style="color:#444;">{s['passed']}/{s['total']} checks passed
      {'· ' + str(s['critical_failed']) + ' critical failing' if s['critical_failed'] else ''}</span>
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <thead><tr style="text-align:left;color:#777;font-size:12px;text-transform:uppercase;">
      <th style="padding:6px 10px;">Surface</th><th style="padding:6px 10px;">Result</th>
      <th style="padding:6px 10px;">Code</th><th style="padding:6px 10px;">Detail</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p style="color:#999;font-size:11px;margin-top:18px;">
    Smoke test against {cfg.base_url}. Checks route availability + content render only —
    not interaction flows. WARN = non-critical surface degraded; FAIL = a critical surface is down.
  </p>
</div></body></html>"""


def build_email(cfg: Config, *, subject: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.mail_from
    msg["To"] = ", ".join(cfg.mail_to)
    msg.set_content("Your email client did not render the HTML version of the Site QA report.")
    msg.add_alternative(html, subtype="html")
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
    return _read_state(cfg.state_path).get("last_sent_date") == report_date.isoformat()


def _record_sent(cfg: Config, report_date: date, overall: str) -> None:
    cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_path.write_text(
        json.dumps({
            "last_sent_date": report_date.isoformat(),
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "overall": overall,
        }),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


async def run_once(cfg: Config, *, force: bool = False, dry_run: bool = False) -> dict:
    if not cfg.enabled and not dry_run:
        return {"status": "skipped", "reason": "disabled"}

    now = datetime.now(timezone.utc)
    today = now.date()

    if not force and not dry_run and already_sent(cfg, today):
        return {"status": "skipped", "reason": "already_sent", "date": today.isoformat()}

    results = await run_checks(cfg)
    s = summarise(results)
    html = build_html(cfg, results, now)
    subject = f"[{s['overall']}] Odds Primer Site QA · {today.isoformat()} · {cfg.env_label}"

    if dry_run:
        return {"status": "dry_run", "summary": s, "subject": subject,
                "html": html, "results": results}

    msg = build_email(cfg, subject=subject, html=html)
    send_email(cfg, msg)
    _record_sent(cfg, today, s["overall"])
    return {"status": "sent", "summary": s, "subject": subject,
            "to": list(cfg.mail_to)}


def _main() -> int:
    ap = argparse.ArgumentParser(description="Odds Primer daily site QA smoke test")
    ap.add_argument("--once", action="store_true", help="Run a single pass and exit")
    ap.add_argument("--force", action="store_true", help="Ignore already-sent-today")
    ap.add_argument("--dry-run", action="store_true",
                    help="Run checks + render, but do NOT email or record state")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    cfg = load_config()
    result = asyncio.run(run_once(cfg, force=args.force, dry_run=args.dry_run))

    if args.dry_run:
        s = result.get("summary", {})
        print(f"\nSUBJECT: {result.get('subject')}")
        print(f"OVERALL: {s.get('overall')}  ({s.get('passed')}/{s.get('total')} passed, "
              f"{s.get('critical_failed')} critical fail)\n")
        for r in result.get("results", []):
            tag = "PASS" if r.ok else ("FAIL" if r.critical else "WARN")
            print(f"  [{tag:4}] {r.name:24} {r.status or '-':>4}  {r.detail}")
        print()
    else:
        print(json.dumps(result, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
