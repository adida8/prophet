"""`desk` CLI.

Sub-commands:
    desk run [--once]    Run the engine. v1: --once is the only mode (PR 6 adds the loop).
    desk sports          List registered sports.
    desk match <id>      Print the current published JSON for one match.
    desk replay <id>     PR 6+ — placeholder for as-of replay from snapshots.

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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="desk", description="The Desk — engine CLI.")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--output-dir", help="override DESK_OUTPUT_DIR")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the engine")
    r.add_argument("--once", action="store_true", help="single pass, then exit")
    r.set_defaults(func=_cmd_run)

    s = sub.add_parser("sports", help="list registered sports")
    s.set_defaults(func=_cmd_sports)

    m = sub.add_parser("match", help="print one published match JSON")
    m.add_argument("match_id")
    m.set_defaults(func=_cmd_match)

    rp = sub.add_parser("replay", help="re-derive a match as-of (PR 6)")
    rp.add_argument("match_id")
    rp.add_argument("--as-of", required=False)
    rp.set_defaults(func=_cmd_replay)

    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
