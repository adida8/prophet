"""API-Football client (api-sports.io direct endpoint).

Narrow surface — only the endpoints the desk actually consumes ship as
public helpers. v1 wires:
  - `status` → account tier + daily quota (guardrail 4 check)
  - `teams`  → resolve canonical-id ↔ api-football numeric team_id
  - `fixtures` / `standings` / `injuries` (later PRs)
"""

from desk.data.api_football.cache import (
    APIFootballCache,
    FixtureResult,
    FormDelta,
    TeamResolution,
)
from desk.data.api_football.client import APIFootballClient, APIFootballError
from desk.data.api_football.refresh import RefreshOutcome, refresh_all, refresh_one
from desk.data.api_football.runtime import APIFootballRuntime, default_cache_path
from desk.data.api_football.status import AccountStatus, fetch_status

__all__ = [
    "APIFootballCache",
    "APIFootballClient",
    "APIFootballError",
    "APIFootballRuntime",
    "AccountStatus",
    "FixtureResult",
    "FormDelta",
    "RefreshOutcome",
    "TeamResolution",
    "default_cache_path",
    "fetch_status",
    "refresh_all",
    "refresh_one",
]
