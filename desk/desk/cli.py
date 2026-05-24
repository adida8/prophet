"""`desk` CLI.

Sub-commands:
    desk run [--once]                     Run the engine. v1: --once only (PR 6 adds the loop).
    desk sports                           List registered sports.
    desk match <id>                       Print the current published JSON for one match.
    desk backtest --tournament wc-2022    Replay the engine across a historical tournament.
    desk replay <id>                      PR 6+ — placeholder for as-of replay from snapshots.

Designed to be runnable two ways during development:
    python -m desk        # via the package
    desk                  # via the project.scripts entry point
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from desk import config
from desk.publish import Publisher
from desk.runner import run_once
from desk.sports import SPORT_REGISTRY


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(name)-32s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.once:
        print("desk run currently supports only --once (PR 6 adds the loop)", file=sys.stderr)
        return 2
    written = run_once(output_dir=Path(args.output_dir) if args.output_dir else None)
    total = sum(len(v) for v in written.values())
    print(f"wrote {total} files across {len(written)} sport(s)")
    for sport, paths in written.items():
        print(f"  {sport}: {len(paths)} file(s)")

    if not args.skip_outrights:
        from desk.outrights.run import run_once as run_outrights_once
        out_root = Path(args.output_dir) if args.output_dir else None
        out_dir = (out_root / "outrights") if out_root else None
        try:
            path = run_outrights_once(out_dir=out_dir)
            print(f"outrights: wrote {path}")
        except Exception as e:  # noqa: BLE001 — never break matches if outrights fail
            print(f"outrights: skipped — {e}", file=sys.stderr)
    return 0


def _cmd_outrights(args: argparse.Namespace) -> int:
    from desk.outrights.run import run_once as run_outrights_once
    out_dir = Path(args.output_dir) / "outrights" if args.output_dir else None
    path = run_outrights_once(
        sims=args.sims,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_sims=args.bootstrap_sims,
        seed=args.seed,
        out_dir=out_dir,
    )
    print(f"outrights: wrote {path}")
    return 0


def _cmd_sports(_: argparse.Namespace) -> int:
    for code, sport in SPORT_REGISTRY.items():
        print(f"{code}\t{sport.short_code}\t{sport.label}")
    return 0


def _cmd_match(args: argparse.Namespace) -> int:
    pub = Publisher(output_dir=Path(args.output_dir) if args.output_dir else config.OUTPUT_DIR)
    sport = args.match_id.split("-", 1)[0]
    sport = "football" if sport == "fb" else sport
    try:
        m = pub.read_match(sport, args.match_id)
    except FileNotFoundError:
        print(f"no published JSON for {args.match_id}", file=sys.stderr)
        return 1
    print(json.dumps(m.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    print("desk replay is a PR 6 placeholder — coming with the scheduler", file=sys.stderr)
    return 2


def _cmd_fetch_signals(args: argparse.Namespace) -> int:
    """Fetch the trusted-core sources into the signals cache.

    Read-only against the engine — does nothing to /api/desk/* output.
    Useful for poking at what the registry actually pulls down. Long-
    tail aggregators (GDELT) are off by default since they hit external
    APIs whose query has to be tuned per use case; opt in with
    `--include-long-tail`.
    """
    from desk.signals.cache import SignalsCache
    from desk.signals.fetch import fetch_all
    from desk.signals.registry import Registry

    reg = Registry.from_csv()
    from desk.signals.runtime import default_cache_path
    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tiers: tuple[str, ...] = ("trusted_core",)
    if args.include_long_tail:
        tiers = tiers + ("long_tail",)
    with SignalsCache(db_path) as cache:
        outcomes = fetch_all(reg, cache, tiers=tiers)

    totals = {"new": 0, "changed": 0, "unchanged": 0}
    for o in outcomes:
        totals["new"]       += o.new
        totals["changed"]   += o.changed
        totals["unchanged"] += o.unchanged
        suffix = f"  err={o.error}" if o.error else ""
        print(
            f"  {o.source_id:28s}  {o.status:14s}  "
            f"new={o.new:3d}  changed={o.changed:3d}  unchanged={o.unchanged:3d}{suffix}"
        )
    print()
    print(f"  totals: new={totals['new']}  changed={totals['changed']}  "
          f"unchanged={totals['unchanged']}  (db: {db_path})")
    return 0


def _cmd_extract_signals(args: argparse.Namespace) -> int:
    """Run the LLM extractor across the signals cache. Idempotent — items
    we've already extracted (at the same content_hash) are skipped."""
    import os

    from desk.signals.cache import SignalsCache
    from desk.signals.extract import AnthropicExtractor, extract_all

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    from desk.signals.runtime import default_cache_path
    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    extractor = AnthropicExtractor(model=args.model)
    with SignalsCache(db_path) as cache:
        outcomes = extract_all(
            cache,
            extractor=extractor,
            source_ids=set(args.source) if args.source else None,
            limit_per_source=args.limit,
        )

    counts: dict[str, int] = {}
    new = 0
    for o in outcomes:
        counts[o.status] = counts.get(o.status, 0) + 1
        new += o.new_signals
    for status, n in sorted(counts.items()):
        print(f"  {status:18s}  {n}")
    print()
    print(f"  signals written: {new}  (db: {db_path})")
    return 0


def _cmd_distribute_drain(args: argparse.Namespace) -> int:
    """Single-sweep drainer for the MTA push outbox.

    Designed to be called repeatedly (e.g. every 30s by the
    project-root async loop). Exits cleanly when push is disabled so a
    cron-style caller can fire it unconditionally without an env check.
    """
    import asyncio

    from desk.distribute import Outbox, drain_once, load_config
    from desk.distribute.client import MTAClient

    try:
        cfg = load_config()
    except ValueError as e:
        print(f"distribute-drain: {e}", file=sys.stderr)
        return 2

    if not cfg.push_enabled:
        print("distribute-drain: DESK_DISTRIBUTE_PUSH=0 — nothing to do")
        return 0

    async def _run() -> int:
        assert cfg.webhook_url and cfg.webhook_secret  # load_config guarantees
        client = MTAClient(
            webhook_url=cfg.webhook_url,
            webhook_secret=cfg.webhook_secret,
        )
        try:
            with Outbox(cfg.db_path) as ob:
                pending_before = ob.pending_count()
                dead_before    = ob.dead_count()
                stats = await drain_once(
                    ob, client,
                    max_in_flight=cfg.max_in_flight,
                    rate_per_min=cfg.rate_per_min,
                )
                pending_after = ob.pending_count()
                dead_after    = ob.dead_count()
        finally:
            await client.aclose()

        print(
            f"distribute-drain: claimed={stats.claimed} sent={stats.sent} "
            f"retried={stats.retried} dead={stats.dead} "
            f"(pending {pending_before}→{pending_after}, "
            f"dead {dead_before}→{dead_after})"
        )
        if stats.errors_by_kind:
            kinds = " ".join(f"{k}={v}" for k, v in sorted(stats.errors_by_kind.items()))
            print(f"  errors: {kinds}")
        return 0

    return asyncio.run(_run())


def _cmd_signals_validate(args: argparse.Namespace) -> int:
    """Load + report on the source seed.

    Catches malformed seeds before they reach the fetcher / explainer.
    Prints one line per source with its trust-gate verdict and a
    summary so the operator can eyeball the registry shape.
    """
    from desk.signals.registry import DEFAULT_SEED_PATH, Registry
    from desk.signals.resolve import sources_for

    seed_path = Path(args.seed) if args.seed else DEFAULT_SEED_PATH
    try:
        reg = Registry.from_csv(seed_path)
    except (ValueError, FileNotFoundError) as e:
        print(f"validate: {e}", file=sys.stderr)
        return 2

    enabled       = reg.enabled()
    model_eligible = [s for s in enabled if s.can_feed_model]
    editorial      = [s for s in enabled if s.editorial_only]
    by_feed_type:  dict[str, int] = {}
    for s in enabled:
        by_feed_type[s.feed_type] = by_feed_type.get(s.feed_type, 0) + 1

    print(f"seed: {seed_path}")
    print(f"  rows: {len(reg.all())}  enabled: {len(enabled)}  "
          f"disabled: {len(reg.all()) - len(enabled)}")
    print(f"  can_feed_model: {len(model_eligible)}  "
          f"editorial_only: {len(editorial)}")
    print(f"  by feed_type: " + ", ".join(
        f"{ft}={n}" for ft, n in sorted(by_feed_type.items())
    ))
    print()
    print(f"  {'id':24s} {'feed_type':11s} {'rel':>5s}  bias       tier         gate")
    for s in reg.all():
        gate = "model" if s.can_feed_model else "editorial-only"
        enabled_mark = " " if s.enabled else "X"
        print(f"  {enabled_mark} {s.id:22s} {s.feed_type:11s} "
              f"{s.reliability:>5.2f}  {s.bias_flag:9s}  "
              f"{s.tier:11s}  {gate}")

    # Smoke the resolver on the most common tag set so a regression in
    # tag intersection at least one row off the seed gets caught here.
    if args.resolve:
        tags = set(args.resolve.split(","))
        print()
        print(f"resolve {sorted(tags)}: {len(sources_for(tags, reg))} match(es)")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    """Run the historical backtest harness.

    Lazy-imports the backtest package so the rest of the CLI is fast and
    doesn't depend on openpyxl when only `desk run` is used.
    """
    from desk.backtest.runner import ALL_WINDOWS, run_backtest
    from desk.backtest.tournaments import TOURNAMENTS

    if args.all:
        keys = sorted(TOURNAMENTS)
    else:
        keys = list(args.tournament or [])
    if not keys:
        print("Provide --tournament <key> [--tournament ...] or --all.", file=sys.stderr)
        print(f"Known tournaments: {sorted(TOURNAMENTS)}", file=sys.stderr)
        return 2

    if args.windows:
        windows = tuple(args.windows)
    else:
        windows = ALL_WINDOWS

    # Walk up until we find the workbook scaffold so the resolved path is
    # robust whether `desk` is invoked from the project root or from inside `desk/`.
    here = Path(__file__).resolve()
    candidate_root: Path | None = None
    for ancestor in (*here.parents, here):
        if (ancestor / "desk_backtest.xlsx").exists():
            candidate_root = ancestor
            break
    project_root = candidate_root or here.parents[3]
    workbook_path  = Path(args.workbook)  if args.workbook  else project_root / "desk_backtest.xlsx"
    dashboard_path = Path(args.dashboard) if args.dashboard else project_root / "desk_backtest_dashboard.html"

    try:
        summary = run_backtest(
            tournament_keys=keys,
            windows=windows,
            limit=args.limit,
            workbook_path=workbook_path,
            dashboard_path=dashboard_path,
        )
    except (ValueError, FileNotFoundError, NotImplementedError) as e:
        print(f"backtest failed: {e}", file=sys.stderr)
        return 2

    print()
    print(f"  tournaments       {', '.join(summary['tournaments'])}")
    print(f"  matches           {summary['matches']}")
    print(f"  snapshots         {summary['snapshots']}  (KO: {summary['ko_snapshots']})")
    print(f"  mean Brier        model {summary['mean_brier']:.4f}  | "
          f"closing market {summary['mean_market_brier']:.4f}")
    diff = summary['mean_brier'] - summary['mean_market_brier']
    arrow = "▲ worse" if diff > 0 else ("▼ better" if diff < 0 else "= equal")
    print(f"                    {arrow} by {abs(diff):.4f}")
    print(f"  verdicts          {summary['verdict_counts']}")
    print(f"  workbook          {summary['workbook']}")
    print(f"  dashboard         {summary['dashboard']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="desk", description="The Desk — engine CLI.")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--output-dir", help="override DESK_OUTPUT_DIR")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the engine")
    r.add_argument("--once", action="store_true", help="single pass, then exit")
    r.add_argument("--skip-outrights", action="store_true",
                   help="don't run the outright winner sim (matches only)")
    r.set_defaults(func=_cmd_run)

    o = sub.add_parser("outrights", help="run the outright winner sim only")
    o.add_argument("--sims", type=int, default=10_000)
    o.add_argument("--bootstrap-samples", type=int, default=100)
    o.add_argument("--bootstrap-sims", type=int, default=1_000)
    o.add_argument("--seed", type=int, default=42)
    o.set_defaults(func=_cmd_outrights)

    s = sub.add_parser("sports", help="list registered sports")
    s.set_defaults(func=_cmd_sports)

    m = sub.add_parser("match", help="print one published match JSON")
    m.add_argument("match_id")
    m.set_defaults(func=_cmd_match)

    rp = sub.add_parser("replay", help="re-derive a match as-of (PR 6)")
    rp.add_argument("match_id")
    rp.add_argument("--as-of", required=False)
    rp.set_defaults(func=_cmd_replay)

    fs = sub.add_parser("fetch-signals", help="fetch trusted-core sources into the signals cache")
    fs.add_argument("--db", help="override signals DB path (default: desk/data/signals.db)")
    fs.add_argument("--include-long-tail", action="store_true",
                    help="also fetch long-tail aggregators (e.g. GDELT) — extra cost")
    fs.set_defaults(func=_cmd_fetch_signals)

    es = sub.add_parser("extract-signals",
                        help="run the LLM extractor across cached items (needs ANTHROPIC_API_KEY)")
    es.add_argument("--db", help="override signals DB path (default: desk/data/signals.db)")
    es.add_argument("--model", default="claude-haiku-4-5",
                    help="Claude model id (default: claude-haiku-4-5)")
    es.add_argument("--source", action="append",
                    help="restrict to source(s) by id; repeatable")
    es.add_argument("--limit", type=int, default=None,
                    help="extract at most N items per source (smoke-testing)")
    es.set_defaults(func=_cmd_extract_signals)

    dd = sub.add_parser("distribute-drain",
                        help="drain pending outbox rows to MTA (one sweep)")
    dd.set_defaults(func=_cmd_distribute_drain)

    # `desk signals <subcommand>` — nested subparser. `validate` is the
    # only entry for now; future ops (list, stats, …) plug in here.
    sg = sub.add_parser("signals", help="news-signals subsystem ops")
    sg_sub = sg.add_subparsers(dest="signals_cmd", required=True)
    sv = sg_sub.add_parser("validate", help="load + report on the source seed")
    sv.add_argument("--seed", help="override seed CSV path (default: shipped seed)")
    sv.add_argument("--resolve",
                    help="comma-separated tags; report how many sources match")
    sv.set_defaults(func=_cmd_signals_validate)

    bt = sub.add_parser("backtest", help="run the historical backtest harness")
    bt.add_argument("--tournament", action="append",
                    help="tournament key (repeatable); e.g. wc-2022")
    bt.add_argument("--all", action="store_true",
                    help="run every configured tournament")
    bt.add_argument("--limit", type=int, default=None,
                    help="smoke-test on first N matches per tournament")
    bt.add_argument("--windows", nargs="+", default=None,
                    choices=["T-38", "T-5", "T-1h", "KO"],
                    help="restrict to the given windows; default = all four")
    bt.add_argument("--workbook",  help="override workbook path (default: project root/desk_backtest.xlsx)")
    bt.add_argument("--dashboard", help="override dashboard path (default: project root/desk_backtest_dashboard.html)")
    bt.set_defaults(func=_cmd_backtest)

    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
