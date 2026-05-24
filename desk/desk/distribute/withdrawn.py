"""Withdrawn detection — diff prior index against current run.

Compares the per-sport `index.json` written by the previous run against
the set of match_ids the current run is about to publish. Any match_id
present in the prior index but absent from the current run is a
*withdrawal*: we emit one final `MatchOutput` for it with
`verdict.state="withdrawn"`, write it to disk via the normal
`Publisher`, and enqueue it to the distribute outbox.

Single-shot per fixture — the next run's prior index reflects the
current run's writes, which excluded the withdrawn match_ids, so they
don't re-trigger detection. See `desk/docs/adr/0001-withdrawn-verdict-state.md`.

This module reads back the previously-published per-match JSON to
reuse `team_a`, `team_b`, `kickoff_utc`, `competition`, `venue`,
`market_outcomes` — withdrawing doesn't require re-ingest.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable

from desk.publish import (
    Competition,
    Copy,
    MatchOutput,
    OutputIndex,
    Publisher,
    Venue,
    Verdict,
)
from desk.publish.contract import VerdictState

log = logging.getLogger("desk.distribute.withdrawn")


def detect_and_emit(
    *,
    sport: str,
    publisher: Publisher,
    prior_index: OutputIndex | None,
    current_match_ids: Iterable[str],
    now: datetime,
) -> list[MatchOutput]:
    """Emit withdrawn payloads for any match_ids missing from the current run.

    Returns the list of MatchOutputs written. The runner enqueues them
    into the distribute outbox after writing.
    """
    if prior_index is None:
        return []
    current = set(current_match_ids)
    prior_ids = {entry.match_id for entry in prior_index.matches}
    missing = prior_ids - current
    if not missing:
        return []

    out: list[MatchOutput] = []
    for match_id in sorted(missing):
        try:
            prev = publisher.read_match(sport, match_id)
        except FileNotFoundError:
            log.warning(
                "withdrawn skip %s: prior index references missing file",
                match_id,
            )
            continue
        # Don't re-withdraw a match that already terminated.
        if prev.verdict.state == VerdictState.WITHDRAWN.value:
            continue
        withdrawn = _build_withdrawn(prev, now=now)
        try:
            publisher.write_match(withdrawn)
        except Exception as e:                              # noqa: BLE001
            log.warning("withdrawn write_match failed for %s: %s", match_id, e)
            continue
        out.append(withdrawn)
        log.info("withdrawn: %s (was %s)", match_id, prev.verdict.state)
    return out


def _build_withdrawn(prev: MatchOutput, *, now: datetime) -> MatchOutput:
    """Reuse identity fields, replace verdict + copy."""
    return MatchOutput(
        match_id        = prev.match_id,
        sport           = prev.sport,
        competition     = Competition.model_validate(prev.competition.model_dump()),
        kickoff_utc     = prev.kickoff_utc,
        team_a          = prev.team_a,
        team_b          = prev.team_b,
        venue           = Venue.model_validate(prev.venue.model_dump()) if prev.venue else None,
        market_outcomes = list(prev.market_outcomes),
        verdict         = Verdict(state=VerdictState.WITHDRAWN),
        copy            = Copy(
            title=f"{prev.team_a} v {prev.team_b} · withdrawn",
            summary=(
                "The Desk is no longer tracking this fixture. "
                "Withdrawal reason isn't recorded in the engine — most often "
                "the market was de-listed by the source venue, the fixture was "
                "postponed past its slug date, or the fixture was renamed and "
                "now lives under a new match_id."
            ),
            blurb="",
            drivers=[],
        ),
        hard_signal_adjustments = [],
        updated_at      = now,
    )


# ── helpers ────────────────────────────────────────────────────────────


def load_prior_index(publisher: Publisher, sport: str) -> OutputIndex | None:
    """Read the index.json BEFORE the runner overwrites it. Returns None
    if no prior index exists (fresh deploy / first run for this sport)."""
    path = publisher.output_dir / sport / "index.json"
    if not path.is_file():
        return None
    try:
        return OutputIndex.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:                                  # noqa: BLE001
        log.warning("prior index unreadable for %s: %s", sport, e)
        return None


def snapshot_prior_index(publisher: Publisher, sport: str) -> OutputIndex | None:
    """Snapshot the prior index BEFORE write_index overwrites it.

    Call this at the top of each per-sport block in the runner — the
    returned `OutputIndex` is what `detect_and_emit` compares against
    after the loop has finished publishing the current run's matches.
    """
    return load_prior_index(publisher, sport)


def parse_match_json(path: Path) -> MatchOutput:
    """Convenience for tests + scripts: round-trip a single match file."""
    return MatchOutput.model_validate_json(path.read_text(encoding="utf-8"))
