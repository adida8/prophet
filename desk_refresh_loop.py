"""Hourly Desk refresh loop (server-side shim).

Lives at the project root next to `desk_api.py` for the same reason —
the `desk/` directory ships as an independent Python package and is not
pip-installed in the Railway deploy. We therefore drive the existing
`python -m desk …` CLI as subprocesses (cwd=desk/) instead of
importing the package directly.

Each tick runs steps in sequence, isolated:
  0a. `python -m desk fetch-signals`   — pull RSS into signals cache
      (gated on DESK_SIGNALS_FETCH=1)
  0b. `python -m desk extract-signals` — Haiku reads cache → Signals
      (gated on DESK_SIGNALS_EXTRACT=1, needs ANTHROPIC_API_KEY)
  1.  `python -m desk run --once`      — football match pipeline
      (auto-enriches `copy.editorial_citations` + hard-signal Elo
      adjustments when the signals cache has rows for a fixture)
  2.  `python -m desk outrights`       — WC 2026 winner MC sim
  3.  `python site/generate.py --quiet` — regenerate the static site
      so the masthead's "Last refresh" stamp and the per-match pages
      pick up the new JSON.

A single tick fires shortly after boot so the site reflects fresh data
even when the last committed JSON is stale.

Disabled with DESK_AUTORUN=0 (defaults to on). Signals steps default
off so a deploy without ANTHROPIC_API_KEY runs cleanly.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("desk.refresh_loop")

REFRESH_INTERVAL_SEC = int(os.getenv("DESK_REFRESH_INTERVAL_SEC", str(60 * 60)))
INITIAL_DELAY_SEC    = int(os.getenv("DESK_INITIAL_DELAY_SEC",    "60"))

ROOT     = Path(__file__).resolve().parent
DESK_DIR = ROOT / "desk"
SITE_GEN = ROOT / "site" / "generate.py"


def _run(cmd: list[str], *, cwd: Path, timeout: int, label: str) -> None:
    """Synchronous subprocess wrapper. Logs outcome; never raises."""
    import subprocess
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            log.info("%s: ok", label)
        else:
            # Strip the leading Pydantic UserWarning that contract.py emits
            # on every import — it's noise that pushes the real exception
            # off the visible end of the truncated log line. Keep up to 2000
            # chars of the actual tail so a traceback survives.
            blob = (result.stderr or result.stdout)
            lines = [ln for ln in blob.splitlines()
                     if "UserWarning" not in ln
                     and "shadows an attribute" not in ln
                     and "class MatchOutput" not in ln]
            tail = "\n".join(lines)[-2000:].strip()
            log.warning("%s: exit %d — %s", label, result.returncode, tail)
    except subprocess.TimeoutExpired:
        log.warning("%s: timed out after %ds", label, timeout)
    except Exception:
        log.exception("%s: subprocess failed", label)


def _tick() -> None:
    py = sys.executable

    # News-signals steps run only when explicitly enabled — they hit
    # external services + the Anthropic API, so an unconfigured deploy
    # should never accidentally start charging tokens.
    if os.getenv("DESK_SIGNALS_FETCH", "0") == "1":
        _run([py, "-m", "desk", "fetch-signals"],
             cwd=DESK_DIR, timeout=180, label="desk fetch-signals")

    if os.getenv("DESK_SIGNALS_EXTRACT", "0") == "1":
        if not os.getenv("ANTHROPIC_API_KEY"):
            log.warning("desk extract-signals: ANTHROPIC_API_KEY unset, skipping")
        else:
            extract_cmd = [py, "-m", "desk", "extract-signals"]
            # Optional per-source-per-tick cap, e.g. DESK_SIGNALS_EXTRACT_LIMIT=25
            # keeps the steady-state cost predictable. Unset ⇒ no cap.
            cap = os.getenv("DESK_SIGNALS_EXTRACT_LIMIT")
            if cap:
                extract_cmd += ["--limit", cap]
            _run(extract_cmd, cwd=DESK_DIR, timeout=600, label="desk extract-signals")

    _run([py, "-m", "desk", "run", "--once"],
         cwd=DESK_DIR, timeout=300, label="desk matches")
    _run([py, "-m", "desk", "outrights"],
         cwd=DESK_DIR, timeout=300, label="desk outrights")
    _run([py, str(SITE_GEN), "--quiet"],
         cwd=ROOT, timeout=120, label="site regenerate")


async def run_desk_loop() -> None:
    if os.getenv("DESK_AUTORUN", "1") == "0":
        log.info("desk refresh loop disabled (DESK_AUTORUN=0)")
        return

    log.info(
        "desk refresh loop online — every %ds (first run in %ds)",
        REFRESH_INTERVAL_SEC, INITIAL_DELAY_SEC,
    )
    await asyncio.sleep(INITIAL_DELAY_SEC)
    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("desk refresh tick failed")
        await asyncio.sleep(REFRESH_INTERVAL_SEC)
