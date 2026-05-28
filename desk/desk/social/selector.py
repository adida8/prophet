"""Daily + weekly selectors.

Pure functions over a list of `MatchOutput`. The runner is responsible
for loading those off disk via `Publisher.read_match`; the selector
never touches the filesystem. Keeps unit tests trivial (inject a list,
assert the picked one) and the selector itself sport-agnostic.

`select_daily_pick` returns the highest-conviction Pick of the day. If
nothing qualifies the function returns None — we never draft for the
sake of drafting. Spec rules in order:

  1. verdict.state == "pick"
  2. selector_edge_pp >= min_edge_pp   (default 2.0)
  3. kickoff_utc > now                 (haven't kicked off yet)
  4. already_drafted_match_ids miss     (idempotent across reruns)
  5. sort by selector_edge_pp desc, return top

`selector_edge_pp` prefers `verdict.lower_edge_pp` when present (Phase
A.3 multi-window persistence) and falls back to `verdict.edge_pp` —
the data-layer evolved past lower_edge_pp being mandatory and the
selector should keep working on legacy MatchOutputs.

`build_weekly_roundup` takes the trailing-week published set + a
resolved-outcomes lookup and builds a frozen `WeeklyRoundupPayload`.
The "what we got wrong" row is the highest-conviction resolved Pick
that lost; if every Pick won (or none resolved) it stays None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

from desk.publish.contract import MatchOutput, VerdictState
from desk.social.models import (
    DraftKind,
    RoundupPick,
    ResolvedPick,
    WeeklyRoundupPayload,
)


# Sentinel for "no edge data" — sort below every numeric edge.
_NO_EDGE = float("-inf")


def _selector_edge(match: MatchOutput) -> float:
    """Read the conviction-ordering edge off a MatchOutput.

    The published contract exposes `edge_pp` on every Pick. Some live
    paths also stash a `lower_edge_pp` (bootstrap CI lower bound)
    elsewhere — we honour it via duck typing when present, since
    `Verdict.model_extra` would have surfaced it if validated under
    extra='allow'. Default contract is extra='forbid' so we just read
    edge_pp directly. Returns float('-inf') when missing.
    """
    v = match.verdict
    edge = getattr(v, "edge_pp", None)
    if edge is None:
        return _NO_EDGE
    return float(edge)


def _is_pick(match: MatchOutput) -> bool:
    v = match.verdict
    # MatchOutput uses use_enum_values=True so state may be a raw str
    # already. Compare against both shapes for safety.
    return v.state == VerdictState.PICK.value or v.state == VerdictState.PICK


def select_daily_pick(
    matches: Iterable[MatchOutput],
    *,
    now: datetime,
    min_edge_pp: float = 2.0,
    already_drafted_match_ids: set[str] | frozenset[str] = frozenset(),
) -> Optional[MatchOutput]:
    """Return the highest-conviction Pick of the day, or None."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware UTC")
    candidates: list[MatchOutput] = []
    for m in matches:
        if not _is_pick(m):
            continue
        edge = _selector_edge(m)
        if edge < min_edge_pp:
            continue
        if m.kickoff_utc <= now:
            continue
        if m.match_id in already_drafted_match_ids:
            continue
        candidates.append(m)
    if not candidates:
        return None
    candidates.sort(key=_selector_edge, reverse=True)
    return candidates[0]


# ── Weekly roundup ────────────────────────────────────────────────────


@dataclass(frozen=True)
class WeekWindow:
    """The 7-day window the roundup covers. UTC; Mon 00:00 → Sun 23:59:59.

    Stored as date-only on the roundup payload (`week_starting`) so the
    queue's per-week uniqueness key is human-readable.
    """
    start: datetime
    end:   datetime
    week_starting: date


