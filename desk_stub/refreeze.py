"""Re-freeze the stub's data/output/ from a live Desk's read API.

Pulls the *current published* per-match + per-outright JSON over HTTP and
rewrites `data/output/` so the stub serves what production serves right
now (instead of whatever was copied when the folder was created).

Uses the INTERNAL, unauthenticated read routes on purpose:

    GET {base}/api/desk/matches?sport=football   → list of match_ids
    GET {base}/api/desk/match/{id}               → published match JSON
    GET {base}/api/desk/outrights                → outrights index (verbatim)
    GET {base}/api/desk/outright/{id}            → published outright JSON

These return the raw on-disk PUBLISHED shape — which is what belongs on
disk. The stub's external route re-applies the outright wire-transform
(content_type + lifted hard_signal_adjustments) itself, so storing the
external/wire shape here would double-transform and drop the adjustments.

No bearer token required (the external/* routes need one; these don't).

Usage:
    python refreeze.py --base-url https://oddsprimer.com
    python refreeze.py --base-url https://oddsprimer.com --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from stubdesk.config import output_root
from stubdesk.etag import canonical_json, content_etag

DEFAULT_BASE_URL = "https://oddsprimer.com"
SPORT = "football"


def _write(path: Path, payload: dict, *, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    body = canonical_json(payload)
    path.write_text(body, encoding="utf-8")
    # Mirror the live writer: sibling .etag of the canonical content.
    path.with_suffix(path.suffix + ".etag").write_text(
        content_etag(payload), encoding="utf-8"
    )


def refreeze(base_url: str, *, dry_run: bool = False) -> int:
    base = base_url.rstrip("/")
    out = output_root()
    fb_dir = out / SPORT
    od_dir = out / "outrights"

    with httpx.Client(timeout=30.0, follow_redirects=True) as c:
        # ── matches ──────────────────────────────────────────────────
        r = c.get(f"{base}/api/desk/matches", params={"sport": SPORT})
        r.raise_for_status()
        listing = r.json()
        match_ids = [m["match_id"] for m in listing.get("matches", [])]
        print(f"matches: {len(match_ids)} published on {base}")

        index_entries: list[dict] = []
        for i, mid in enumerate(match_ids, 1):
            rm = c.get(f"{base}/api/desk/match/{mid}", params={"sport": SPORT})
            rm.raise_for_status()
            full = rm.json()
            _write(fb_dir / f"{mid}.json", full, dry_run=dry_run)
            index_entries.append({
                "kickoff_utc": full.get("kickoff_utc"),
                "match_id":    full["match_id"],
                "updated_at":  full.get("updated_at"),
            })
            print(f"  [{i}/{len(match_ids)}] {mid}")

        # Rebuild index.json (sorted by kickoff then id, like the writer).
        index_entries.sort(key=lambda e: (e.get("kickoff_utc") or "", e["match_id"]))
        fb_index = {
            "matches":    index_entries,
            "sport":      SPORT,
            "updated_at": listing.get("updated_at"),
        }
        _write(fb_dir / "index.json", fb_index, dry_run=dry_run)

        # ── outrights ────────────────────────────────────────────────
        ro = c.get(f"{base}/api/desk/outrights")
        ro.raise_for_status()
        od_index = ro.json()
        _write(od_dir / "index.json", od_index, dry_run=dry_run)
        outright_ids = [o["outright_id"] for o in od_index.get("outrights", [])]
        print(f"outrights: {len(outright_ids)} published")
        for oid in outright_ids:
            roo = c.get(f"{base}/api/desk/outright/{oid}")
            roo.raise_for_status()
            _write(od_dir / f"{oid}.json", roo.json(), dry_run=dry_run)
            print(f"  {oid}")

    where = "(dry-run; nothing written)" if dry_run else str(out)
    print(f"\nrefreeze complete -> {where}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="refreeze")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL,
                   help=f"live Desk base URL (default {DEFAULT_BASE_URL})")
    p.add_argument("--dry-run", action="store_true",
                   help="fetch + report counts but write nothing")
    args = p.parse_args(argv)
    try:
        return refreeze(args.base_url, dry_run=args.dry_run)
    except httpx.HTTPError as e:
        print(f"refreeze failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
