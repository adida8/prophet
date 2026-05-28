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
# DESK_OPS_DIR (no default constant — runner + ops API each read the
# env var directly because the default depends on the caller's
# output_dir; see desk/runner.py and desk_ops_api.py).

# ── Verdict thresholds (percentage points) ───────────────────────────
# Locked in spec §4 PR 4. Read once at process start.
PICK_PP_THRESHOLD:  float = float(os.getenv("DESK_PICK_PP", "3.0"))
PASS_PP_THRESHOLD:  float = float(os.getenv("DESK_PASS_PP", "1.0"))
AVOID_PP_THRESHOLD: float = float(os.getenv("DESK_AVOID_PP", "-2.0"))

# ── LLM ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── External data layer (data-layer spec §4 + §6) ────────────────────
# Phase 2 spine — RANK + FORM (B.1) and INJURIES + LINEUP (B.3). Empty
# string when unset; data-layer modules treat empty as "unconfigured"
# and skip their fetch with a clean error.
API_FOOTBALL_KEY:        str = os.getenv("API_FOOTBALL_KEY", "")
# Phase 3 weather (B.2). OpenWeatherMap One Call 3.0.
OPENWEATHERMAP_API_KEY:  str = os.getenv("OPENWEATHERMAP_API_KEY", "")

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

# ── Phase B.1 — form / FIFA-rank residual on the Elo prior ───────────
# Off by default — the model hook lives in Shadow until data-layer
# Phase 2 (API-Football rank + form) populates FootballFeatures with
# real values. Flip to 1 once the coupled unit clears forward-validation
# per THE_DESK_OPTIMIZATION_SPEC §4.B.1.
FORM_RANK_RESIDUAL_ENABLED: bool = os.getenv("DESK_FORM_RANK_RESIDUAL", "0") == "1"

# ── Phase B.3 — injury Elo penalty ──────────────────────────────────
# Off by default. Data side (`desk fetch-injuries`) fills the cache;
# the flag only controls whether the published verdict reflects the
# bounded per-team penalty. Stays off until the operator-run source
# audit (`desk b3-audit`) clears + a forward-validation report shows
# no Brier regression.
INJURY_PENALTY_ENABLED: bool = os.getenv("DESK_INJURY_PENALTY", "0") == "1"
