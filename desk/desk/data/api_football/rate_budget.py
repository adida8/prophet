"""Rate-budget instrumentation for the api-football spine.

Data-layer spec §4.1 acceptance: "an instrumented worst-case
fixture-density estimate is produced and shown to fit inside every
source's cap with headroom for retries."

Walks the cadences declared in spec §3.6 + the wire-up in
`desk_refresh_loop.py` and produces a per-call-class daily count. The
operator + reviewers see the math, not a handwave.

Outputs the totals required by spec §4.1:
  - api-football daily-cap headroom
  - Per-call breakdown (teams resolution + fixtures fetch + future
    injuries/lineups slots)
"""

from __future__ import annotations

from dataclasses import dataclass

from desk.data.api_football.wc26_registry import WC26_NATIONAL_REGISTRY

# api-football Pro plan ceiling — verified against the vendor's
# /status endpoint payload (see `desk verify-data-sources`).
PRO_DAILY_CAP: int = 7_500


@dataclass(frozen=True)
class RateBudgetLine:
    """One call-class budget line — endpoint, cadence, calls/day."""
    label:        str
    endpoint:     str
    cadence_desc: str
    calls_per_day: int
    phase:        str


@dataclass(frozen=True)
class RateBudgetReport:
    lines:         tuple[RateBudgetLine, ...]
    daily_cap:     int = PRO_DAILY_CAP

    @property
    def total_calls_per_day(self) -> int:
        return sum(l.calls_per_day for l in self.lines)

    @property
    def headroom_pct(self) -> float:
        used = self.total_calls_per_day / self.daily_cap if self.daily_cap else 0.0
        return max(0.0, 100.0 * (1.0 - used))

    @property
    def within_cap(self) -> bool:
        return self.total_calls_per_day <= self.daily_cap

    def headline(self) -> str:
        cap_ok = "✓" if self.within_cap else "✗"
        return (
            f"api-football rate budget · {cap_ok} "
            f"{self.total_calls_per_day} / {self.daily_cap} req/day "
            f"({self.headroom_pct:.1f}% headroom)"
        )


def build_report(
    *,
    fetch_ticks_per_day: int = 1,
    daily_cap: int = PRO_DAILY_CAP,
) -> RateBudgetReport:
    """Calculate the worst-case daily-call estimate.

    `fetch_ticks_per_day` is how many times `desk fetch-rank-form`
    runs in a 24h window. The refresh loop ships at 1 tick/day by
    default (see `desk_refresh_loop.py`'s scheduled hours).
    """
    n_teams = len(WC26_NATIONAL_REGISTRY)

    lines = [
        RateBudgetLine(
            label="team-id resolution (one-off)",
            endpoint="/teams?search=...",
            cadence_desc=f"~{n_teams} calls total across cold-start ticks; "
                         "cached afterwards",
            calls_per_day=n_teams,   # cold-start worst case
            phase="B.1 / one-off",
        ),
        RateBudgetLine(
            label="form / last-N fixtures (per team)",
            endpoint="/fixtures?team=X&last=10",
            cadence_desc=f"{n_teams} teams × {fetch_ticks_per_day} tick(s)/day",
            calls_per_day=n_teams * fetch_ticks_per_day,
            phase="B.1",
        ),
        # Reserved slots for future B.3 (injuries) and B.3 (lineups).
        # Listed at 0 calls/day so the report ages with the codebase
        # — adding an injuries fetcher updates this line and the
        # operator sees the cap impact immediately.
        RateBudgetLine(
            label="injuries (reserved for B.3)",
            endpoint="/injuries?team=X&date=Y",
            cadence_desc="per team, every 6-12h inside T-3d (not wired in v1)",
            calls_per_day=0,
            phase="B.3 (reserved)",
        ),
        RateBudgetLine(
            label="lineups (reserved for B.3)",
            endpoint="/fixtures/lineups?fixture=X",
            cadence_desc="per fixture, hourly inside T-1h (not wired in v1)",
            calls_per_day=0,
            phase="B.3 (reserved)",
        ),
    ]
    return RateBudgetReport(lines=tuple(lines), daily_cap=daily_cap)
