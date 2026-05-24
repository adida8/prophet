"""Anthropic cost ledger for the desk pipeline.

Each Haiku call site (signals extractor, blurb writer) appends one row to
`{ops_root}/costs.jsonl` immediately after receiving a response. Rows are
tagged with `DESK_TICK_ID` (set by desk_refresh_loop.py) so the refresh
loop can sum per-tick cost after running all subprocesses and write a
sidecar `tick-totals.jsonl` that the ops dashboard joins onto each
RunReport row by `run_id`.

Pricing constants are checked in. Bump them when Anthropic updates the
public price list.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("desk.ops.cost")

# USD per token. Source: anthropic.com/pricing.
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {
        "input":           1.00 / 1_000_000,
        "output":          5.00 / 1_000_000,
        "cache_write_5m":  1.25 / 1_000_000,
        "cache_read":      0.10 / 1_000_000,
    },
}


def _ops_root() -> Path:
    """Mirror the resolution used by recorder + desk_ops_api.py."""
    ops_dir_env = os.getenv("DESK_OPS_DIR")
    if ops_dir_env:
        return Path(ops_dir_env)
    out_env = os.getenv("DESK_OUTPUT_DIR")
    if out_env:
        return Path(out_env) / "ops"
    return Path(__file__).resolve().parents[2] / "data" / "output" / "ops"


def usd_for(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation: int = 0,
    cache_read: int = 0,
) -> float:
    p = _PRICING.get(model)
    if not p:
        # Unknown model — fall back to Haiku 4.5 so unknown-model spend
        # still shows up in the dashboard, not silently zeroed.
        log.warning("unknown model %s; pricing as claude-haiku-4-5", model)
        p = _PRICING["claude-haiku-4-5"]
    return round(
        input_tokens * p["input"]
        + output_tokens * p["output"]
        + cache_creation * p["cache_write_5m"]
        + cache_read * p["cache_read"],
        6,
    )


def log_call(*, model: str, usage: Any, caller: str) -> None:
    """Append one cost row from an anthropic response's `usage` field.

    `usage` is the raw `Usage` object from the SDK. Never raises — cost
    logging must not break the calling pipeline on disk/IO problems.
    """
    try:
        input_tokens   = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens  = int(getattr(usage, "output_tokens", 0) or 0)
        cache_creation = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cache_read     = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    except Exception as e:                              # noqa: BLE001
        log.warning("cost log: bad usage object: %s", e)
        return

    row = {
        "ts":             datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "tick_id":        os.getenv("DESK_TICK_ID") or "",
        "model":          model,
        "caller":         caller,
        "input_tokens":   input_tokens,
        "output_tokens":  output_tokens,
        "cache_creation": cache_creation,
        "cache_read":     cache_read,
        "usd":            usd_for(
            model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            cache_creation=cache_creation, cache_read=cache_read,
        ),
    }
    try:
        root = _ops_root()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "costs.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError as e:
        log.warning("cost log write failed: %s", e)