def week_window_for(now: datetime) -> WeekWindow:
    """Compute the trailing-week window ending at the most recent
    Sunday 23:59:59 UTC.

    Sunday job runs in the morning UTC — by then the previous calendar
    week (Mon–Sun) is complete. We freeze the entire previous week to
    avoid double-counting any "today" data.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware UTC")
    # `now` is most often Sunday morning. We want the week that just
    # ended — Monday of last week through Sunday of last week. If `now`
    # *is* Sunday, the most recent completed Sunday is yesterday's date.
    today = now.date()
    weekday = today.weekday()        # Mon=0 … Sun=6
    # Days since last Monday (the start of the week we're closing out).
    days_since_monday = weekday + 7  # always look at the previous week
    start_date = today - timedelta(days=days_since_monday)
    end_date   = start_date + timedelta(days=6)
    start_dt = datetime(start_date.year, start_date.month, start_date.day,
                        0, 0, 0, tzinfo=timezone.utc)
    end_dt   = datetime(end_date.year, end_date.month, end_date.day,
                        23, 59, 59, tzinfo=timezone.utc)
    return WeekWindow(start=start_dt, end=end_dt, week_starting=start_date)


OutcomeLookup = Callable[[str], Optional[bool]]
"""`outcome_lookup(match_id) → True` if Pick side won, False if lost,
None if not yet resolved. Implementations live in the runner — we
inject so the selector stays pure."""


def build_weekly_roundup(
    published_matches: Iterable[MatchOutput],
    *,
    window: WeekWindow,
    outcome_lookup: OutcomeLookup,
    top_n: int = 5,
) -> WeeklyRoundupPayload:
    """Build the structured payload backing a Sunday roundup carousel."""
    picks_in_window: list[MatchOutput] = []
    for m in published_matches:
        if not _is_pick(m):
            continue
        ko = m.kickoff_utc
        if ko < window.start or ko > window.end:
            continue
        picks_in_window.append(m)

    picks_in_window.sort(key=_selector_edge, reverse=True)
    top_matches = picks_in_window[:top_n]
    top_picks = [
        RoundupPick(
            match_id   = m.match_id,
            team_a     = m.team_a,
            team_b     = m.team_b,
            pick_side  = m.verdict.side or "",
            edge_pp    = _selector_edge(m),
            kickoff_utc= m.kickoff_utc,
        )
        for m in top_matches
        if m.verdict.side  # has-side check; Pick invariants guarantee non-null
    ]

    # Hit-rate over every Pick in the window that has resolved.
    resolved: list[tuple[MatchOutput, bool]] = []
    for m in picks_in_window:
        won = outcome_lookup(m.match_id)
        if won is None:
            continue
        resolved.append((m, won))

    sample_size = len(resolved)
    hit_rate    = round(sum(1 for _, w in resolved if w) / sample_size, 4) \
                  if sample_size else None

    # "What we got wrong": the highest-conviction losing Pick.
    losing = [(m, w) for m, w in resolved if not w]
    losing.sort(key=lambda mw: _selector_edge(mw[0]), reverse=True)
    wrong: ResolvedPick | None = None
    if losing:
        m, _ = losing[0]
        wrong = ResolvedPick(
            match_id  = m.match_id,
            pick_side = m.verdict.side or "",
            edge_pp   = _selector_edge(m),
            won       = False,
        )

    return WeeklyRoundupPayload(
        week_starting        = window.week_starting,
        top_picks            = top_picks,
        hit_rate             = hit_rate,
        hit_rate_sample_size = sample_size,
        what_we_got_wrong    = wrong,
    )


# ── id helpers ────────────────────────────────────────────────────────


def daily_draft_id(match: MatchOutput, *, now: datetime) -> str:
    """Compose the deterministic draft_id used for the daily kind."""
    # `now` is when the selector ran (used as the date prefix so the id
    # sort-orders by draft-run, not match kickoff). Match-id includes
    # team codes + match date already, which is what we need for the
    # operator-readable suffix.
    return f"soc-{DraftKind.DAILY.value}-{now.strftime('%Y%m%d')}-{match.match_id}"


def weekly_draft_id(week_starting: date) -> str:
    return (f"soc-{DraftKind.WEEKLY_ROUNDUP.value}-"
            f"{week_starting.strftime('%Y%m%d')}")
