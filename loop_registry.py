"""Background loop registry + schedules.json read/write helpers.

Source of truth for which background loops exist + their on/off state.
Lives at the project root for the same reason as `desk_ops_api.py`:
both the FastAPI process and the asyncio loop tasks need to share this,
and `desk/` is not pip-installed in the Railway deploy so we can't put
it under that package.

Schema of `{ops_root}/schedules.json`:

    {
      "version": 1,
      "updated_at": "2026-05-31T...",
      "loops": {
        "<loop_id>": { "enabled": bool, ... shape-specific fields }
      }
    }

The schedule shape per loop is fixed in `LOOPS` below. The admin page
toggles `enabled`; cadence fields are surfaced read-only in Phase 1.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger("loop_registry")

_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_OUTPUT = _PROJECT_ROOT / "desk" / "data" / "output"

ShapeKind = Literal["cron_hourly", "interval", "cron_weekly"]


@dataclass(frozen=True)
class LoopDef:
    """Static metadata about one background loop."""
    id:          str
    label:       str
    description: str
    shape:       ShapeKind
    # Default cadence (read-only in Phase 1). Stored in schedules.json
    # so the API can surface the current value; phase 2 makes it editable.
    default:     dict[str, Any]
    # Default `enabled` state on a fresh install. Important: this is the
    # state when schedules.json doesn't yet exist. Existing env-var-based
    # gates (DESK_DISTRIBUTE_PUSH, DAILY_REPORT_ENABLED, etc.) layer on
    # top — `enabled` is the *additional* admin-side gate.
    default_enabled: bool
    # Free-form additional gating info shown in the UI so the operator
    # understands why a loop might still be inactive even when enabled.
    requires:    tuple[str, ...] = ()


# Ordered for display. Most-expensive/highest-attention first.
LOOPS: tuple[LoopDef, ...] = (
    LoopDef(
        id="desk_refresh",
        label="Desk refresh",
        description="Matches + outrights + site regeneration + signals fetch/extract. "
                    "Most expensive loop (Haiku per match).",
        shape="cron_hourly",
        default={"hours": [6]},
        default_enabled=True,
    ),
    LoopDef(
        id="lineups_refresh",
        label="Lineups refresh",
        description="api-football /fixtures/lineups poll for kickoffs in the next 2h. "
                    "Free unless DESK_LINEUP_LOOP_PUBLISH=1 (then re-fires Haiku).",
        shape="interval",
        default={"tick_sec": 900},
        default_enabled=False,
        requires=("DESK_LINEUP_LOOP_ENABLED=1", "API_FOOTBALL_KEY"),
    ),
    LoopDef(
        id="distribute",
        label="Distribute drain",
        description="MTA push wire — drains outbox every 30s.",
        shape="interval",
        default={"tick_sec": 30},
        default_enabled=True,
        requires=("DESK_DISTRIBUTE_PUSH=1",),
    ),
    LoopDef(
        id="activity_aggregate",
        label="Activity aggregate",
        description="Recomputes per-match view + reaction aggregates from raw rows.",
        shape="interval",
        default={"tick_sec": 60},
        default_enabled=True,
        requires=("DATABASE_URL",),
    ),
    LoopDef(
        id="activity_seed",
        label="Activity seed",
        description="Popularity-weighted seed rows toward stage targets. "
                    "Auto-decays when real traffic catches up.",
        shape="interval",
        default={"tick_sec": 480},
        default_enabled=True,
        requires=("DATABASE_URL", "ACTIVITY_SEED_ENABLED=1"),
    ),
    LoopDef(
        id="activity_prune",
        label="Activity prune",
        description="Drops match_views rows older than 7 days.",
        shape="interval",
        default={"tick_sec": 86400},
        default_enabled=True,
        requires=("DATABASE_URL",),
    ),
    LoopDef(
        id="daily_report",
        label="Daily report",
        description="One-page HTML + PDF brief emailed once per day at DAILY_REPORT_HOUR UTC.",
        shape="cron_hourly",
        default={"hours": [8]},
        default_enabled=True,
        requires=("DAILY_REPORT_ENABLED=1", "SMTP_*"),
    ),
    LoopDef(
        id="site_qa",
        label="Site QA",
        description="Smoke test of the static site once per day; emails PASS/FAIL.",
        shape="cron_hourly",
        default={"hours": [7]},
        default_enabled=True,
        requires=("SMTP_*",),
    ),
    LoopDef(
        id="ledger_refresh",
        label="Ledger refresh",
        description="Polymarket wallet refresh for recently-viewed wallets. "
                    "DISABLED 2026-05-31 — flip the toggle on to re-activate.",
        shape="interval",
        default={"tick_sec": 1800},
        default_enabled=False,
    ),
    LoopDef(
        id="social_weekly",
        label="Social weekly roundup",
        description="Weekly Sunday roundup draft into the social approval queue.",
        shape="cron_weekly",
        default={"weekday": "sun", "hh_mm": "09:00"},
        default_enabled=True,
        requires=("DESK_SOCIAL_ENABLED=1",),
    ),
)


_LOOPS_BY_ID = {ld.id: ld for ld in LOOPS}


def _ops_root() -> Path:
    """Mirrors the helper in `desk_ops_api.py` / `desk_refresh_loop.py`.

    Both already settled on this resolution order — keep them aligned so
    schedules.json lives next to control.json on every deploy.
    """
    ops_dir = os.getenv("DESK_OPS_DIR")
    if ops_dir:
        return Path(ops_dir)
    out_env = os.getenv("DESK_OUTPUT_DIR")
    if out_env:
        return Path(out_env) / "ops"
    return _DEFAULT_OUTPUT / "ops"


def _schedules_path() -> Path:
    return _ops_root() / "schedules.json"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _defaults_doc() -> dict[str, Any]:
    """Build the in-memory defaults doc (used as fallback + as seed)."""
    return {
        "version":    1,
        "updated_at": None,
        "loops": {
            ld.id: {"enabled": ld.default_enabled, **ld.default}
            for ld in LOOPS
        },
    }


def read_schedules() -> dict[str, Any]:
    """Load schedules.json. Missing/unreadable → defaults.

    Always returns a doc with rows for every known loop. Unknown rows in
    the on-disk file are preserved (so a future-loop's row written by a
    newer deploy doesn't get wiped by an older one), but they don't show
    up in the `LOOPS` iteration and aren't surfaced by the API.
    """
    defaults = _defaults_doc()
    path = _schedules_path()
    if not path.is_file():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("schedules.json unreadable, using defaults: %s", e)
        return defaults

    on_disk = raw.get("loops") if isinstance(raw, dict) else None
    if not isinstance(on_disk, dict):
        return defaults

    merged = dict(defaults["loops"])
    for k, v in on_disk.items():
        if not isinstance(v, dict):
            continue
        seed = merged.get(k, {})
        # Coerce `enabled` strictly to bool; preserve other shape fields
        # the on-disk row carries (forward-compat with future shapes).
        out = {**seed, **v}
        out["enabled"] = bool(v.get("enabled", seed.get("enabled", True)))
        merged[k] = out
    return {
        "version":    int(raw.get("version") or 1),
        "updated_at": raw.get("updated_at"),
        "loops":      merged,
    }


def write_schedules(doc: dict[str, Any]) -> dict[str, Any]:
    """Persist a full schedules doc atomically.

    Caller must pass the full doc (use `read_schedules()` → mutate →
    `write_schedules()`). We stamp `updated_at` here so all writers
    agree on the source of truth for the timestamp.
    """
    doc = dict(doc)
    doc["version"] = int(doc.get("version") or 1)
    doc["updated_at"] = _now_iso()
    root = _ops_root()
    root.mkdir(parents=True, exist_ok=True)
    path = _schedules_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    tmp.replace(path)
    return doc


def set_loop_enabled(loop_id: str, enabled: bool) -> dict[str, Any]:
    """Toggle one loop's enabled flag and persist. Returns the new doc."""
    if loop_id not in _LOOPS_BY_ID:
        raise KeyError(f"unknown loop_id: {loop_id}")
    doc = read_schedules()
    row = dict(doc["loops"].get(loop_id, {}))
    row["enabled"] = bool(enabled)
    doc["loops"][loop_id] = row
    return write_schedules(doc)


def is_enabled(loop_id: str) -> bool:
    """Cheap read-side check loops call on every tick.

    Defensive: an unknown loop_id returns False rather than raising —
    a typo in a loop's registration shouldn't take the loop down at
    boot. The startup log will still flag it.
    """
    if loop_id not in _LOOPS_BY_ID:
        log.warning("is_enabled called with unknown loop_id=%s", loop_id)
        return False
    doc = read_schedules()
    row = doc["loops"].get(loop_id) or {}
    return bool(row.get("enabled", _LOOPS_BY_ID[loop_id].default_enabled))


def loop_defs() -> tuple[LoopDef, ...]:
    return LOOPS
