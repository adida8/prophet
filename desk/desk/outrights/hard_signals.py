"""Apply hard-track signals to per-team Elo for the outright sim.

Mirrors `desk/sports/football/hard_signals.py` for the per-team-binary
outright market. Two differences from the match path:

  * **No late-binding window.** A confirmed injury weeks ahead of the
    tournament absolutely matters for outright odds — squads firm up
    in the weeks before the World Cup. The recency cap inside
    `desk.signals.hard_track.hard_signals_for` (7-day default) is
    sufficient on its own; the match-path's 5-day window is a
    fixture-specific concern that doesn't transfer.
  * **Many teams, not two.** Each signal is matched against the full
    field; a non-match drops the row.

Per-signal magnitudes and the per-team cap are imported from the
match-path module so a single env override (`DESK_HARD_SIGNAL_*`)
changes both pipelines together.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from desk.signals.models import Signal, SignalType, Source
from desk.sports.football.hard_signals import (
    INJURY_ELO_PENALTY,
    MAX_TOTAL_PENALTY_ELO,
    SUSPENSION_ELO_PENALTY,
)
from desk.sports.football.teams import iso3_for_name

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutrightHardSignalAdjustment:
    """Audit row for one applied adjustment. Surfaced on the published
    JSON's `model.hard_signal_adjustments` so a reader can answer
    'why did Argentina's number move?' without grepping logs."""

    team:         str
    delta_elo:    float        # negative ⇒ penalty
    capped:       bool         # True if the per-team cap clipped this row
    reason:       str          # short normalised claim from the Signal
    signal_url:   str
    signal_type:  str
    source_id:    str
    source_name:  str | None = None
    published_at: datetime | None = None


def _per_signal_delta(signal: Signal) -> float:
    if signal.type == SignalType.INJURY:
        return -INJURY_ELO_PENALTY
    if signal.type == SignalType.SUSPENSION:
        return -SUSPENSION_ELO_PENALTY
    # confirmed_lineup carries no Elo delta in v1 — same as the match
    # path. Tightens uncertainty, doesn't move the central estimate.
    return 0.0


def _match_team(signal_team: str, field: tuple[str, ...]) -> str | None:
    """Match a signal's `team` string to a canonical name in the field.

    Tries two routes in order:
      1. Case-insensitive exact match — covers the common case where the
         extractor returned a name verbatim from the article.
      2. ISO3 resolution via the football team registry — handles
         aliases like "United States" ↔ "USA", "South Korea" ↔
         "Korea Republic", "Ivory Coast" ↔ "Côte d'Ivoire". Returns
         the *field*'s canonical spelling so downstream Elo lookup hits.

    Returns None when neither route resolves; the caller drops the row.
    """
    norm = signal_team.strip().lower()
    if not norm:
        return None
    for team in field:
        if team.strip().lower() == norm:
            return team
    sig_iso3 = iso3_for_name(signal_team)
    if not sig_iso3:
        return None
    for team in field:
        if iso3_for_name(team) == sig_iso3:
            return team
    return None


def apply_hard_signals(
    field: tuple[str, ...],
    *,
    signals: Iterable[tuple[Signal, Source]],
    max_total: float = MAX_TOTAL_PENALTY_ELO,
) -> tuple[dict[str, float], list[OutrightHardSignalAdjustment]]:
    """Return (per-team Elo delta, audit log).

    The delta dict only contains teams with a non-zero net adjustment.
    Outright `run.run_once` adds it on top of seed Elo before the sim.
    """
    deltas: dict[str, float] = {}
    audit:  list[OutrightHardSignalAdjustment] = []

    for signal, source in signals:
        team = _match_team(signal.team, field)
        if team is None:
            _LOG.debug(
                "hard signal team %r matches no team in field — dropping",
                signal.team,
            )
            continue
        delta = _per_signal_delta(signal)
        if delta == 0.0:
            continue
        current  = deltas.get(team, 0.0)
        proposed = current + delta
        capped   = False
        if proposed < -max_total:
            applied = -max_total - current
            deltas[team] = -max_total
            capped = True
        else:
            applied = delta
            deltas[team] = proposed
        audit.append(OutrightHardSignalAdjustment(
            team=team,
            delta_elo=applied,
            capped=capped,
            reason=signal.claim,
            signal_url=signal.url,
            signal_type=signal.type.value if hasattr(signal.type, "value") else str(signal.type),
            source_id=source.id,
            source_name=source.name,
            published_at=signal.published_at,
        ))

    return deltas, audit
