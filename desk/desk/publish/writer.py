"""Static-file publisher.

Writes per-match JSON to `data/output/{sport}/{match_id}.json` and
maintains `data/output/{sport}/index.json`. Every write is atomic (temp
file + rename). Emits an ETag per file via the sibling `<file>.etag`.

The `Publisher` interface is intentionally narrow — the same shape will
back an S3 + CloudFront variant in v1.1 without callers changing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from desk.publish.contract import MatchOutput, MatchOutputIndexEntry, OutputIndex
from desk.publish.etag import canonical_json, content_etag


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class Publisher:
    """Static-file publisher rooted at `output_dir`.

    Layout on disk:
      output_dir/
        {sport}/
          {match_id}.json
          {match_id}.json.etag
          index.json
          index.json.etag
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    # ── per-match ──────────────────────────────────────────────────

    def write_match(self, match: MatchOutput) -> tuple[Path, str]:
        """Write one match. Returns (path, etag)."""
        sport_dir = self.output_dir / match.sport
        path = sport_dir / f"{match.match_id}.json"

        body = match.model_dump(mode="json", exclude_none=False)
        etag = content_etag(body)

        _atomic_write(path, canonical_json(body))
        _atomic_write(path.with_suffix(path.suffix + ".etag"), etag)
        return path, etag

    # ── index ──────────────────────────────────────────────────────

    def write_index(self, sport: str, matches: Iterable[MatchOutput]) -> tuple[Path, str]:
        """Rebuild and write `index.json` for a sport from the supplied matches.

        The publisher does not crawl the directory — callers pass the full
        set, so the index is always coherent with what was just written.
        """
        sport_dir = self.output_dir / sport
        path = sport_dir / "index.json"

        entries = [
            MatchOutputIndexEntry(
                match_id=m.match_id,
                kickoff_utc=m.kickoff_utc,
                updated_at=m.updated_at,
            )
            for m in matches
        ]
        entries.sort(key=lambda e: (e.kickoff_utc, e.match_id))

        idx = OutputIndex(sport=sport, matches=entries, updated_at=_utc_now())
        body = idx.model_dump(mode="json", exclude_none=False)
        etag = content_etag(body)

        _atomic_write(path, canonical_json(body))
        _atomic_write(path.with_suffix(path.suffix + ".etag"), etag)
        return path, etag

    # ── read-back (used by tests + the read API later) ─────────────

    def read_match(self, sport: str, match_id: str) -> MatchOutput:
        path = self.output_dir / sport / f"{match_id}.json"
        return MatchOutput.model_validate_json(path.read_text(encoding="utf-8"))

    def read_index(self, sport: str) -> OutputIndex:
        path = self.output_dir / sport / "index.json"
        return OutputIndex.model_validate_json(path.read_text(encoding="utf-8"))
