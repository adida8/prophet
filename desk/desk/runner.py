"""Engine runner — orchestrates one full pass.

`run_once()` lists fixtures from every active sport, builds a stub
`MatchOutput` per fixture, and publishes per-match JSON + per-sport
`index.json`. PR 4 wires real verdicts in; PR 6 puts this on a schedule.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from desk import config
from desk.publish import (
    Competition,
    MatchOutput,
    Publisher,
    Venue,
    Verdict,
)
from desk.sport import FixtureRef
from desk.sports import active_sports

log = logging.getLogger("desk.runner")


def _stub_match(fx: FixtureRef, *, now: datetime) -> MatchOutput:
    """Translate a `FixtureRef` into a Pass-state `MatchOutput` for PR 2."""
    venue = None
    if fx.venue_city and fx.venue_stadium and fx.venue_country:
        venue = Venue(
            city=fx.venue_city,
            stadium=fx.venue_stadium,
            country=fx.venue_country,
        )
    return MatchOutput(
        match_id=fx.match_id,
        sport=fx.sport,
        competition=Competition(
            code=fx.competition_code,
            label=fx.competition_label,
            stage=fx.competition_stage,
        ),
        kickoff_utc=fx.kickoff_utc,
        team_a=fx.team_a,
        team_b=fx.team_b,
        venue=venue,
        market_outcomes=list(fx.market_outcomes),
        verdict=Verdict(state="pass"),
        updated_at=now,
    )


def run_once(*, output_dir: Path | None = None) -> dict[str, list[Path]]:
    """List fixtures, write stub MatchOutputs, refresh per-sport index.

    Returns the set of paths written, keyed by sport. Catches per-fixture
    failures so a single bad row doesn't block the rest of the publish.
    """
    pub = Publisher(output_dir=Path(output_dir or config.OUTPUT_DIR))
    now = datetime.now(tz=timezone.utc)
    written: dict[str, list[Path]] = {}

    for sport in active_sports():
        log.info("listing fixtures for %s", sport.code)
        fixtures = list(sport.list_fixtures())
        log.info("got %d fixtures for %s", len(fixtures), sport.code)

        matches: list[MatchOutput] = []
        paths: list[Path] = []
        for fx in fixtures:
            try:
                m = _stub_match(fx, now=now)
            except Exception as e:                # noqa: BLE001 — tolerated per spec §9
                log.warning("skipping fixture %s: %s", fx.match_id, e)
                continue
            try:
                path, _ = pub.write_match(m)
            except Exception as e:                # noqa: BLE001
                log.warning("skipping write for %s: %s", fx.match_id, e)
                continue
            matches.append(m)
            paths.append(path)

        if matches:
            idx_path, _ = pub.write_index(sport.code, matches)
            paths.append(idx_path)
        written[sport.code] = paths

    return written
