"""Desk refresh loop (server-side shim).

Lives at the project root next to `desk_api.py` for the same reason —
the `desk/` directory ships as an independent Python package and is not
pip-installed in the Railway deploy. We therefore drive the existing
`python -m desk …` CLI as subprocesses (cwd=desk/) instead of
importing the package directly.

Each tick runs these steps in sequence, isolated:
  1. `python -m desk run --once`       — football match pipeline
     (auto-enriches `copy.editorial_citations` + hard-signal Elo
     adjustments when the signals cache has rows for a fixture).
     Writes a RunReport with a run_id we read back from the manifest
     so we can attach cost to it later in the tick.
  2. `python -m desk outrights`        — WC 2026 winner MC sim
  3. `python site/generate.py --quiet` — regenerate the static site
  4. `python -m desk fetch-signals`    — pull RSS into signals cache
     (gated on DESK_SIGNALS_FETCH=1)
  5. `python -m desk extract-signals`  — Haiku reads cache → Signals
     (gated on DESK_SIGNALS_EXTRACT=1, needs ANTHROPIC_API_KEY)

After step 5, we sum all Haiku-cost rows tagged with this tick's
`DESK_TICK_ID` (written by the call sites in
`desk/desk/signals/extract.py` and `desk/desk/explainer/haiku.py`)
and append a `tick-totals.jsonl` row keyed by the matches RunReport's
`run_id`. The ops API joins this onto the run history table so the
dashboard shows a per-run cost column.

Cadence + enable/disable are read from `{ops_root}/control.json`, the
file the Desk admin page writes. The schema is:

    { "enabled": bool, "hours": [int 0..23], "updated_at": iso8601 }

Each hour in `hours` is a UTC clock hour at which the loop fires
exactly once per day. Empty list = no scheduled runs (loop idles).
Operators add/remove hours via the UI; the loop polls control.json
on every scheduling decision so changes land without a restart.

`DESK_AUTORUN=0` is still respected as a hard kill switch (useful
when the deployment platform needs to pause the loop without dashboard
access), but the dashboard's enabled flag is the runtime knob.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("desk.refresh_loop")

INITIAL_DELAY_SEC = int(os.getenv("DESK_INITIAL_DELAY_SEC", "60"))
IDLE_POLL_SEC     = 60   # how often we re-read control.json when paused or unscheduled

ROOT     = Path(__file__).resolve().parent
DESK_DIR = ROOT / "desk"
SITE_GEN = ROOT / "site" / "generate.py"

_RUN_ID_RE = re.compile(r"^run-\d{8}T\d{6}Z$")

# Default schedule for a fresh install. Must match desk_ops_api.py.
_DEFAULT_HOURS = [6]


def _ops_root() -> Path:
    ops_dir_env = os.getenv("DESK_OPS_DIR")
    if ops_dir_env:
        return Path(ops_dir_env)
    out_env = os.getenv("DESK_OUTPUT_DIR")
    if out_env:
        return Path(out_env) / "ops"
    return DESK_DIR / "data" / "output" / "ops"


def _normalise_hours(raw: Any) -> list[int]:
    """Coerce input into a sorted, deduped list of valid UTC hours."""
    if not isinstance(raw, (list, tuple)):
        return list(_DEFAULT_HOURS)
    out: set[int] = set()
    for v in raw:
        try:
            h = int(v)
        except (TypeError, ValueError):
            continue
        if 0 <= h <= 23:
            out.add(h)
    return sorted(out)[:24]


def _read_control() -> dict[str, Any]:
    """Return the persisted control state, or sane defaults."""
    path = _ops_root() / "control.json"
    if not path.is_file():
        return {"enabled": True, "hours": list(_DEFAULT_HOURS)}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("control.json unreadable, using defaults: %s", e)
        return {"enabled": True, "hours": list(_DEFAULT_HOURS)}
    return {
        "enabled": bool(raw.get("enabled", True)),
        "hours":   _normalise_hours(raw.get("hours")),
    }


def _seconds_until_next_run(hours: list[int], now: datetime | None = None) -> int | None:
    """Seconds from `now` (UTC) until the next scheduled run, or None.

    Returns None when `hours` is empty — the caller idles. We fire on
    the next *strictly later* matching hour boundary so a tick that
    runs slightly past the top of the hour doesn't immediately retrigger.
    """
    hours = sorted(set(h for h in hours if 0 <= h <= 23))
    if not hours:
        return None
    now = now or datetime.now(timezone.utc)
    for h in hours:
        target = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if target > now:
            return int((target - now).total_seconds())
    # Past today's last scheduled hour → tomorrow's earliest.
    tomorrow = (now + timedelta(days=1)).replace(
        hour=hours[0], minute=0, second=0, microsecond=0,
    )
    return int((tomorrow - now).total_seconds())


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _new_tick_id() -> str:
    return datetime.now(tz=timezone.utc).strftime("tick-%Y%m%dT%H%M%SZ")


def _run(cmd: list[str], *, cwd: Path, timeout: int, label: str,
         extra_env: dict[str, str] | None = None) -> bool:
    """Synchronous subprocess wrapper. Logs outcome; never raises. Returns
    True on exit code 0, False otherwise (so the loop can record
    matches_failed correctly when deciding what to attach cost to)."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
        )
        if result.returncode == 0:
            log.info("%s: ok", label)
            return True
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
        return False
    except subprocess.TimeoutExpired:
        log.warning("%s: timed out after %ds", label, timeout)
        return False
    except Exception:
        log.exception("%s: subprocess failed", label)
        return False


