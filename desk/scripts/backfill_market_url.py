"""Backfill `verdict.market_url` on existing per-match JSON outputs.

Run from desk/:  python3 scripts/backfill_market_url.py

The contract change introducing `verdict.market_url` (see
desk/publish/contract.py) is non-breaking on Pass/Avoid (the field is
optional there) but breaking on Pick — every Pick must carry a CTA
destination. New runs of `python -m desk run --once` populate
market_url naturally via the Polymarket gamma slug. This script is for
the existing committed outputs that pre-date the change.

Mapping rule (WC26 only — the only competition with priced Picks today):
    match_id  fb-wc26-{home}-{away}-{yyyymmdd}
    slug      fifwc-{home}-{away}-{yyyy}-{mm}-{dd}
    URL       https://polymarket.com/event/{slug}

Non-WC26 fixtures are all Pass and do not strictly require a URL — they
get one populated only when their match_id maps cleanly under a known
Polymarket prefix. Today the script leaves them alone (market_url=None
on Pass is allowed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "output" / "football"

# match_id competition_code → Polymarket slug prefix
WC26_PREFIX = "fifwc"


def market_url_for_match_id(match_id: str) -> Optional[str]:
    parts = match_id.split("-")
    # fb-{competition}-{home}-{away}-{yyyymmdd}
    if len(parts) < 5:
        return None
    sport_short, comp, home, away, date = parts[0], parts[1], parts[-3], parts[-2], parts[-1]
    if sport_short != "fb" or len(date) != 8:
        return None
    yyyy, mm, dd = date[0:4], date[4:6], date[6:8]
    if comp == "wc26":
        slug = f"{WC26_PREFIX}-{home}-{away}-{yyyy}-{mm}-{dd}"
        return f"https://polymarket.com/event/{slug}"
    # Other competitions: prefix mapping not stored on disk; leave None.
    return None


def main() -> int:
    files = sorted(OUTPUT_DIR.glob("fb-*.json"))
    if not files:
        print(f"no per-match JSONs found under {OUTPUT_DIR}", file=sys.stderr)
        return 1

    n_updated = n_skipped = n_pick_fixed = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        match_id = data.get("match_id", path.stem)
        verdict = data.get("verdict") or {}
        url = market_url_for_match_id(match_id)
        if url is None:
            n_skipped += 1
            continue
        if verdict.get("market_url") == url:
            n_skipped += 1
            continue
        verdict["market_url"] = url
        data["verdict"] = verdict
        # Canonical JSON (matches desk/publish/writer.py shape).
        path.write_text(
            json.dumps(data, sort_keys=True, separators=(",", ":"), default=str),
            encoding="utf-8",
        )
        n_updated += 1
        if verdict.get("state") == "pick":
            n_pick_fixed += 1

    print(f"updated {n_updated} files ({n_pick_fixed} picks), skipped {n_skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
