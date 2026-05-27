"""CLI entry: `python -m desk.outrights.backtest [--tournament wc-2022]`.

Standalone so the outright backtest can be invoked without touching
`desk/cli.py` (kept clean to minimise merge collisions with parallel
work on the cli module).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from desk.outrights.backtest.runner import run_backtest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m desk.outrights.backtest",
        description="Replay an outright market against frozen historical inputs.",
    )
    parser.add_argument(
        "--tournament", default="wc-2022",
        help="Tournament key. Today only 'wc-2022' is wired.",
    )
    parser.add_argument(
        "--dashboard",
        default="desk_outrights_backtest_dashboard.html",
        help="HTML dashboard output path (default: cwd).",
    )
    parser.add_argument(
        "--sims", type=int, default=5000,
        help="Point-estimate sims (default: 5000).",
    )
    parser.add_argument(
        "--bootstrap-samples", type=int, default=30,
        help="Bootstrap perturbed samples (default: 30).",
    )
    parser.add_argument(
        "--bootstrap-sims", type=int, default=200,
        help="Sims per bootstrap sample (default: 200).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    summary = run_backtest(
        tournament_key=args.tournament,
        dashboard_path=Path(args.dashboard),
        sims=args.sims,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_sims=args.bootstrap_sims,
    )

    print("\noutright backtest:")
    for k, v in summary.items():
        print(f"  {k:18s}  {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