def _latest_run_id() -> str | None:
    """Most-recent persisted matches run_id, or None.

    Reads the recorder's `index.json` (rebuilt by the recorder on every
    persist) — falls back to scanning runs/ if the manifest is missing
    or stale.
    """
    root = _ops_root()
    index_path = root / "index.json"
    if index_path.is_file():
        try:
            manifest = json.loads(index_path.read_text(encoding="utf-8"))
            runs = manifest.get("runs") or []
            if runs:
                rid = runs[0].get("run_id")
                if rid and _RUN_ID_RE.match(rid):
                    return rid
        except (OSError, json.JSONDecodeError):
            pass
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return None
    candidates = sorted(
        f.stem for f in runs_dir.iterdir()
        if f.is_file() and f.suffix == ".json" and _RUN_ID_RE.match(f.stem)
    )
    return candidates[-1] if candidates else None


def _sum_costs(tick_id: str) -> dict[str, Any]:
    """Read costs.jsonl and sum rows tagged with `tick_id`."""
    path = _ops_root() / "costs.jsonl"
    out: dict[str, Any] = {"total_usd": 0.0, "calls": 0, "breakdown": {}}
    if not path.is_file():
        return out
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
                if row.get("tick_id") != tick_id:
                    continue
                usd = float(row.get("usd") or 0.0)
                out["total_usd"] += usd
                out["calls"] += 1
                caller = row.get("caller") or "?"
                out["breakdown"][caller] = round(
                    out["breakdown"].get(caller, 0.0) + usd, 6,
                )
    except OSError as e:
        log.warning("costs.jsonl read failed: %s", e)
    out["total_usd"] = round(out["total_usd"], 6)
    return out


