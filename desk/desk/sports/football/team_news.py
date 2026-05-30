"""Team-news payload + builder — Slice A of the team-news blurb spec.

Aggregates everything the blurb writer needs about one team's
availability into a single structured object: who's missing, why,
which source said so, plus lineup status when it lands.

Two existing data paths feed in:

  * **api-football injuries cache** — `InjuryRow`s already fetched by
    `desk fetch-injuries` (Phase B.3 data side). Authoritative for
    *who is out*, but not an editorial outlet — the blurb states these
    facts without press attribution.

  * **News-signals hard track** — `Signal(type=INJURY|SUSPENSION|
    CONFIRMED_LINEUP|PREDICTED_LINEUP)` from `can_feed_model` sources
    (Guardian, BBC, etc.). Carries citation URLs the blurb can attribute.

Dedupe rule: when both sources flag the same player, we prefer the
api-football structured row (it has the position) but carry the RSS
source_url so the blurb can attribute the story.

`materiality` is the directive for the Haiku prompt — see PR N4. Values:

    high   — must address in the blurb. Triggered by ≥1 GK/CB/captain
             absence OR an Elo penalty ≥30 OR ≥3 absences.
    medium — must address briefly. 10–30 Elo penalty OR ≥1 absence
             without high-importance flags.
    low    — optional. <10 Elo penalty, no GK/CB.
    none   — must NOT mention availability (no data).

The materiality magnitude is computed from the api-football
`InjuryPenalty.elo_penalty` (Phase B.3) when available, otherwise from
the count + position weights of the merged absence list.

Failures here are silent — the builder NEVER raises. A missing api-
football cache yields absences from RSS only; a missing RSS pool yields
absences from api-football only; both missing yields TeamNews with
materiality=none, the same as today's behaviour.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Literal

from desk.data.api_football.cache import InjuryRow
from desk.data.api_football.injury_penalty import COUNTED_INJURY_TYPES
from desk.signals.models import Signal, SignalType, Source
from desk.sport import FixtureRef
from desk.sports.football.teams import iso3_for_name

_LOG = logging.getLogger(__name__)

# Position-importance buckets the blurb writer cares about. Mirrors
# `injury_penalty.POSITION_WEIGHT` but maps to a coarser editorial
# label — the prompt needs "high / medium / low", not Elo weights.
_HIGH_IMPORTANCE_POSITIONS = frozenset({"Goalkeeper"})
_MEDIUM_IMPORTANCE_POSITIONS = frozenset({"Defender", "Midfielder", "Attacker"})

# Materiality thresholds. Tuned to "should the blurb talk about this?"
# rather than to Elo-impact symmetry — a side missing their first-choice
# goalkeeper is high-materiality regardless of how the Elo number lands.
_MATERIALITY_HIGH_ELO    = 30.0
_MATERIALITY_MEDIUM_ELO  = 10.0
_MATERIALITY_HIGH_COUNT  = 3


# ── payload types ───────────────────────────────────────────────────

@dataclass(frozen=True)
class PlayerAbsence:
    """One player ruled out of the fixture.

    `source` carries the upstream provider id:
      * "api-football" for an InjuryRow
      * the registered Source.id for a news Signal (e.g. "guardian-football")
    `source_url` is the deep link when source is an editorial outlet,
    None for api-football (which isn't a quotable outlet).
    """
    name:        str
    position:    str | None
    type:        Literal["injury", "suspension"]
    reason:      str | None
    source:      str
    source_url:  str | None
    source_name: str | None = None
    importance:  Literal["high", "medium", "low"] = "medium"


@dataclass(frozen=True)
class LineupStatus:
    """The fixture's lineup status from the team's side.

    `state="confirmed"` only when a trusted source has explicitly
    announced the XI (`Signal.type == CONFIRMED_LINEUP`) — predicted
    XIs from speculation pieces stay at `state="predicted"`. Absent
    information yields `state="unknown"`.
    """
    state:        Literal["confirmed", "predicted", "unknown"]
    formation:    str | None = None
    changes:      tuple[str, ...] = ()
    source:       str | None = None
    source_url:   str | None = None
    source_name:  str | None = None
    announced_at: datetime | None = None


@dataclass(frozen=True)
class TeamNews:
    """Per-team team-news payload threaded onto the explainer's Inputs."""
    team:        str
    absences:    tuple[PlayerAbsence, ...]
    lineup:      LineupStatus
    materiality: Literal["high", "medium", "low", "none"]


# ── builder ─────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    """NFD-normalise + lowercase a name so 'Vázquez' matches 'Vazquez'."""
    nfd = unicodedata.normalize("NFD", name or "")
    stripped = "".join(c for c in nfd if not unicodedata.combining(c))
    return stripped.strip().lower()


def _importance_for(position: str | None) -> Literal["high", "medium", "low"]:
    if not position:
        return "low"
    if position in _HIGH_IMPORTANCE_POSITIONS:
        return "high"
    if position in _MEDIUM_IMPORTANCE_POSITIONS:
        return "medium"
    return "low"


def _injury_row_to_absence(row: InjuryRow) -> PlayerAbsence | None:
    """Convert an api-football InjuryRow to a PlayerAbsence.

    Returns None for row types that don't count as availability impact
    (`Questionable`, etc.) — matches `injury_penalty.COUNTED_INJURY_TYPES`.
    """
    if row.type not in COUNTED_INJURY_TYPES:
        return None
    is_suspension = row.type == "Suspended"
    return PlayerAbsence(
        name=row.player_name or "",
        position=row.position,
        type="suspension" if is_suspension else "injury",
        reason=row.reason or None,
        source="api-football",
        source_url=None,
        source_name=None,
        importance=_importance_for(row.position),
    )


def _signal_to_absence(signal: Signal, source: Source) -> PlayerAbsence | None:
    """Convert a hard-track Signal to a PlayerAbsence when type matches.

    Signals don't carry player position directly — the claim text might
    ("calf strain"), but extracting it reliably is a separate job. We
    leave position=None and importance="medium" so the blurb still has
    a tag to anchor priority. api-football fills in the gap when both
    sources cover the same player.
    """
    if signal.type == SignalType.INJURY:
        kind: Literal["injury", "suspension"] = "injury"
    elif signal.type == SignalType.SUSPENSION:
        kind = "suspension"
    else:
        return None
    name = (signal.claim or "").strip()
    # The claim is usually the short normalised assertion: "Mbappé out".
    # Fall back to the source title if the extractor produced an empty
    # claim — a non-empty hint is better than dropping the row.
    if not name:
        return None
    return PlayerAbsence(
        name=name,
        position=None,
        type=kind,
        reason=None,
        source=source.id,
        source_url=signal.url,
        source_name=source.name,
        importance="medium",
    )


def _signal_to_lineup(signal: Signal, source: Source) -> LineupStatus | None:
    """Convert a CONFIRMED_LINEUP / PREDICTED_LINEUP signal to a LineupStatus.

    Formation extraction is best-effort — the extractor schema doesn't
    surface it as a structured field today. The blurb prompt explicitly
    handles `formation=None` by stating "official lineup confirms…"
    without naming the shape.
    """
    if signal.type == SignalType.CONFIRMED_LINEUP:
        state: Literal["confirmed", "predicted", "unknown"] = "confirmed"
    elif signal.type == SignalType.PREDICTED_LINEUP:
        state = "predicted"
    else:
        return None
    return LineupStatus(
        state=state,
        formation=None,
        changes=(),
        source=source.id,
        source_url=signal.url,
        source_name=source.name,
        announced_at=signal.published_at,
    )


def _merge_absences(
    api_rows: list[PlayerAbsence],
    sig_rows: list[PlayerAbsence],
) -> tuple[PlayerAbsence, ...]:
    """Merge api-football + RSS absence lists with dedupe.

    Strategy: walk api-football first (structured truth), then add RSS
    rows that don't match an existing player by normalised name. When
    they DO match, upgrade the api-football row to carry the RSS
    source_url so the blurb can attribute the story.
    """
    out: list[PlayerAbsence] = []
    api_by_key: dict[str, int] = {}  # normalised name → index in `out`

    for row in api_rows:
        key = _norm(row.name)
        if not key:
            continue
        if key in api_by_key:
            continue  # duplicate inside api-football — keep first
        api_by_key[key] = len(out)
        out.append(row)

    for sig in sig_rows:
        key = _norm(sig.name)
        if not key:
            continue
        if key in api_by_key:
            # Upgrade: api-football row gets RSS citation attached.
            idx = api_by_key[key]
            existing = out[idx]
            if existing.source_url is None and sig.source_url:
                out[idx] = PlayerAbsence(
                    name=existing.name,
                    position=existing.position,
                    type=existing.type,
                    reason=existing.reason,
                    source=sig.source,
                    source_url=sig.source_url,
                    source_name=sig.source_name,
                    importance=existing.importance,
                )
            continue
        # Sub-string match for RSS-only names against api-football
        # entries (handles "Mbappé" vs "Kylian Mbappé").
        upgraded = False
        for other_key, idx in api_by_key.items():
            if key and other_key and (key in other_key or other_key in key):
                existing = out[idx]
                if existing.source_url is None and sig.source_url:
                    out[idx] = PlayerAbsence(
                        name=existing.name,
                        position=existing.position,
                        type=existing.type,
                        reason=existing.reason,
                        source=sig.source,
                        source_url=sig.source_url,
                        source_name=sig.source_name,
                        importance=existing.importance,
                    )
                upgraded = True
                break
        if upgraded:
            continue
        # Genuinely new name from RSS.
        out.append(sig)
        api_by_key[key] = len(out) - 1

    return tuple(out)


def _materiality_for(
    absences: tuple[PlayerAbsence, ...],
    *,
    elo_penalty: float | None,
) -> Literal["high", "medium", "low", "none"]:
    """Decide how forcefully the blurb should address availability.

    Rules:
      * No absences and no Elo penalty → none.
      * Any GK / CB / captain absence → high.
      * Elo penalty ≥ 30 → high.
      * ≥ 3 absences → high.
      * Elo penalty 10–30 → medium.
      * Otherwise (some absences, low total impact) → low.
    """
    if not absences and not elo_penalty:
        return "none"
    if any(a.importance == "high" for a in absences):
        return "high"
    if elo_penalty is not None and elo_penalty >= _MATERIALITY_HIGH_ELO:
        return "high"
    if len(absences) >= _MATERIALITY_HIGH_COUNT:
        return "high"
    if elo_penalty is not None and elo_penalty >= _MATERIALITY_MEDIUM_ELO:
        return "medium"
    if absences:
        return "medium" if any(a.importance == "medium" for a in absences) else "low"
    return "low"


def build_team_news(
    *,
    team_name: str,
    iso3: str | None,
    injury_rows: list[InjuryRow] | None,
    signals: Iterable[tuple[Signal, Source]],
    elo_penalty: float | None,
) -> TeamNews:
    """Build the per-team payload threaded onto Inputs.

    Inputs:
      * `team_name` — display name as it appears on FixtureRef.team_a/_b.
      * `iso3` — canonical ISO3 used to filter signals to this side.
                 Pass None for club fixtures where iso3 isn't applicable.
      * `injury_rows` — api-football InjuryRow list for this team's
                 resolved api-football team_id, or None when the cache
                 doesn't carry the team yet.
      * `signals` — the full (Signal, Source) list resolved for the
                 fixture (the same list `apply_hard_signals` saw).
                 The builder filters to this team's signals by
                 case-insensitive team-name match.
      * `elo_penalty` — the api-football B.3 Elo penalty already cached
                 for this side. Drives the materiality threshold when
                 absences are missing position data.
    """
    # Per-team filter on the signal pool. Hard-track signals carry the
    # team name as the extractor saw it; matching tolerates case +
    # whitespace. Outright wrong-side bindings are dropped here too.
    norm_team = _norm(team_name)
    norm_iso3 = (iso3 or "").strip().lower()
    sig_absences: list[PlayerAbsence] = []
    lineup: LineupStatus = LineupStatus(state="unknown")
    best_lineup_rank = -1  # confirmed (2) > predicted (1) > unknown (0)

    for signal, source in signals:
        sig_team = _norm(signal.team)
        if not sig_team:
            continue
        # Accept matches on display name OR ISO3 (the extractor may
        # have produced either; both should map to this team).
        if sig_team != norm_team and (not norm_iso3 or sig_team != norm_iso3):
            # Allow substring inclusion in either direction so
            # "England" matches a signal team "England men's national".
            if not (sig_team in norm_team or norm_team in sig_team):
                continue
        absence = _signal_to_absence(signal, source)
        if absence is not None:
            sig_absences.append(absence)
            continue
        lu = _signal_to_lineup(signal, source)
        if lu is not None:
            rank = 2 if lu.state == "confirmed" else 1
            if rank > best_lineup_rank:
                lineup = lu
                best_lineup_rank = rank

    # api-football absence pool.
    api_absences: list[PlayerAbsence] = []
    for row in (injury_rows or []):
        a = _injury_row_to_absence(row)
        if a is not None:
            api_absences.append(a)

    merged = _merge_absences(api_absences, sig_absences)
    materiality = _materiality_for(merged, elo_penalty=elo_penalty)

    return TeamNews(
        team=team_name,
        absences=merged,
        lineup=lineup,
        materiality=materiality,
    )


# ── side-name → iso3 helper, mirroring the football ingest fallback ──

def iso3_for_team(team_name: str) -> str | None:
    """Convenience: resolve a FixtureRef team_a/_b to ISO3 when possible.

    Returns None for club teams or unknown names — caller passes None
    to build_team_news and the signal filter falls back to name-match.
    """
    return iso3_for_name(team_name)
