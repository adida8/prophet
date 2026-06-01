"""CLI for the stub — `python -m stubdesk <command>`.

Commands
--------
run-once   Re-enqueue all frozen matches + outrights onto the push outbox.
drain      One sweep of the outbox → POST to MTAI.
status     Print outbox pending / dead counts + frozen-file inventory.

These mirror the live Desk's `desk run --once` / `desk distribute-drain`
but with no compute — `run-once` just walks the frozen JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from stubdesk import engine
from stubdesk.client import MTAClient
from stubdesk.config import load_config, output_root
from stubdesk.outbox import Outbox
from stubdesk.worker import drain_once

log = logging.getLogger("stubdesk.cli")


def _cmd_run_once(_args) -> int:
    stats = engine.run_once()
    print(
        f"run-once: enqueued {stats.matches_enqueued} matches + "
        f"{stats.outrights_enqueued} outrights ({stats.skipped} skipped)"
    )
    return 0


def _cmd_drain(_args) -> int:
    cfg = load_config()
    if not cfg.push_enabled:
        print("drain: push disabled (DESK_DISTRIBUTE_PUSH != 1); nothing to do")
        return 0
    assert cfg.webhook_url and cfg.webhook_secret  # load_config guarantees this

    async def _go() -> int:
        box = Outbox(cfg.db_path)
        client = MTAClient(webhook_url=cfg.webhook_url, webhook_secret=cfg.webhook_secret)
        try:
            stats = await drain_once(
                box, client,
                max_in_flight=cfg.max_in_flight,
                rate_per_min=cfg.rate_per_min,
            )
        finally:
            await client.aclose()
            box.close()
        print(
            f"drain: claimed={stats.claimed} sent={stats.sent} "
            f"retried={stats.retried} dead={stats.dead} errors={stats.errors_by_kind}"
        )
        return 0

    return asyncio.run(_go())


def _cmd_status(_args) -> int:
    cfg = load_config()
    root = output_root()
    n_matches = len(list((root / "football").glob("*.json"))) - (
        1 if (root / "football" / "index.json").is_file() else 0
    )
    n_outrights = len(list((root / "outrights").glob("*.json"))) - (
        1 if (root / "outrights" / "index.json").is_file() else 0
    )
    box = Outbox(cfg.db_path)
    try:
        pending = box.pending_count()
        dead = box.dead_count()
    finally:
        box.close()
    print(f"output_root: {root}")
    print(f"frozen: {n_matches} matches, {n_outrights} outrights")
    print(f"push_enabled: {cfg.push_enabled}  webhook: {cfg.webhook_url or '(unset)'}")
    print(f"outbox: {pending} pending, {dead} dead  ({cfg.db_path})")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="stubdesk")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-once", help="re-enqueue all frozen payloads")
    sub.add_parser("drain", help="one outbox drain sweep → MTAI")
    sub.add_parser("status", help="outbox + frozen-file inventory")

    args = parser.parse_args(argv)
    handlers = {
        "run-once": _cmd_run_once,
        "drain":    _cmd_drain,
        "status":   _cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
