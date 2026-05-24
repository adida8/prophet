"""Env-driven config for the distribute layer.

Reads at process start (not module import) so tests can monkey-patch
env vars per case. Validation is fail-loud: if push is enabled but the
URL/secret are missing, `load_config()` raises rather than silently
publishing to nowhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Backoff schedule between attempts (in seconds). After the last entry
# is exhausted, the row is dead-lettered. Tuned for hourly refresh
# cadence: the 30s/2min/10min steps fire on the first sub-tick worker
# sweep that finds the row due; 1h/6h cover steady-state MTA outages.
RETRY_SCHEDULE_SEC: tuple[int, ...] = (30, 120, 600, 3600, 21600)

# Hard ceiling on canonical-JSON body size before we refuse to enqueue.
# MTA enforces 65536 bytes; we guard at a slightly lower threshold so
# the worst-case is a loud local failure, not a 413 round-trip. The
# contract bounds make this comfortable — see ADR / changelog.
DEFAULT_MAX_BODY_BYTES = 60_000

# How many in-flight pushes the worker dispatches concurrently per sweep.
DEFAULT_MAX_IN_FLIGHT = 8

# Token-bucket cap to stay under MTA's 60-req/min/source-IP ceiling.
DEFAULT_RATE_PER_MIN = 50

# Where the outbox sqlite lives by default. Mirrors the signals.db
# pattern — overridable via DESK_DISTRIBUTE_DB_PATH so the production
# deploy can point at a mounted Railway volume that survives container
# restarts (otherwise an in-flight outbox row gets wiped on every
# redeploy and MTA misses the push).
_PACKAGE_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "distribute.db"


def default_db_path() -> Path:
    env = os.getenv("DESK_DISTRIBUTE_DB_PATH")
    if env:
        return Path(env)
    return _PACKAGE_DB_PATH


@dataclass(frozen=True)
class DistributeConfig:
    """Resolved at process start; immutable thereafter."""
    push_enabled:   bool
    webhook_url:    str | None
    webhook_secret: str | None
    db_path:        Path
    rate_per_min:   int
    max_in_flight:  int
    max_body_bytes: int


def load_config() -> DistributeConfig:
    """Read env and return a frozen config.

    Raises ValueError when DESK_DISTRIBUTE_PUSH=1 but URL or secret are
    missing — fail-loud at boot beats silently dropping pushes.
    """
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
        push_enabled   = push_enabled,
        webhook_url    = webhook_url,
        webhook_secret = webhook_secret,
        db_path        = default_db_path(),
        rate_per_min   = _int_env("DESK_DISTRIBUTE_RATE_PER_MIN", DEFAULT_RATE_PER_MIN),
        max_in_flight  = _int_env("DESK_DISTRIBUTE_MAX_IN_FLIGHT", DEFAULT_MAX_IN_FLIGHT),
        max_body_bytes = _int_env("DESK_DISTRIBUTE_MAX_BYTES", DEFAULT_MAX_BODY_BYTES),
    )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default