def _append_tick_total(row: dict[str, Any]) -> None:
    root = _ops_root()
    root.mkdir(parents=True, exist_ok=True)
    try:
        with (root / "tick-totals.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError as e:
        log.warning("tick-totals.jsonl write failed: %s", e)


def _tick() -> None:
    """Run all subprocess steps for one refresh tick, then persist costs."""
    py = sys.executable
    tick_id    = _new_tick_id()
    started_at = _now_iso()
    sub_env    = {"DESK_TICK_ID": tick_id}

    # Order matters: matches + outrights + site come first so the
    # dashboard-critical artifacts always get refreshed, even if the
    # news-signals steps run long. Signals enrich next tick's matches —
    # one-tick lag is fine, missing matches isn't.
    _run([py, "-m", "desk", "run", "--once"],
         cwd=DESK_DIR, timeout=600, label="desk matches", extra_env=sub_env)
    _run([py, "-m", "desk", "outrights"],
         cwd=DESK_DIR, timeout=300, label="desk outrights", extra_env=sub_env)
    _run([py, str(SITE_GEN), "--quiet"],
         cwd=ROOT, timeout=120, label="site regenerate", extra_env=sub_env)

    # News-signals steps run only when explicitly enabled — they hit
    # external services + the Anthropic API, so an unconfigured deploy
    # should never accidentally start charging tokens.
    if os.getenv("DESK_SIGNALS_FETCH", "0") == "1":
        _run([py, "-m", "desk", "fetch-signals"],
             cwd=DESK_DIR, timeout=180, label="desk fetch-signals", extra_env=sub_env)

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
            _run(extract_cmd, cwd=DESK_DIR, timeout=600,
                 label="desk extract-signals", extra_env=sub_env)

    # Phase B.1 data side — refresh api-football form_delta values.
    # Gated on the operator: a fresh deploy won't burn the api-football
    # daily quota until they opt in. Cost: ~70 calls per tick, well
    # under the 7,500/day Pro cap.
    if os.getenv("DESK_RANK_FORM_FETCH", "0") == "1":
        if not os.getenv("API_FOOTBALL_KEY"):
            log.warning("desk fetch-rank-form: API_FOOTBALL_KEY unset, skipping")
        else:
            _run([py, "-m", "desk", "fetch-rank-form"],
                 cwd=DESK_DIR, timeout=300,
                 label="desk fetch-rank-form", extra_env=sub_env)

    # Phase B.3 data side — refresh api-football /injuries cache +
    # per-team Elo penalty. Off by default; flips on once the operator
    # runs `desk b3-audit` and confirms api-football's coverage.
    if (os.getenv("DESK_INJURY_FETCH", "0") == "1"
            and os.getenv("API_FOOTBALL_KEY")):
        _run([py, "-m", "desk", "fetch-injuries"],
             cwd=DESK_DIR, timeout=300,
             label="desk fetch-injuries", extra_env=sub_env)

    # Phase 1b data side — refresh live Elo (eloratings.net + clubelo).
    # Free providers; no vendor key required. Gated so a fresh deploy
    # doesn't start fetching until the operator opts in.
    if os.getenv("DESK_ELO_FETCH", "0") == "1":
        _run([py, "-m", "desk", "fetch-elo"],
             cwd=DESK_DIR, timeout=300,
             label="desk fetch-elo", extra_env=sub_env)

    # Slice B / N3 — refresh api-football lineups for fixtures inside the
    # next 24h. Confirmed XI lands ~1h pre-kickoff, so the daily tick
    # catches it only for fixtures kicking off late tomorrow. The T-90m
    # polling loop in `desk_lineups_refresh_loop.py` is the main writer.
    # Both share the same cache + idempotent upsert.
    if (os.getenv("DESK_LINEUP_FETCH", "0") == "1"
            and os.getenv("API_FOOTBALL_KEY")):
        _run([py, "-m", "desk", "fetch-lineups", "--window-hours", "24"],
             cwd=DESK_DIR, timeout=300,
             label="desk fetch-lineups", extra_env=sub_env)

    # Phase B.1 measurement loop — ingest resolved match outcomes so
    # the forward-validation report can score them. Piggy-backs on
    # the form-fetch flag because both need the same api-football key.
    if (os.getenv("DESK_RANK_FORM_FETCH", "0") == "1"
            and os.getenv("API_FOOTBALL_KEY")):
        _run([py, "-m", "desk", "fv-ingest-outcomes"],
             cwd=DESK_DIR, timeout=300,
             label="desk fv-ingest-outcomes", extra_env=sub_env)

    # Social — draft today's daily Pick into the approval queue.
    # No network calls (Phase 1 publish is manual), so safe to run
    # whenever enabled. Selector returns None when nothing qualifies.
    if os.getenv("DESK_SOCIAL_ENABLED", "0") == "1":
        _run([py, "-m", "desk", "social", "draft-daily"],
             cwd=DESK_DIR, timeout=180,
             label="desk social draft-daily", extra_env=sub_env)

    # Persist this tick's cost summary so the dashboard can show it.
    # Linking by `run_id` lets the dashboard join one row of the run
    # history table with one row of tick-totals. When matches failed
    # outright and no RunReport got written, run_id stays None and the
    # cost row simply doesn't appear in the dashboard's cost column.
    totals     = _sum_costs(tick_id)
    run_id     = _latest_run_id()
    finished_at = _now_iso()
    _append_tick_total({
        "tick_id":     tick_id,
        "run_id":      run_id,
        "started_at":  started_at,
        "finished_at": finished_at,
        "total_usd":   totals["total_usd"],
        "calls":       totals["calls"],
        "breakdown":   totals["breakdown"],
    })


async def run_desk_loop() -> None:
    if os.getenv("DESK_AUTORUN", "1") == "0":
        log.info("desk refresh loop disabled (DESK_AUTORUN=0)")
        return

    log.info(
        "desk refresh loop online — control state via {ops_root}/control.json "
        "(boot tick in %ds)", INITIAL_DELAY_SEC,
    )
    await asyncio.sleep(INITIAL_DELAY_SEC)

    # Boot tick — only when the loop is enabled. This gives a fresh
    # deploy current data without waiting for the next scheduled hour.
    # `DESK_FORCE_TICK_ON_BOOT=1` overrides control.json so a redeploy
    # can guarantee a refresh even when the schedule is empty or paused.
    boot_control = _read_control()
    force_boot = os.getenv("DESK_FORCE_TICK_ON_BOOT", "0") == "1"
    should_boot = force_boot or (
        boot_control["enabled"] and boot_control["hours"]
    )
    if should_boot:
        if force_boot:
            log.info("desk refresh: boot tick FORCED via DESK_FORCE_TICK_ON_BOOT=1")
        else:
            log.info("desk refresh: boot tick starting (scheduled hours=%s)",
                     boot_control["hours"])
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("desk refresh tick failed (boot)")
    else:
        log.info(
            "desk refresh: boot tick skipped (enabled=%s, hours=%s); "
            "set DESK_FORCE_TICK_ON_BOOT=1 to override",
            boot_control["enabled"], boot_control["hours"],
        )

    while True:
        control = _read_control()

        if not control["enabled"]:
            # Paused via the dashboard. Re-check periodically so the
            # operator's flip takes effect within ~1 minute.
            log.info("desk refresh: paused via control.json — re-check in %ds", IDLE_POLL_SEC)
            await asyncio.sleep(IDLE_POLL_SEC)
            continue

        sleep_for = _seconds_until_next_run(control["hours"])
        if sleep_for is None:
            # Enabled but no hours scheduled — idle.
            log.info("desk refresh: no scheduled hours — re-check in %ds", IDLE_POLL_SEC)
            await asyncio.sleep(IDLE_POLL_SEC)
            continue

        # Sleep in chunks no longer than ~5 min so a mid-day schedule
        # edit (e.g. adding a closer hour) takes effect promptly. After
        # each chunk we re-read control and re-compute the next target.
        chunk = min(sleep_for, 300)
        log.info(
            "desk refresh: next run in %ds (hours=%s)",
            sleep_for, control["hours"],
        )
        await asyncio.sleep(chunk)
        if chunk < sleep_for:
            continue   # not yet — recompute on next iteration

        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("desk refresh tick failed")
