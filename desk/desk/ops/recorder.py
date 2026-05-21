"""Recorder — persists `RunReport`s + maintains the manifest.

Mirrors the atomic-write discipline of `desk/publish/writer.py`: every
write goes through a temp file + rename so a crashed mid-write never
leaves a half-written run log.

Layout on disk:
    {root}/
      runs/
        {run_id}.json
      index.json

Retention prunes the oldest run files past `DESK_OPS_RETENTION`
(default 200). The cap is a sane default — the manifest stays small,
and 200 runs is roughly 50 hours at the planned 15-min cadence.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from desk.publish.etag import canonical_json
from desk.ops.report import (
    RUN_ID_RE,
    RunManifest,
    RunReport,
    manifest_entry_from_report,
)

log = logging.getLogger("desk.ops.recorder")

DEFAULT_RETENTION = 200


def _retention() -> int:
    try:
        n = int(os.getenv("DESK_OPS_RETENTION", str(DEFAULT_RETENTION)))
    except ValueError:
        return DEFAULT_RETENTION
    return max(1, n)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


class Recorder:
    """Persist `RunReport`s under `root/runs/{run_id}.json` + maintain
    `root/index.json`. Pure I/O — building the report is the runner's job.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.runs_dir = self.root / "runs"
        self.index_path = self.root / "index.json"

    # ── write ─────────────────────────────────────────────────────

    def persist(self, report: RunReport) -> Path:
        """Write the report + refresh the manifest + prune the tail.

        Returns the path to the written report. Idempotent on `run_id`
        — re-writing the same id overwrites the file and the matching
        manifest row.
        """
        path = self.runs_dir / f"{report.run_id}.json"
        body = report.model_dump(mode="json", exclude_none=False, by_alias=True)
        _atomic_write(path, canonical_json(body))

        self._refresh_manifest()
        self._prune()
        return path

    def _refresh_manifest(self) -> None:
        """Rebuild `index.json` from the run files on disk.

        Reads each file just for the manifest fields — cheap because the
        reports are small. We rebuild rather than patch so the manifest
        always matches what's actually persisted (catches dropped writes,
        manual deletions, etc).
        """
        if not self.runs_dir.exists():
            return
        entries = []
        for f in sorted(self.runs_dir.iterdir()):
            if not f.is_file() or f.suffix != ".json":
                continue
            if not RUN_ID_RE.match(f.stem):
                continue
            try:
                report = RunReport.model_validate_json(f.read_text(encoding="utf-8"))
            except Exception as e:                          # noqa: BLE001
                log.warning("skipping unreadable run log %s: %s", f.name, e)
                continue
            entries.append(manifest_entry_from_report(report))

        # Newest first — the dashboard reads top-down.
        entries.sort(key=lambda e: e.finished_at, reverse=True)
        manifest = RunManifest(
            runs=entries,
            updated_at=datetime.now(tz=timezone.utc),
        )
        body = manifest.model_dump(mode="json", exclude_none=False, by_alias=True)
        _atomic_write(self.index_path, canonical_json(body))

    def _prune(self) -> None:
        """Drop run files past the retention cap, oldest first."""
        if not self.runs_dir.exists():
            return
        files = [
            f for f in self.runs_dir.iterdir()
            if f.is_file() and f.suffix == ".json" and RUN_ID_RE.match(f.stem)
        ]
        if len(files) <= _retention():
            return
        # Sort oldest → newest by name; run_id sorts the same as time.
        files.sort(key=lambda f: f.name)
        for old in files[: len(files) - _retention()]:
            try:
                old.unlink()
            except OSError as e:
                log.warning("failed to prune %s: %s", old.name, e)
        self._refresh_manifest()

    # ── read ──────────────────────────────────────────────────────

    def latest(self) -> RunReport | None:
        if not self.runs_dir.exists():
            return None
        files = sorted(
            (f for f in self.runs_dir.iterdir()
             if f.is_file() and f.suffix == ".json" and RUN_ID_RE.match(f.stem)),
            key=lambda f: f.name,
        )
        if not files:
            return None
        return self.read(files[-1].stem)

    def read(self, run_id: str) -> RunReport:
        path = self.runs_dir / f"{run_id}.json"
        return RunReport.model_validate_json(path.read_text(encoding="utf-8"))

    def manifest(self) -> RunManifest:
        if not self.index_path.exists():
            return RunManifest(runs=[], updated_at=datetime.now(tz=timezone.utc))
        return RunManifest.model_validate_json(
            self.index_path.read_text(encoding="utf-8")
        )

    def previous_snapshot(self, before_run_id: str) -> list | None:
        """Return the `snapshot` from the most recent run BEFORE the given
        run_id, or None if there is none. Used by PR 3's diff engine.
        """
        if not self.runs_dir.exists():
            return None
        candidates = sorted(
            (f.stem for f in self.runs_dir.iterdir()
             if f.is_file() and f.suffix == ".json"
             and RUN_ID_RE.match(f.stem) and f.stem < before_run_id),
        )
        if not candidates:
            return None
        return self.read(candidates[-1]).snapshot
