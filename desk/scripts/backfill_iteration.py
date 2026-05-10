"""Backfill `verdict.model_p` / `verdict.market_p` / `copy.drivers` on
existing per-match JSON outputs.

Run from desk/:  python3 scripts/backfill_iteration.py

The iteration brief surfaces structured probabilities + a "Why this
call?" bullet list to the front-of-house. New runs of `python -m desk
run --once` populate them naturally; this script handles the JSONs
that pre-date the change.

Strategy
--------
For Picks: parse `model_p` and `market_p` from the existing blurb (the
template writes them in the form "rates X at 34%. {Venue} prices the
same outcome at 22%"). Regenerate `drivers` via the same template the
new runs would use.

For Pass / Avoid: leave model_p / market_p null (per contract — no
single side to talk about). Regenerate `drivers` deterministically.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "output" / "football"

# "rates Bosnia and Herzegovina to win at 34%."
_MODEL_P_RE = re.compile(r"rates [^.]*?at (\d+)%", re.IGNORECASE)

# "Polymarket prices the same outcome at 22%"
_MARKET_P_RE = re.compile(r"prices the same outcome at (\d+)%", re.IGNORECASE)


def _parse_pick_probabilities(blurb: str) -> tuple[float | None, float | None]:
    m = _MODEL_P_RE.search(blurb)
    k = _MARKET_P_RE.search(blurb)
    model_p  = round(int(m.group(1)) / 100.0, 4) if m else None
    market_p = round(int(k.group(1)) / 100.0, 4) if k else None
    return model_p, market_p


def _drivers_for(verdict: dict[str, Any]) -> list[str]:
    state = verdict.get("state")
    edge  = verdict.get("edge_pp") or 0.0
    side  = verdict.get("side") or "this side"
    venue = (verdict.get("market_venue") or "the market").title()

    if state == "pick":
        edge_str = f"{edge:+.1f}"
        return [
            f"Pre-tournament Elo gives {side} a stronger prior than the {venue} line implies.",
            f"The {edge_str}pp gap clears our 3 percentage point threshold for a Pick.",
            "Calibration sits with the closing market across recent fixtures, so selection is the lever.",
            "Late-binding signals — form, confirmed XI, weather — re-evaluate closer to kickoff.",
        ]
    if state == "pass":
        return [
            "Model and market sit within a percentage point on every side.",
            "No structural disagreement to publish — both are pricing the same shape.",
            "Late-binding signals (form, weather, confirmed XI) re-evaluate near kickoff.",
        ]
    if state == "avoid":
        return [
            f"Every side priced shorter than our model — most-negative gap is {edge:+.1f}pp.",
            "No side priced attractively against the engine's Elo prior.",
            "Avoid is reported separately from Pass so it doesn't read as ambiguous.",
        ]
    return []


def main() -> int:
    files = sorted(OUTPUT_DIR.glob("fb-*.json"))
    if not files:
        print(f"no per-match JSONs found under {OUTPUT_DIR}", file=sys.stderr)
        return 1

    n_updated = n_picks = n_pass = n_avoid = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        verdict = data.get("verdict") or {}
        copy    = data.get("copy") or {}
        state   = verdict.get("state")

        if state == "pick":
            blurb = copy.get("blurb", "")
            model_p, market_p = _parse_pick_probabilities(blurb)
            if model_p is None or market_p is None:
                print(f"  skipped {path.name}: couldn't parse pick probabilities from blurb")
                continue
            verdict["model_p"]  = model_p
            verdict["market_p"] = market_p
            n_picks += 1
        elif state == "pass":
            verdict["model_p"] = None
            verdict["market_p"] = None
            n_pass += 1
        elif state == "avoid":
            verdict["model_p"] = None
            verdict["market_p"] = None
            n_avoid += 1
        else:
            continue

        copy["drivers"] = _drivers_for(verdict)
        data["verdict"] = verdict
        data["copy"]    = copy

        path.write_text(
            json.dumps(data, sort_keys=True, separators=(",", ":"), default=str),
            encoding="utf-8",
        )
        n_updated += 1

    print(f"updated {n_updated} files: {n_picks} picks, {n_pass} pass, {n_avoid} avoid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
