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
