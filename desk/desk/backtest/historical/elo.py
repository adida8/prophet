"""Historical Elo loader.

v1 ships frozen pre-tournament snapshots checked into the repo at
`desk/data/backtest/elo/intl/{yyyymmdd}.json`. The interface is
designed so a future revision can swap in a live Wikipedia revision
pull (MediaWiki API by date) without changing callers.

Lookahead-prevention rule (spec §3.1): if the requested `asof` is
before the earliest snapshot we have, raise `LookaheadError` rather
than silently using a later one. We treat "no exact match" as "use
the latest snapshot at or before `asof`".
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger("desk.backtest.historical.elo")


class LookaheadError(RuntimeError):
    """Raised when no Elo snapshot is available at or before the requested
    date. Refusing to silently use a later one is the whole point."""


# desk/desk/backtest/historical/elo.py → desk/data/backtest/elo/intl
_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data" / "backtest" / "elo" / "intl"
)


def _list_snapshot_dates() -> list[date]:
    if not _DATA_DIR.exists():
        return []
    out: list[date] = []
    for p in _DATA_DIR.glob("*.json"):
        try:
            out.append(datetime.strptime(p.stem, "%Y%m%d").date())
        except ValueError:
            continue
    return sorted(out)


def _snapshot_path(d: date) -> Path:
    return _DATA_DIR / f"{d.strftime('%Y%m%d')}.json"


def load_intl_elo_snapshot(asof: date) -> dict[str, float]:
    """Return `{team_iso3 → elo}` snapshotted at the latest date ≤ `asof`.

    Raises `LookaheadError` when nothing is available at or before `asof`.
    """
    snapshots = _list_snapshot_dates()
    if not snapshots:
        raise LookaheadError(
            f"no Elo snapshots committed under {_DATA_DIR}; "
            "add at least one before backtesting"
        )

    eligible = [d for d in snapshots if d <= asof]
    if not eligible:
        earliest = snapshots[0]
        raise LookaheadError(
            f"asof={asof.isoformat()} is before the earliest committed Elo "
            f"snapshot ({earliest.isoformat()}). Refusing to use a later "
            f"snapshot for a backtest — would leak future information."
        )

    chosen = max(eligible)
    raw = json.loads(_snapshot_path(chosen).read_text(encoding="utf-8"))
    elo = raw.get("elo", {})
    log.debug("loaded intl Elo snapshot %s — %d teams", chosen, len(elo))
    return {k.lower(): float(v) for k, v in elo.items()}


def get_elo(snapshot: dict[str, float], iso3: str, *, default: float = 1500.0) -> float:
    """Return the Elo for `iso3` from a loaded snapshot, with a default."""
    return float(snapshot.get(iso3.lower(), default))
