"""Configuration — env vars + locked constants.

Constants live here as authoritative defaults. Anything tunable per
environment is read from the process env on import.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent

# ── Paths ─────────────────────────────────────────────────────────────
OUTPUT_DIR:   Path = Path(os.getenv("DESK_OUTPUT_DIR", str(ROOT / "data" / "output")))
CACHE_DIR:    Path = Path(os.getenv("DESK_CACHE_DIR", str(ROOT / "data" / "cache")))
SNAPSHOT_DIR: Path = Path(os.getenv("DESK_SNAPSHOT_DIR", str(ROOT / "data" / "snapshots")))

# ── Verdict thresholds (percentage points) ───────────────────────────
# Locked in spec §4 PR 4. Read once at process start.
PICK_PP_THRESHOLD:  float = float(os.getenv("DESK_PICK_PP", "3.0"))
PASS_PP_THRESHOLD:  float = float(os.getenv("DESK_PASS_PP", "1.0"))
AVOID_PP_THRESHOLD: float = float(os.getenv("DESK_AVOID_PP", "-2.0"))

# ── LLM ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Sport registry default ────────────────────────────────────────────
# v1 ships football only. Sports config in v2 reads sources.yaml.
DEFAULT_ACTIVE_SPORTS: tuple[str, ...] = ("football",)

# ── Competition allowlist ─────────────────────────────────────────────
# Live ingest only emits fixtures whose mapped competition code is in
# this set. Default is WC26-only — the launch wedge. Override with
# `DESK_COMPETITIONS=wc26,epl,ucl` (comma-separated codes) or set to
# `*` to disable the filter entirely.
def _parse_competitions(raw: str) -> frozenset[str] | None:
    raw = raw.strip()
    if raw == "*" or raw == "":
        return None
    return frozenset(c.strip().lower() for c in raw.split(",") if c.strip())


COMPETITION_ALLOWLIST: frozenset[str] | None = _parse_competitions(
    os.getenv("DESK_COMPETITIONS", "wc26")
)
