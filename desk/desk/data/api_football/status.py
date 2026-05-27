"""GET /status — the cheapest call api-football offers.

Used as the boot-time / CLI smoke check that closes guardrail 4 of
`THE_DESK_DATA_LAYER_SPEC.md`: "API-Football, OpenWeatherMap, and
Railway assumptions in §4 / §3.4 are verified against current vendor
terms before any code is written." Reports the operator's actual plan
tier and quotas — the spec talks about a $19/mo "Pro" plan; this is
how we verify the live account matches.

Response shape (truncated, as of 2026-05-15):

    {
      "get": "status",
      "parameters": [],
      "errors": [],
      "results": 1,
      "response": {
        "account": {"firstname": "...", "lastname": "...", "email": "..."},
        "subscription": {"plan": "Pro", "end": "2027-05-15T00:00:00+00:00",
                         "active": true},
        "requests": {"current": 12, "limit_day": 7500}
      }
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desk.data.api_football.client import APIFootballClient


@dataclass(frozen=True)
class AccountStatus:
    plan_name:      str        # "Free", "Pro", "Ultra", ...
    plan_active:    bool
    plan_end:       str | None  # ISO-8601 from api-football; None if absent
    requests_today: int        # subscription.requests.current
    limit_per_day:  int        # subscription.requests.limit_day
    email:          str | None  # for human verification; censored downstream

    @property
    def is_pro_or_higher(self) -> bool:
        """The spec's $19/mo spine assumes the Pro tier at 7,500 req/day.
        Anything Pro+ clears that bar. The Free tier (100 req/day) does
        not — useful for B.1 form/rank smoke-tests only.
        """
        return self.limit_per_day >= 1_000

    def headline(self) -> str:
        """One-line human summary for the CLI smoke check."""
        active = "active" if self.plan_active else "INACTIVE"
        return (
            f"api-football · plan={self.plan_name} ({active}) · "
            f"quota={self.requests_today}/{self.limit_per_day}/day"
        )


async def fetch_status(client: APIFootballClient) -> AccountStatus:
    resp = await client.get("/status")
    payload: dict[str, Any] = resp.payload.get("response") or {}
    subscription = payload.get("subscription") or {}
    requests = payload.get("requests") or {}
    account = payload.get("account") or {}

    return AccountStatus(
        plan_name=str(subscription.get("plan") or "unknown"),
        plan_active=bool(subscription.get("active", False)),
        plan_end=subscription.get("end"),
        requests_today=int(requests.get("current") or 0),
        limit_per_day=int(requests.get("limit_day") or 0),
        email=account.get("email"),
    )
