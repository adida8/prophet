"""Source registry — loaded once from a checked-in CSV seed.

The seed is a reviewable file (so PR-diffable updates to reliability /
bias_flag are visible). Runtime state (`last_fetched`, content cache)
lives elsewhere; the registry itself is read-only at startup.

De-listing workflow: set `enabled=false` in the seed. Nothing has to be
purged from the DB — the resolver filters by `enabled`.

Bad rows fail loud: a single malformed row raises with the row index
and source id so the operator can fix the seed and re-run.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from desk.signals.models import Source

DEFAULT_SEED_PATH = Path(__file__).resolve().parent / "data" / "sources_seed.csv"

# Columns the loader requires to be present in the CSV header. Optional
# columns — `parent_org`, `notes` — may be present but are not required.
_REQUIRED_COLUMNS = (
    "id", "name", "feed_type", "feed_ref", "language",
    "coverage_tags", "reliability", "bias_flag",
    "tier", "enabled",
)
_OPTIONAL_COLUMNS = ("parent_org", "notes")


def _coerce_row(row: dict[str, str]) -> dict[str, object]:
    """CSV gives us strings; coerce the few non-string fields ahead of
    Pydantic validation so error messages point at the right column."""
    out: dict[str, object] = {
        k: row.get(k) for k in (*_REQUIRED_COLUMNS, *_OPTIONAL_COLUMNS) if k in row
    }
    out["enabled"] = _parse_bool(row.get("enabled", "true"))
    if not row.get("parent_org"):
        out["parent_org"] = None
    if not row.get("notes"):
        out["notes"] = None
    # `feed_ref` may be empty for feed_type=none; the model's validator
    # cross-checks the pair.
    out["feed_ref"] = (row.get("feed_ref") or "").strip()
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
            sources: list[Source] = []
            for line_no, row in enumerate(reader, start=2):  # header is line 1
                try:
                    sources.append(Source.model_validate(_coerce_row(row)))
                except ValidationError as e:
                    src_id = (row.get("id") or "<no id>").strip()
                    raise ValueError(
                        f"{path}:{line_no} source {src_id!r}: {_fmt_errors(e)}"
                    ) from e
                except ValueError as e:
                    src_id = (row.get("id") or "<no id>").strip()
                    raise ValueError(
                        f"{path}:{line_no} source {src_id!r}: {e}"
                    ) from e
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


def _fmt_errors(e: ValidationError) -> str:
    """Compact one-liner for a ValidationError. Pydantic's default
    multiline format is fine for a developer but loses context when
    we wrap it with the source-id prefix in the loader."""
    parts = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts) or str(e)
