"""Async loop that drains the distribute outbox to MTA.

Lives at the project root next to `desk_refresh_loop.py` for the same
reason: the `desk/` directory ships as an independent Python package
and is not pip-installed in the Railway deploy. We drive
`python -m desk distribute-drain` as a subprocess each tick.

Cadence is independent of the hourly matches refresh: this loop ticks
every `DESK_DISTRIBUTE_TICK_SEC` (default 30s) so retries land near
the bottom of the backoff schedule (30/120/600/3600/21600s). When
`DESK_DISTRIBUTE_PUSH=0` (default) the loop exits immediately and is
never re-entered — no env-change cost when the wire is off.

Subprocess-per-tick keeps memory bounded and lets the desk package
manage its own SQLite handle / HTTP client lifecycle. A drain of an
empty outbox returns in <100ms; a sweep of 70 fresh enqueues at
50 req/min ceiling completes inside ~90s — comfortably under the
2-min process timeout.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("desk.distribute_loop")

ROOT     = Path(__file__).resolve().parent
DESK_DIR = ROOT / "desk"

INITIAL_DELAY_SEC = int(os.getenv("DESK_DISTRIBUTE_INITIAL_DELAY_SEC", "75"))
DEFAULT_TICK_SEC  = 30
PROCESS_TIMEOUT_SEC = 120


def _tick() -> None:
    """One subprocess invocation of `desk distribute-drain`."""
    py = sys.executable
    cmd = [py, "-m", "desk", "distribute-drain"]
    try:
        result = subprocess.run(
            cmd, cwd=DESK_DIR, capture_output=True, text=True,
            timeout=PROCESS_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        log.warning("distribute-drain: timed out after %ds", PROCESS_TIMEOUT_SEC)
        return
    except Exception:
        log.exception("distribute-drain: subprocess failed")
        return

    if result.returncode != 0:
        # Strip the Pydantic UserWarning noise that prefixes every desk
        # subprocess (the contract's `copy` field shadows BaseModel.copy).
        blob = (result.stderr or result.stdout)
        lines = [ln for ln in blob.splitlines()
                 if "UserWarning" not in ln
                 and "shadows an attribute" not in ln
                 and "class MatchOutput" not in ln]
        tail = "\n".join(lines)[-1000:].strip()
        log.warning("distribute-drain: exit %d — %s", result.returncode, tail)
        return

    # Stdout carries the per-sweep summary line; surface it at info so
    # the operator can grep one log stream for steady-state delivery.
    out = (result.stdout or "").strip()
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line:
                log.info(line)


async def run_distribute_loop() -> None:
    if os.getenv("DESK_DISTRIBUTE_PUSH", "0") != "1":
        log.info("distribute loop disabled (DESK_DISTRIBUTE_PUSH != 1)")
        return

    tick_sec = int(os.getenv("DESK_DISTRIBUTE_TICK_SEC", str(DEFAULT_TICK_SEC)))
    if tick_sec < 5:
        log.warning("DESK_DISTRIBUTE_TICK_SEC=%d clamped to 5", tick_sec)
        tick_sec = 5

    log.info(
        "distribute loop online — tick every %ds (boot tick in %ds)",
        tick_sec, INITIAL_DELAY_SEC,
    )
    await asyncio.sleep(INITIAL_DELAY_SEC)

    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("distribute loop tick failed")
        await asyncio.sleep(tick_sec)
