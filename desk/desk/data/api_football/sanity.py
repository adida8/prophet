"""Plausibility checks for api-football data before it reaches features.

Per data-layer spec §3.7: freshness + citation alone don't catch wrong
data, and wrong data with a clean timestamp is the worst failure mode
for a credibility engine. Every Datum passes plausibility checks
before the feature-assembly layer accepts it.

Three checks shipped for v1 (Phase 2 / form):

* `check_fixture` — fixture played_at must be in the past + within a
  plausible recency window (last 5 years; older than that suggests
  api-football returned a wrong-team or wrong-endpoint payload).
* `check_entity_match` — when fetching team X's fixtures, the returned
  fixture must have team X on one side. Catches cross-wiring.
* `check_form_delta_range` — derived form_delta within plausible
  bounds [-2.0, +2.0]. Baseline is 1.5 PPG and per-game extremes are
  [0, 3] PPG, so anything outside [-2, +2] is a math bug or a corrupt
  fixture set.

Failures return a reason string per spec §3.1 — "outside_window",
"entity_mismatch", "failed_sanity". The caller marks the datum
**absent** with that reason; it never silently feeds the model.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from desk.data.api_football.cache import FixtureResult

# Reason codes — match the data-layer spec §3.1 vocabulary so absent
# features can be aggregated across the layer.
REASON_OK:               str = "ok"
REASON_OUTSIDE_WINDOW:   str = "outside_window"
REASON_ENTITY_MISMATCH:  str = "entity_mismatch"
REASON_FAILED_SANITY:    str = "failed_sanity"

# Plausibility windows.
MAX_FIXTURE_AGE = timedelta(days=5 * 365)
FORM_DELTA_MIN: float = -2.0
FORM_DELTA_MAX: float = +2.0


def check_fixture(f: FixtureResult, *, now: datetime | None = None) -> str:
    """Return REASON_OK or one of the reason codes."""
    now = now or datetime.now(tz=timezone.utc)
    if f.played_at > now + timedelta(hours=1):
        # Played time in the future (allowing 1h clock skew tolerance)
        # — api-football returned an upcoming fixture instead of a
        # completed one, or our /fixtures?last=N call misfired.
        return REASON_OUTSIDE_WINDOW
    if (now - f.played_at) > MAX_FIXTURE_AGE:
        return REASON_OUTSIDE_WINDOW
    if f.team_goals is not None and f.team_goals < 0:
        return REASON_FAILED_SANITY
    if f.opponent_goals is not None and f.opponent_goals < 0:
        return REASON_FAILED_SANITY
    return REASON_OK


def check_entity_match(f: FixtureResult, requested_team_id: int) -> str:
    """The fetched team_id must appear on the fixture (we already
    normalise the perspective in fixtures.py, so the resulting row
    carries the requested team_id verbatim). This double-checks the
    invariant before the row reaches the cache — defensive against
    upstream changes."""
    if f.api_football_team_id != requested_team_id:
        return REASON_ENTITY_MISMATCH
    return REASON_OK


def check_form_delta_range(form_delta: float) -> str:
    """Range sanity on the derived form_delta scalar."""
    if not (FORM_DELTA_MIN <= form_delta <= FORM_DELTA_MAX):
        return REASON_FAILED_SANITY
    return REASON_OK


# Plausibility caps for card counts. A season total outside [0, 20]
# yellows or [0, 10] reds is a data error. Mirrors the per-row drop in
# `cards.py:_sane_row`; surfaced here so the squad-paragraph reconcile
# can reject pathological derivations consistently.
CARDS_MAX_YELLOWS: int = 20
CARDS_MAX_REDS:    int = 10


def check_card_counts(yellows: int, reds: int) -> str:
    """Range sanity on per-player card counts. Reject negative or
    implausibly large values (per spec §Q1 sanity gates)."""
    if yellows < 0 or reds < 0:
        return REASON_FAILED_SANITY
    if yellows > CARDS_MAX_YELLOWS or reds > CARDS_MAX_REDS:
        return REASON_FAILED_SANITY
    return REASON_OK


def check_at_risk_not_suspended(
    *, player_id: int, suspended_player_ids: set[int],
) -> str:
    """A player flagged `at_risk` cannot also be in the team's current
    suspension set — they're already a confirmed absence (per spec §Q1
    sanity gates: "prefer the suspension"). Caller drops the at_risk
    flag for any player_id this check rejects."""
    if player_id in suspended_player_ids:
        return REASON_FAILED_SANITY
    return REASON_OK
