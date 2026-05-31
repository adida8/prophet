"""Social weekly-roundup cron loop.

Project-root async loop, sibling to `desk_refresh_loop.py` +
`activity_refresh_loop.py`. Fires `python -m desk social draft-weekly`
once per week — by default Sunday 09:00 UTC. Day + time are configurable
via env vars matching the spec:

    DESK_SOCIAL_WEEKLY_DAY   default "sunday" (case-insensitive)
    DESK_SOCIAL_WEEKLY_AT    default "09:00"  (UTC, HH:MM)

`DESK_AUTORUN=0` is honoured as the global kill switch (same as the
matches loop). `DESK_SOCIAL_ENABLED=0` keeps the loop online but the
draft subprocess no-ops — useful when the operator wants to leave the
schedule armed but pause briefly.

The loop is intentionally simple: one timer, one subprocess, no
tick-id / cost ledger. The weekly path doesn't hit any paid API
(stub renderer + zero Anthropic calls), so cost telemetry isn't
required. When the renderer or weekly captioner starts spending
money in a later PR, this is where to add it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loop_registry import is_enabled

log = logging.getLogger("desk.social.weekly_loop")

LOOP_ID           = "social_weekly"
INITIAL_DELAY_SEC = int(os.getenv("DESK_SOCIAL_INITIAL_DELAY_SEC", "120"))
IDLE_POLL_SEC     = 60   # wake every minute when we're between firings

ROOT     = Path(__file__).resolve().parent
DESK_DIR = ROOT / "desk"

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday")


def _read_weekday() -> int:
    raw = (os.getenv("DESK_SOCIAL_WEEKLY_DAY") or "sunday").strip().lower()
    if raw not in _WEEKDAYS:
        log.warning("DESK_SOCIAL_WEEKLY_DAY=%r invalid, defaulting to sunday", raw)
        return _WEEKDAYS.index("sunday")
    return _WEEKDAYS.index(raw)


def _read_clock() -> tuple[int, int]:
    raw = (os.getenv("DESK_SOCIAL_WEEKLY_AT") or "09:00").strip()
    parts = raw.split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except (ValueError, IndexError):
        log.warning("DESK_SOCIAL_WEEKLY_AT=%r invalid, defaulting to 09:00", raw)
        return 9, 0
    return h, m


def _next_fire(now: datetime) -> datetime:
    """Return the next datetime (UTC) at which the weekly cron should fire."""
    weekday_target = _read_weekday()
    hour, minute   = _read_clock()
    days_ahead     = (weekday_target - now.weekday()) % 7
    candidate = now.replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    ) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _run_subprocess(cmd: list[str], *, cwd: Path, timeout: int, label: str) -> bool:
    """Mirror of desk_refresh_loop._run, slimmed for the weekly cron.

    Returns True on exit 0. Never raises — we log + sleep regardless.
    """
    env = os.environ.copy()
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
        )
        if result.returncode == 0:
            log.info("%s: ok", label)
            return True
        tail = (result.stderr or result.stdout)[-2000:].strip()
        log.warning("%s: exit %d — %s", label, result.returncode, tail)
        return False
    except subprocess.TimeoutExpired:
        log.warning("%s: timed out after %ds", label, timeout)
        return False
    except Exception:
        log.exception("%s: subprocess failed", label)
        return False


def _fire_once() -> None:
    py = sys.executable
    _run_subprocess(
        [py, "-m", "desk", "social", "draft-weekly"],
        cwd=DESK_DIR, timeout=300,
        label="desk social draft-weekly",
    )


async def run_weekly_loop() -> None:
    if os.getenv("DESK_AUTORUN", "1") == "0":
        log.info("social weekly loop disabled (DESK_AUTORUN=0)")
        return
    if os.getenv("DESK_SOCIAL_ENABLED", "0") != "1":
        # Loop stays alive — flipping DESK_SOCIAL_ENABLED back to 1
        # without a restart would otherwise lose this scheduler. Idle
        # polling re-reads env on every tick.
        log.info("social weekly loop online (DESK_SOCIAL_ENABLED=0 — polling)")
    else:
        log.info("social weekly loop online")

    await asyncio.sleep(INITIAL_DELAY_SEC)

    while True:
        try:
            if not is_enabled(LOOP_ID) or os.getenv("DESK_SOCIAL_ENABLED", "0") != "1":
                await asyncio.sleep(IDLE_POLL_SEC)
                continue
            now = datetime.now(tz=timezone.utc)
            target = _next_fire(now)
            sleep_for = max(1, int((target - now).total_seconds()))
            log.info("social weekly: next fire at %s (sleep %ds)",
                     target.isoformat(), sleep_for)
            await asyncio.sleep(sleep_for)
            # Re-read enable flag — operator might have paused mid-sleep.
            if not is_enabled(LOOP_ID) or os.getenv("DESK_SOCIAL_ENABLED", "0") != "1":
                log.info("social weekly: paused at fire time, skipping")
                continue
            await asyncio.to_thread(_fire_once)
        except asyncio.CancelledError:
            raise
        except Exception:                                       # noqa: BLE001
            log.exception("social weekly loop iteration failed")
            await asyncio.sleep(60)
