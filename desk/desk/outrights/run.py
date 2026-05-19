"""End-to-end orchestrator for outright winners.

Ingest → model → decide → explain → publish. Used by the CLI:

    python -m desk outrights run

…and by the main `python -m desk run --once` runner after matches
finish (one extra step, ~30s of compute).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from desk.config import OUTPUT_DIR
from desk.outrights.decide import decide
from desk.outrights.explainer import build_copy
from desk.outrights.ingest_polymarket import fetch_snapshot
from desk.outrights.model import (
    BASE_SEED,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_SIMS,
    SIMS,
    run as run_model,
)
from desk.outrights.publish import write, write_index
from desk.outrights.wc26_data import elo_is_stub

log = logging.getLogger("desk.outrights.run")


def run_once(
    *,
    sims: int = SIMS,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    bootstrap_sims: int = BOOTSTRAP_SIMS,
    seed: int = BASE_SEED,
    out_dir: Path | None = None,
) -> Path:
    """Run the outrights pipeline end-to-end. Returns the path of the
    JSON that was written.
    """
    out = out_dir or (OUTPUT_DIR / "outrights")
    out.mkdir(parents=True, exist_ok=True)

    log.info("outrights: fetching Polymarket snapshot")
    snapshot = asyncio.run(fetch_snapshot())
    log.info("outrights: %d priced teams (overround %+.2fpp)",
             len(snapshot.prices), snapshot.overround * 100)

    field = tuple(p.team for p in snapshot.prices)
    stub_count = sum(1 for t in field if elo_is_stub(t))
    if stub_count:
        log.info("outrights: %d/%d teams using stub Elo", stub_count, len(field))

    log.info(
        "outrights: running MC sim — %d sims + %d×%d bootstrap",
        sims, bootstrap_samples, bootstrap_sims,
    )
    model = run_model(
        field,
        sims=sims,
        bootstrap_samples=bootstrap_samples,
        bootstrap_sims=bootstrap_sims,
        seed=seed,
    )

    verdict = decide(snapshot, model)
    copy = build_copy(snapshot, model, verdict)

    log.info(
        "outrights: verdict=%s candidate=%s",
        verdict.state,
        verdict.candidate.label if verdict.candidate else "—",
    )

    json_path = write(out, snapshot, model, verdict, copy)

    # Index — for now just one outright; the manifest shape stays
    # forward-compatible with adding group winners / golden boot.
    payload_entry = {
        "outright_id":  json_path.stem,
        "verdict":      verdict.state,
        "candidate":    verdict.candidate.team if verdict.candidate else None,
        "resolves_at":  snapshot.resolution_utc.isoformat().replace("+00:00", "Z"),
    }
    write_index(out, [payload_entry])
    return json_path
