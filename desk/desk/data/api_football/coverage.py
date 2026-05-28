"""Coverage report — what fraction of priced WC26 fixtures resolve to
form_delta in the cache?

Per data-layer spec §3.3: a competition does not go live until its
alias coverage clears a two-part floor — **≥95% of its known teams**
*and* **≥98% of the priced fixtures in the next publish window** resolve
across all required tier-1 sources.

For Phase B.1 the only required tier-1 source is api-football's
form_delta path. This module computes both metrics + emits a
`CoverageReport`. The runner logs a WARN if either floor isn't cleared
— for v1 we don't *block* publication (matches still ship; form_delta
is just absent for the unresolved teams), but the warning is the
discipline gate that the spec demands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from desk.data.api_football.cache import APIFootballCache
from desk.data.api_football.wc26_registry import WC26_NATIONAL_REGISTRY

# Spec §3.3 floors.
TEAM_COVERAGE_FLOOR_PCT:    float = 95.0
FIXTURE_COVERAGE_FLOOR_PCT: float = 98.0


@dataclass(frozen=True)
class CoverageReport:
    competition_code:  str

    # Team-side coverage: of every known WC26 team, how many have a
    # form_delta value in the cache.
    teams_total:       int
    teams_covered:     int
    teams_uncovered:   tuple[str, ...]      # iso3s missing

    # Fixture-side coverage: of every priced fixture about to publish,
    # how many have form_delta cached for both teams. A fixture
    # "uncovered" means at least one side is missing.
    fixtures_total:    int
    fixtures_covered:  int
    fixtures_uncovered: tuple[str, ...]     # match_ids missing

    @property
    def team_coverage_pct(self) -> float:
        return 100.0 * self.teams_covered / self.teams_total if self.teams_total else 0.0

    @property
    def fixture_coverage_pct(self) -> float:
        return 100.0 * self.fixtures_covered / self.fixtures_total if self.fixtures_total else 0.0

    @property
    def teams_floor_cleared(self) -> bool:
        return self.team_coverage_pct >= TEAM_COVERAGE_FLOOR_PCT

    @property
    def fixtures_floor_cleared(self) -> bool:
        return self.fixture_coverage_pct >= FIXTURE_COVERAGE_FLOOR_PCT

    @property
    def both_floors_cleared(self) -> bool:
        return self.teams_floor_cleared and self.fixtures_floor_cleared

    def headline(self) -> str:
        team_ok = "✓" if self.teams_floor_cleared else "✗"
        fix_ok  = "✓" if self.fixtures_floor_cleared else "✗"
        return (
            f"api-football coverage [{self.competition_code}] · "
            f"teams {team_ok} {self.teams_covered}/{self.teams_total} "
            f"({self.team_coverage_pct:.1f}%) · "
            f"fixtures {fix_ok} {self.fixtures_covered}/{self.fixtures_total} "
            f"({self.fixture_coverage_pct:.1f}%)"
        )


def build_coverage_report(
    *,
    cache: APIFootballCache,
    competition_code: str,
    priced_fixture_iso3_pairs: list[tuple[str, str, str]],
) -> CoverageReport:
    """Compute a coverage report.

    `priced_fixture_iso3_pairs` is `(match_id, iso3_a, iso3_b)` for
    every fixture about to publish. Either iso3 may be empty when the
    fixture isn't a WC26 international (clubs, friendlies); those
    fixtures are excluded from the denominator (not "uncovered").
    """
    teams_uncovered: list[str] = []
    for iso3 in WC26_NATIONAL_REGISTRY:
        if cache.form_delta_for_iso3(iso3) is None:
            teams_uncovered.append(iso3)
    teams_total = len(WC26_NATIONAL_REGISTRY)
    teams_covered = teams_total - len(teams_uncovered)

    fixtures_uncovered: list[str] = []
    fixtures_total = 0
    fixtures_covered = 0
    for match_id, iso3_a, iso3_b in priced_fixture_iso3_pairs:
        # Skip non-WC26-international fixtures — clubs etc. aren't in
        # the registry and therefore aren't in scope for this report.
        if (iso3_a not in WC26_NATIONAL_REGISTRY
                or iso3_b not in WC26_NATIONAL_REGISTRY):
            continue
        fixtures_total += 1
        if (cache.form_delta_for_iso3(iso3_a) is not None
                and cache.form_delta_for_iso3(iso3_b) is not None):
            fixtures_covered += 1
        else:
            fixtures_uncovered.append(match_id)

    return CoverageReport(
        competition_code=competition_code,
        teams_total=teams_total,
        teams_covered=teams_covered,
        teams_uncovered=tuple(sorted(teams_uncovered)),
        fixtures_total=fixtures_total,
        fixtures_covered=fixtures_covered,
        fixtures_uncovered=tuple(fixtures_uncovered),
    )
