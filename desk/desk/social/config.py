"""Process env → SocialConfig dataclass.

Mirrors `desk.distribute.config` in shape — keeps the pattern consistent
across the runtime knobs in the project. Boot-time `load_config()` is
strict: any half-configured Phase 2 spec (publish_mode=api but missing
IG/X creds) raises so a deployment fails loud instead of silently
falling back to "no posts get sent" for hours.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Project-default DB path — matches desk/data/social.db unless the
# operator points DESK_SOCIAL_DB_PATH at a mounted volume.
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH     = _PACKAGE_ROOT / "data" / "social.db"
_DEFAULT_ASSETS_DIR  = _PACKAGE_ROOT / "data" / "social_assets"


@dataclass(frozen=True)
class SocialConfig:
    enabled:        bool
    db_path:        Path
    assets_dir:     Path
    min_edge_pp:    float
    weekly_day:     str          # "sunday" / "monday" / …
    weekly_at:      str          # "HH:MM" UTC
    publish_mode:   str          # "manual" | "api"
    ig_access_token: str
    ig_business_id:  str
    x_api_key:      str
    x_api_secret:   str
    x_access_token: str
    x_access_secret: str


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday")


def _parse_hhmm(raw: str) -> str:
    raw = raw.strip()
    parts = raw.split(":")
    if len(parts) != 2:
        raise ValueError(f"DESK_SOCIAL_WEEKLY_AT must be HH:MM, got {raw!r}")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError as e:
        raise ValueError(f"DESK_SOCIAL_WEEKLY_AT must be HH:MM, got {raw!r}") from e
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"DESK_SOCIAL_WEEKLY_AT out of range: {raw!r}")
    return f"{h:02d}:{m:02d}"


def load_config() -> SocialConfig:
    """Read env into SocialConfig. Raise ValueError on bad shape."""
    enabled       = os.getenv("DESK_SOCIAL_ENABLED", "0") == "1"
    db_path       = Path(os.getenv("DESK_SOCIAL_DB_PATH") or _DEFAULT_DB_PATH)
    assets_dir    = Path(os.getenv("DESK_SOCIAL_ASSETS_DIR") or _DEFAULT_ASSETS_DIR)
    min_edge_raw  = os.getenv("DESK_SOCIAL_MIN_EDGE_PP", "2.0")
    try:
        min_edge_pp = float(min_edge_raw)
    except ValueError as e:
        raise ValueError(f"DESK_SOCIAL_MIN_EDGE_PP must be a number, got {min_edge_raw!r}") from e

    weekly_day = (os.getenv("DESK_SOCIAL_WEEKLY_DAY") or "sunday").strip().lower()
    if weekly_day not in _WEEKDAYS:
        raise ValueError(
            f"DESK_SOCIAL_WEEKLY_DAY must be one of {_WEEKDAYS}, got {weekly_day!r}",
        )

    weekly_at  = _parse_hhmm(os.getenv("DESK_SOCIAL_WEEKLY_AT") or "09:00")

    publish_mode = (os.getenv("DESK_SOCIAL_PUBLISH_MODE") or "manual").strip().lower()
    if publish_mode not in ("manual", "api"):
        raise ValueError(
            f"DESK_SOCIAL_PUBLISH_MODE must be 'manual' or 'api', got {publish_mode!r}",
        )

    ig_access_token  = (os.getenv("IG_ACCESS_TOKEN") or "").strip()
    ig_business_id   = (os.getenv("IG_BUSINESS_ACCOUNT_ID") or "").strip()
    x_api_key        = (os.getenv("X_API_KEY") or "").strip()
    x_api_secret     = (os.getenv("X_API_SECRET") or "").strip()
    x_access_token   = (os.getenv("X_ACCESS_TOKEN") or "").strip()
    x_access_secret  = (os.getenv("X_ACCESS_SECRET") or "").strip()

    if publish_mode == "api":
        missing = [
            name for name, val in (
                ("IG_ACCESS_TOKEN",        ig_access_token),
                ("IG_BUSINESS_ACCOUNT_ID", ig_business_id),
                ("X_API_KEY",              x_api_key),
                ("X_API_SECRET",           x_api_secret),
                ("X_ACCESS_TOKEN",         x_access_token),
                ("X_ACCESS_SECRET",        x_access_secret),
            ) if not val
        ]
        if missing:
            raise ValueError(
                "DESK_SOCIAL_PUBLISH_MODE=api requires all Phase 2 credentials "
                f"to be set together. Missing: {', '.join(missing)}",
            )

    return SocialConfig(
        enabled=enabled,
        db_path=db_path,
        assets_dir=assets_dir,
        min_edge_pp=min_edge_pp,
        weekly_day=weekly_day,
        weekly_at=weekly_at,
        publish_mode=publish_mode,
        ig_access_token=ig_access_token,
        ig_business_id=ig_business_id,
        x_api_key=x_api_key,
        x_api_secret=x_api_secret,
        x_access_token=x_access_token,
        x_access_secret=x_access_secret,
    )
