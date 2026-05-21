"""Football hard-signal → bounded Elo adjustment.

The biggest Brier lever per `THE_DESK_OPTIMIZATION_SPEC.md` Phase B:
high-trust injury / suspension / confirmed-XI signals from the news
pipeline nudge each team's Elo before the model runs.

Three rules from the news-signals spec §9:

  * **Late-binding** — only apply inside the final N days before
    kickoff (default 5). Outside the window we ignore the signal — a
    transfer-window narrative about Mbappé in June shouldn't be moving
    a March match.
  * **Bounded + auditable** — every adjustment is capped per signal
    *and* per team. The audit log carries the originating Signal so
    PR 5's explainer can write "the model accounts for Mbappé's
    absence" with a real citation.
  * **Markets stay out** — hard signals are feature inputs, not
    market data. Nothing here looks at prices.

`predicted_lineup` is editorial, not hard, and is filtered out at
extraction by `Signal.track()`. `confirmed_lineup` is admitted but
applies no Elo change in v1 — the signal mostly tells us our XI guess
was right, so it tightens uncertainty rather than moving the central
estimate. A later PR may apply a small refinement.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal

from desk.signals.models import Signal, SignalType, Source
from desk.sport import FixtureRef
from desk.sports.football.model import FootballFeatures

_LOG = logging.getLogger(__name__)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        _LOG.warning("ignoring non-float %s=%r (default %s)", name, raw, default)
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        _LOG.warning("ignoring non-int %s=%r (default %s)", name, raw, default)
        return default


# Per-signal magnitudes. Modest by design — the model is the central
# estimate, signals nudge. Override via env for experiments.
INJURY_ELO_PENALTY     = _float_env("DESK_HARD_SIGNAL_INJURY_ELO",     8.0)
SUSPENSION_ELO_PENALTY = _float_env("DESK_HARD_SIGNAL_SUSPENSION_ELO", 6.0)
MAX_TOTAL_PENALTY_ELO  = _float_env("DESK_HARD_SIGNAL_MAX_ELO",        30.0)
LATE_BINDING_DAYS      = _int_env  ("DESK_HARD_SIGNAL_WINDOW_DAYS",    5)


Side = Literal["a", "b"]


@dataclass(frozen=True)
class HardSignalAdjustment:
    """Audit row for one applied adjustment. PR 5's explainer reads
    these to write attributed prose; the runner logs them for ops."""

    side:        Side
    team:        str         # the fixture's team name
    delta_elo:   float       # negative ⇒ penalty
    capped:      bool        # True if the per-team cap clipped this row
    reason:      str         # short normalised claim from the Signal
    signal_url:  str
    signal_type: str         # e.g. "injury"
    source_id:   str


def _match_side(signal_team: str, *, team_a: str, team_b: str) -> Side | None:
    """Case-insensitive exact match of the signal's team to the fixture.
    Returns None when neither side matches; the caller drops the row.
    A later PR can extend this via the football teams registry."""
    norm = signal_team.strip().lower()
    if not norm:
        return None
    if norm == team_a.strip().lower():
        return "a"
    if norm == team_b.strip().lower():
        return "b"
    return None


def _per_signal_delta(signal: Signal) -> float:
    if signal.type == SignalType.INJURY:
        return -INJURY_ELO_PENALTY
    if signal.type == SignalType.SUSPENSION:
        return -SUSPENSION_ELO_PENALTY
    # confirmed_lineup carries no Elo delta in v1 — see module docstring.
    return 0.0


def within_late_binding_window(
    *, kickoff_utc: datetime, now: datetime,
    window: timedelta = timedelta(days=LATE_BINDING_DAYS),
) -> bool:
    """True iff kickoff is in the future AND within the window. Past
    kickoffs are filtered for safety — there shouldn't be priced
    fixtures in the past, but the model never needs to know about a
    match that's already happened."""
    delta = kickoff_utc - now
    return timedelta(0) < delta <= window


def apply_hard_signals(
    features: FootballFeatures,
    *,
    fx: FixtureRef,
    signals: Iterable[tuple[Signal, Source]],
    now: datetime | None = None,
    window: timedelta | None = None,
    max_total: float = MAX_TOTAL_PENALTY_ELO,
) -> tuple[FootballFeatures, list[HardSignalAdjustment]]:
    """Return adjusted features + audit log. A no-op (returns the
    input features unchanged) when outside the late-binding window
    or when no signal matches either team."""
    now = now or datetime.now(tz=timezone.utc)
    eff_window = window if window is not None else timedelta(days=LATE_BINDING_DAYS)

    if not within_late_binding_window(kickoff_utc=fx.kickoff_utc, now=now, window=eff_window):
        return features, []

    # Tally per-side cumulative delta, clipping at the per-team cap.
    deltas: dict[Side, float] = {"a": 0.0, "b": 0.0}
    audit:  list[HardSignalAdjustment] = []

    for signal, source in signals:
        side = _match_side(signal.team, team_a=fx.team_a, team_b=fx.team_b)
        if side is None:
            _LOG.debug(
                "hard signal team %r matches neither side of %s — dropping",
                signal.team, fx.match_id,
            )
            continue
        delta = _per_signal_delta(signal)
        if delta == 0.0:
            continue
        proposed = deltas[side] + delta
        capped   = False
        # Per-team cap: total penalty can't exceed -max_total.
        if proposed < -max_total:
            applied = -max_total - deltas[side]
            capped  = True
            deltas[side] = -max_total
        else:
            applied = delta
            deltas[side] = proposed
        audit.append(HardSignalAdjustment(
            side=side,
            team=fx.team_a if side == "a" else fx.team_b,
            delta_elo=applied,
            capped=capped,
            reason=signal.claim,
            signal_url=signal.url,
            signal_type=signal.type.value if hasattr(signal.type, "value") else str(signal.type),
            source_id=source.id,
        ))

    if deltas["a"] == 0.0 and deltas["b"] == 0.0:
        return features, audit

    adjusted = replace(
        features,
        team_a_elo=features.team_a_elo + deltas["a"],
        team_b_elo=features.team_b_elo + deltas["b"],
    )
    return adjusted, audit
