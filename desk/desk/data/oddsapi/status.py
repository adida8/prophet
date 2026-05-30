"""GET /v4/sports — the cheapest call The Odds API offers.

Used as the boot-time / CLI smoke check. Reports the operator's quota
position so we know how many credits the live fetch can spend before
the monthly plan blows.

Response shape (truncated):

    [
      {"key": "soccer_epl",          "active": true,  "group": "Soccer",
       "title": "EPL",               "description": "...", ...},
      ...
    ]

Headers (only present when the call has a real apiKey):
    x-requests-remaining: 487
    x-requests-used:       13
    x-requests-last:        1
"""

from __future__ import annotations

from dataclasses import dataclass

from desk.data.oddsapi.client import OddsAPIClient, OddsAPIRateLimit


@dataclass(frozen=True)
class QuotaStatus:
    """Snapshot of the operator's Odds API quota at probe time."""
    requests_remaining: int | None
    requests_used:      int | None
    sports_available:   int

    @property
    def key_ok(self) -> bool:
        """The probe only succeeds when the key is valid + the call
        returned a non-empty sports list. Headers are best-effort."""
        return self.sports_available > 0

    def headline(self) -> str:
        rem = self.requests_remaining if self.requests_remaining is not None else "?"
        used = self.requests_used if self.requests_used is not None else "?"
        return (
            f"odds-api · sports={self.sports_available} · "
            f"quota={used}/{rem} (used/remaining)"
        )


async def fetch_quota_status(client: OddsAPIClient) -> QuotaStatus:
    """Probe `/v4/sports`. Returns a `QuotaStatus`; lets the caller
    decide whether to proceed (e.g. only run the daily refresh when
    `quota.requests_remaining` is over some floor)."""
    resp = await client.get("/v4/sports", params={"all": "false"})
    payload = resp.payload if isinstance(resp.payload, list) else []
    snap: OddsAPIRateLimit | None = resp.rate_limit
    return QuotaStatus(
        requests_remaining=(snap.requests_remaining if snap is not None else None),
        requests_used=(snap.requests_used if snap is not None else None),
        sports_available=len(payload),
    )
