"""Engine runner — orchestrates one full pass.

PR 4: pipeline is now end-to-end. For each priced fixture we build
features, run the model, compute a verdict, and publish the resulting
`MatchOutput`. Per-fixture failures are isolated per spec §9 — a single
bad row never blocks the rest of the publish.
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
from desk.publish.contract import VerdictState
from desk.sport import FixtureRef
from desk.sports import active_sports
from desk.verdict.compare import MarketSnapshot

log = logging.getLogger("desk.runner")


def _build_match(
    fx: FixtureRef,
    *,
    verdict: Verdict,
    now: datetime,
    copy=None,
) -> MatchOutput:
    venue = None
    if fx.venue_city and fx.venue_stadium and fx.venue_country:
        venue = Venue(
            city=fx.venue_city,
            stadium=fx.venue_stadium,
            country=fx.venue_country,
        )
    kwargs = dict(
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
        verdict=verdict,
        updated_at=now,
    )
    if copy is not None:
        kwargs["copy"] = copy
    return MatchOutput(**kwargs)


def run_once(*, output_dir: Path | None = None) -> dict[str, list[Path]]:
    pub = Publisher(output_dir=Path(output_dir or config.OUTPUT_DIR))
    now = datetime.now(tz=timezone.utc)
    written: dict[str, list[Path]] = {}

    for sport in active_sports():
        log.info("listing priced fixtures for %s", sport.code)
        try:
            pairs = list(sport.list_priced_fixtures())
        except Exception as e:                          # noqa: BLE001 — spec §9
            log.warning("priced ingest failed for %s: %s", sport.code, e)
            pairs = []

        log.info("got %d priced fixtures for %s", len(pairs), sport.code)
        if not pairs:
            written[sport.code] = []
            continue

        matches: list[MatchOutput] = []
        paths: list[Path] = []
        n_pick = n_pass = n_avoid = 0
        for fx, snapshot in pairs:
            copy = None
            try:
                if hasattr(sport, "decide_and_explain"):
                    v, copy = sport.decide_and_explain(fx, snapshot)
                else:
                    v = sport.decide(fx, snapshot)
            except Exception as e:                      # noqa: BLE001
                log.warning("decide failed for %s: %s", fx.match_id, e)
                v = Verdict(state=VerdictState.PASS)
            try:
                m = _build_match(fx, verdict=v, now=now, copy=copy)
            except Exception as e:                      # noqa: BLE001
                log.warning("build_match failed for %s: %s", fx.match_id, e)
                continue
            try:
                path, _ = pub.write_match(m)
            except Exception as e:                      # noqa: BLE001
                log.warning("write_match failed for %s: %s", fx.match_id, e)
                continue

            matches.append(m)
            paths.append(path)
            if v.state == VerdictState.PICK.value or v.state == VerdictState.PICK:
                n_pick += 1
            elif v.state == VerdictState.AVOID.value or v.state == VerdictState.AVOID:
                n_avoid += 1
            else:
                n_pass += 1

        if matches:
            idx_path, _ = pub.write_index(sport.code, matches)
            paths.append(idx_path)
        log.info("%s: %d pick / %d pass / %d avoid",
                 sport.code, n_pick, n_pass, n_avoid)
        written[sport.code] = paths

    return written
