"""Source registry — loaded once from a checked-in CSV seed.

The seed is a reviewable file (so PR-diffable updates to reliability /
bias_flag are visible). Runtime state (`last_fetched`, content cache)
lives elsewhere; the registry itself is read-only at startup.

De-listing workflow: set `enabled=false` in the seed. Nothing has to be
purged from the DB — the resolver filters by `enabled`.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from desk.signals.models import Source

DEFAULT_SEED_PATH = Path(__file__).resolve().parent / "data" / "sources_seed.csv"

_REQUIRED_COLUMNS = (
    "id", "name", "feed_type", "feed_ref", "language",
    "coverage_tags", "reliability", "bias_flag", "parent_org",
    "tier", "enabled",
)


def _coerce_row(row: dict[str, str]) -> dict[str, object]:
    """CSV gives us strings; coerce the few non-string fields ahead of
    Pydantic validation so error messages point at the right column."""
    out: dict[str, object] = dict(row)
    out["enabled"] = _parse_bool(row.get("enabled", "true"))
    if not row.get("parent_org"):
        out["parent_org"] = None
    return out


def _parse_bool(raw: str) -> bool:
    s = raw.strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n", ""}:
        return False
    raise ValueError(f"cannot parse {raw!r} as bool")


class Registry:
    """In-memory index over the source seed."""

    def __init__(self, sources: Iterable[Source]):
        self._sources = tuple(sources)
        self._by_id: dict[str, Source] = {}
        for s in self._sources:
            if s.id in self._by_id:
                raise ValueError(f"duplicate source id in registry: {s.id!r}")
            self._by_id[s.id] = s

    @classmethod
    def from_csv(cls, path: Path | None = None) -> "Registry":
        path = path or DEFAULT_SEED_PATH
        with path.open(newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            missing = set(_REQUIRED_COLUMNS) - set(reader.fieldnames or ())
            if missing:
                raise ValueError(
                    f"seed {path} is missing required columns: {sorted(missing)}"
                )
            sources = [Source.model_validate(_coerce_row(row)) for row in reader]
        return cls(sources)

    def __len__(self) -> int:
        return len(self._sources)

    def __iter__(self):
        return iter(self._sources)

    def all(self) -> tuple[Source, ...]:
        return self._sources

    def enabled(self) -> tuple[Source, ...]:
        return tuple(s for s in self._sources if s.enabled)

    def get(self, source_id: str) -> Source:
        return self._by_id[source_id]
