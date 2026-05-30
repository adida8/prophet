"""End-to-end orchestrator for outright winners.

Ingest → (hard signals →) model → decide → explain → publish. Used by
the CLI:

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
from desk.outrights.hard_signals import (
    OutrightHardSignalAdjustment,
    apply_hard_signals,
)
from desk.outrights.ingest_polymarket import fetch_snapshot
from desk.outrights.model import (
    BASE_SEED,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_SIMS,
    SIMS,
    run as run_model,
)
from desk.outrights.publish import write, write_index
from desk.outrights.squad_note import squad_notes_for_teams
from desk.outrights.signals_glue import tags_for_outright
from desk.outrights.live_elo import (
    live_elo_overrides_for_field, merge_elo_overrides,
)
from desk.outrights.wc26_data import elo_is_stub
from desk.signals.cache import SignalsCache
from desk.signals.hard_track import hard_signals_for
from desk.signals.registry import Registry
from desk.signals.runtime import default_cache_path

log = logging.getLogger("desk.outrights.run")


def _collect_hard_signals(
    field: tuple[str, ...],
) -> tuple[dict[str, float], list[OutrightHardSignalAdjustment]]:
    """Open the signals cache (if present), pull hard-track signals
    covering any team in the field, apply bounded Elo adjustments.

    Returns ``({}, [])`` when the cache file doesn't exist — same
    posture as `SignalsRuntime.for_sport`: news-signals are *additive*,
    a fresh clone with no cache still runs the outright pipeline.
    """
    path = default_cache_path()
    if not path.exists():
        log.debug("outrights: no signals cache at %s — skipping hard signals", path)
        return {}, []
    tags = tags_for_outright(field)
    cache = SignalsCache(path)
    try:
        registry = Registry.from_csv()
        pairs = hard_signals_for(
            fixture_tags=tags,
            cache=cache,
            registry=registry,
        )
    finally:
        cache.close()
    return apply_hard_signals(field, signals=pairs)


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

    elo_overrides, hard_audit = _collect_hard_signals(field)

    # Phase 1b — fold live-Elo deltas in alongside hard-signal nudges.
    # When the live cache is absent the adapter returns {} and the
    # behaviour is byte-identical to pre-1b (same gate the per-match
    # path uses for EloRuntime).
    from desk.data.elo import EloRuntime, default_cache_path as _elo_default_path
    if _elo_default_path().exists():
        with EloRuntime() as elo_rt:
            live_overrides = live_elo_overrides_for_field(field, runtime=elo_rt)
        if live_overrides:
            teams_touched = len(live_overrides)
            net = sum(live_overrides.values())
            log.info(
                "outrights: applied live-Elo deltas for %d teams (net Elo %+.1f)",
                teams_touched, net,
            )
            elo_overrides = merge_elo_overrides(elo_overrides, live_overrides)

    if hard_audit:
        teams_touched = len({a.team for a in hard_audit})
        total_delta   = sum(a.delta_elo for a in hard_audit)
        log.info(
            "outrights: applied %d hard-signal adjustments across %d teams "
            "(net Elo %+.1f)", len(hard_audit), teams_touched, total_delta,
        )
        for adj in hard_audit:
            log.info(
                "outrights: %s %+0.1f Elo (%s, %s)",
                adj.team, adj.delta_elo, adj.signal_type, adj.source_id,
            )

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
        elo_overrides=elo_overrides,
    )

    verdict = decide(snapshot, model)
    copy = build_copy(snapshot, model, verdict)

    log.info(
        "outrights: verdict=%s candidate=%s",
        verdict.state,
        verdict.candidate.label if verdict.candidate else "—",
    )

    # Q4 squad-paragraph: build a per-team `squad_note` from the
    # api-football cache. When the cache is absent, every team gets an
    # empty string — the ladder JSON shape is unchanged for fresh
    # deploys that haven't run `desk fetch-injuries` / `fetch-cards`.
    squad_notes: dict[str, str] = {}
    try:
        from desk.data.api_football import APIFootballRuntime, default_cache_path
        af_path = default_cache_path()
        if af_path.exists():
            with APIFootballRuntime(af_path) as af_rt:
                squad_notes = squad_notes_for_teams(
                    field, api_football_runtime=af_rt, competition="wc26",
                )
            populated = sum(1 for n in squad_notes.values() if n)
            if populated:
                log.info(
                    "outrights: populated squad_note for %d/%d teams",
                    populated, len(field),
                )
    except Exception as e:  # noqa: BLE001 — never block the ladder
        log.warning("outrights: squad_note build failed: %s", e)

    json_path = write(out, snapshot, model, verdict, copy,
                     hard_signal_adjustments=hard_audit,
                     squad_notes=squad_notes)

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
