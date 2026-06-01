"""The stub engine.

This is the replacement for the live Desk's `run_once` + outrights
pipeline. It does NO computation: it walks the frozen JSON in the output
dir and re-enqueues every match + outright onto the push outbox. The
drain loop (`distribute_loop.py`) then POSTs them to MTAI exactly as the
live Desk would.

"Stub engine completes running → calls MTAI to update" == this function
enqueues the frozen payloads; delivery happens on the next drain sweep.

Idempotent: re-running just refreshes the pending rows (outbox collapse
rule). When `DESK_DISTRIBUTE_PUSH != 1`, enqueue is a no-op and this
function only reports what it *would* have pushed — the GET routes still
serve the frozen JSON regardless.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from stubdesk.config import DistributeConfig, load_config, output_root
from stubdesk.outbox import Outbox
from stubdesk.wire import BodyTooLarge, enqueue_match, enqueue_outright

log = logging.getLogger("stubdesk.engine")

_SPORTS = ("football",)
_OUTRIGHTS_DIR = "outrights"


@dataclass
class EngineStats:
    matches_enqueued:   int = 0
    outrights_enqueued: int = 0
    skipped:            int = 0


def _iter_json_files(directory: Path):
    """Yield every payload JSON in a directory, skipping the index file."""
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.json")):
        if path.name == "index.json":
            continue
        yield path


def run_once(config: DistributeConfig | None = None) -> EngineStats:
    """Re-enqueue all frozen matches + outrights. Returns EngineStats."""
    cfg = config if config is not None else load_config()
    root = output_root()
    stats = EngineStats()

    match_paths = [p for sport in _SPORTS for p in _iter_json_files(root / sport)]
    outright_paths = list(_iter_json_files(root / _OUTRIGHTS_DIR))

    if not cfg.push_enabled:
        log.info(
            "engine: push disabled (DESK_DISTRIBUTE_PUSH != 1); "
            "would enqueue %d matches + %d outrights",
            len(match_paths), len(outright_paths),
        )
        stats.matches_enqueued = len(match_paths)
        stats.outrights_enqueued = len(outright_paths)
        return stats

    box = Outbox(cfg.db_path)
    try:
        for path in match_paths:
            if _enqueue_one(path, box, cfg, kind="match"):
                stats.matches_enqueued += 1
            else:
                stats.skipped += 1
        for path in outright_paths:
            if _enqueue_one(path, box, cfg, kind="outright"):
                stats.outrights_enqueued += 1
            else:
                stats.skipped += 1
    finally:
        box.close()

    log.info(
        "engine: enqueued %d matches + %d outrights (%d skipped)",
        stats.matches_enqueued, stats.outrights_enqueued, stats.skipped,
    )
    return stats


def _enqueue_one(path: Path, box: Outbox, cfg: DistributeConfig, *, kind: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        log.exception("engine: failed to read %s", path)
        return False
    try:
        if kind == "match":
            enqueue_match(payload, config=cfg, outbox=box)
        else:
            enqueue_outright(payload, config=cfg, outbox=box)
        return True
    except BodyTooLarge as e:
        log.error("engine: %s", e)
        return False
    except Exception:                                   # noqa: BLE001
        log.exception("engine: failed to enqueue %s", path)
        return False
