"""Env-driven config for the stub.

Two config surfaces in one place:

  * Output dir   — where the frozen JSON lives (served by the GET routes
                   and read by the engine). `DESK_OUTPUT_DIR` overrides;
                   default is `data/output/` under the stub root.
  * Distribute   — the push wire to MTAI. Identical env contract to the
                   live Desk so the same secret + URL just work.

Reads env at call time (not import) so a runtime flip is honoured and
tests can monkey-patch per case. Validation is fail-loud: push enabled
without URL/secret raises rather than silently pushing to nowhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Stub root is the parent of this package dir (desk_stub/).
_STUB_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT_ROOT = _STUB_ROOT / "data" / "output"
_DEFAULT_DB_PATH = _STUB_ROOT / "data" / "distribute.db"

# Backoff schedule between attempts (seconds). After the last entry is
# exhausted, the row is dead-lettered. Same schedule as the live Desk.
RETRY_SCHEDULE_SEC: tuple[int, ...] = (30, 120, 600, 3600, 21600)

DEFAULT_MAX_BODY_BYTES = 60_000
DEFAULT_MAX_IN_FLIGHT = 8
DEFAULT_RATE_PER_MIN = 50


def output_root() -> Path:
    env = os.getenv("DESK_OUTPUT_DIR")
    return Path(env) if env else _DEFAULT_OUTPUT_ROOT


def default_db_path() -> Path:
    env = os.getenv("DESK_DISTRIBUTE_DB_PATH")
    return Path(env) if env else _DEFAULT_DB_PATH


@dataclass(frozen=True)
class DistributeConfig:
    """Resolved at process start; immutable thereafter."""
    push_enabled:        bool
    webhook_url:         str | None
    webhook_secret:      str | None
    db_path:             Path
    rate_per_min:        int
    max_in_flight:       int
    max_body_bytes:      int
    # Cross-venue (ADR 0004) fields ride the wire body. Default ON to
    # match the live Desk as of 2026-05-31. Override OFF via
    # DESK_DISTRIBUTE_INCLUDE_CROSS_VENUE=0 if a consumer regresses.
    include_cross_venue: bool


def load_config() -> DistributeConfig:
    """Read env and return a frozen config. Raises ValueError when
    DESK_DISTRIBUTE_PUSH=1 but URL or secret are missing."""
    push_enabled = os.getenv("DESK_DISTRIBUTE_PUSH", "0") == "1"
    webhook_url    = os.getenv("DESK_DISTRIBUTE_WEBHOOK_URL") or None
    webhook_secret = os.getenv("DESK_DISTRIBUTE_WEBHOOK_SECRET") or None

    if push_enabled:
        missing: list[str] = []
        if not webhook_url:
            missing.append("DESK_DISTRIBUTE_WEBHOOK_URL")
        if not webhook_secret:
            missing.append("DESK_DISTRIBUTE_WEBHOOK_SECRET")
        if missing:
            raise ValueError(
                "DESK_DISTRIBUTE_PUSH=1 but required env unset: "
                + ", ".join(missing)
            )

    return DistributeConfig(
        push_enabled        = push_enabled,
        webhook_url         = webhook_url,
        webhook_secret      = webhook_secret,
        db_path             = default_db_path(),
        rate_per_min        = _int_env("DESK_DISTRIBUTE_RATE_PER_MIN", DEFAULT_RATE_PER_MIN),
        max_in_flight       = _int_env("DESK_DISTRIBUTE_MAX_IN_FLIGHT", DEFAULT_MAX_IN_FLIGHT),
        max_body_bytes      = _int_env("DESK_DISTRIBUTE_MAX_BYTES", DEFAULT_MAX_BODY_BYTES),
        include_cross_venue = os.getenv("DESK_DISTRIBUTE_INCLUDE_CROSS_VENUE", "1") == "1",
    )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default
