"""T-90m lineup polling loop — Slice C / N6 of the team-news blurb spec.

Confirmed XIs land ~1h pre-kickoff. The daily Desk refresh tick fires at
the operator's scheduled UTC hour and would miss them. This loop sits
next to it, polling at a much shorter cadence (default 15 min) and only
firing actual api-football calls for fixtures whose kickoff lands within
the next 2 hours.

When a lineup row updates AND blurbs need republishing, the loop also
fires `python -m desk run --once` + `python site/generate.py` so the
new starters end up in the published JSON + static HTML before kickoff.

Gated on `DESK_LINEUP_LOOP_ENABLED=1`. Off by default — without it the
data path stays cold and the blurbs continue to render with
`lineup.state="unknown"` exactly like Slice A.

Costs (per spec §6 Option A): ≈ 1 /fixtures call (cached forever) +
1 /fixtures/lineups call per fixture in the 2h window. On a typical
WC26 day with 4 kickoffs in the window, that's ≈ 8 calls/hr at the
default 15-min cadence — well inside Pro tier's 7,500/day cap.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from loop_registry import is_enabled

log = logging.getLogger("desk.lineups_loop")

LOOP_ID           = "lineups_refresh"
INITIAL_DELAY_SEC = int(os.getenv("DESK_LINEUP_LOOP_INITIAL_DELAY_SEC", "120"))
TICK_SEC          = int(os.getenv("DESK_LINEUP_LOOP_TICK_SEC", "900"))   # 15 min
WINDOW_HOURS      = float(os.getenv("DESK_LINEUP_LOOP_WINDOW_HOURS", "2"))
# Default flipped to OFF 2026-05-31. Auto-republishing on every successful
# lineup fetch silently fires the full Haiku blurb writer across all 72
# WC26 matches; with both staging + prod running, that burned $20 of
# Anthropic credit in a single day. Operator must explicitly opt in.
PUBLISH_AFTER_LANDING = (
    os.getenv("DESK_LINEUP_LOOP_PUBLISH", "0") == "1"
)

ROOT     = Path(__file__).resolve().parent
DESK_DIR = ROOT / "desk"
SITE_GEN = ROOT / "site" / "generate.py"


def _enabled() -> bool:
    return (
        os.getenv("DESK_LINEUP_LOOP_ENABLED", "0") == "1"
        and bool(os.getenv("API_FOOTBALL_KEY"))
        and os.getenv("DESK_AUTORUN", "1") != "0"
    )


def _run(cmd: list[str], *, cwd: Path, timeout: int, label: str) -> tuple[bool, str]:
    """Subprocess wrapper. Returns (ok, stdout-tail). Never raises."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            log.info("%s: ok", label)
            return True, (result.stdout or "")[-4000:]
        blob = (result.stderr or result.stdout)
        lines = [ln for ln in blob.splitlines()
                 if "UserWarning" not in ln
                 and "shadows an attribute" not in ln
                 and "class MatchOutput" not in ln]
        tail = "\n".join(lines)[-2000:].strip()
        log.warning("%s: exit %d — %s", label, result.returncode, tail)
        return False, tail
    except subprocess.TimeoutExpired:
        log.warning("%s: timed out after %ds", label, timeout)
        return False, ""
    except Exception:
        log.exception("%s: subprocess failed", label)
        return False, ""


# Match the fetch-lineups CLI's per-fixture status line:
#   "  fb-wc26-fra-mex-...   ok                home=confirmed/11  away=..."
# We just count "ok" outcomes to decide whether to republish.
_OK_LINE_RE = re.compile(r"^\s+\S+\s+ok\b")


def _count_ok_lineups(stdout_tail: str) -> int:
    """Parse the CLI output for ok rows. The loop runs again on the
    next cadence even when nothing landed, so the count drives the
    publish step only — failure isn't a hard stop."""
    n = 0
    for ln in stdout_tail.splitlines():
        if _OK_LINE_RE.match(ln):
            n += 1
    return n


def _tick() -> None:
    """One lineup-loop pass:
      1. Fetch lineups for fixtures in the next WINDOW_HOURS.
      2. If anything landed, run desk run --once + site/generate.py
         so the new starters reach the published JSON + static HTML.
    """
    started_at = datetime.now(tz=timezone.utc).isoformat()
    log.info(
        "lineups loop tick · window=%.1fh · started_at=%s",
        WINDOW_HOURS, started_at,
    )
    py = sys.executable

    ok, tail = _run(
        [py, "-m", "desk", "fetch-lineups",
         "--window-hours", str(WINDOW_HOURS)],
        cwd=DESK_DIR, timeout=300,
        label="desk fetch-lineups",
    )
    if not ok:
        return
    n_ok = _count_ok_lineups(tail)
    if n_ok == 0:
        log.info("lineups loop: no fresh lineups landed in window")
        return
    log.info("lineups loop: %d fresh lineup(s) landed — republishing", n_ok)
    if not PUBLISH_AFTER_LANDING:
        log.info("lineups loop: publish skipped (DESK_LINEUP_LOOP_PUBLISH=0)")
        return
    _run([py, "-m", "desk", "run", "--once"],
         cwd=DESK_DIR, timeout=600, label="desk run --once (post-lineup)")
    _run([py, str(SITE_GEN), "--quiet"],
         cwd=ROOT, timeout=180, label="site/generate.py (post-lineup)")


async def run_lineups_loop() -> None:
    """Entry point invoked from `main.py` alongside the other loops.

    Honours BOTH the schedules.json admin toggle and the legacy
    `DESK_LINEUP_LOOP_ENABLED` env gate. The admin can flip the loop
    on/off live; the env gates remain as hard-deploy controls
    (`DESK_AUTORUN=0` as global kill, `API_FOOTBALL_KEY` as
    feature-flag-style prerequisite).
    """
    if not _enabled():
        log.info(
            "lineups loop disabled at boot (set DESK_LINEUP_LOOP_ENABLED=1 + "
            "API_FOOTBALL_KEY to enable)"
        )
        return

    log.info(
        "lineups loop online · cadence=%ds · window=%.1fh · "
        "boot in %ds (honours schedules.json toggle)",
        TICK_SEC, WINDOW_HOURS, INITIAL_DELAY_SEC,
    )
    await asyncio.sleep(INITIAL_DELAY_SEC)
    while True:
        if not is_enabled(LOOP_ID):
            await asyncio.sleep(min(TICK_SEC, 60))
            continue
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("lineups loop tick failed")
        await asyncio.sleep(TICK_SEC)
