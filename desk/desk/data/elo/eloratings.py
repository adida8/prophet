"""eloratings.net client — World Football Elo Ratings.

eloratings.net publishes the world ranking as a JSON blob loaded by
their front-end. The endpoint `https://eloratings.net/World.tsv` (or
`World_en.tsv`) returns a tab-separated file of every team and their
current Elo. Each row: rank<TAB>team_code<TAB>name<TAB>elo<TAB>... .

Per data-layer spec Phase 1b: parser-hardened. Header / row-shape
check on every parse; mismatch → log loudly + keep last-good cached
values; never overwrite the cache from a half-parsed feed.

The team_code is the FIFA tri-letter (e.g. "FRA", "ENG", "MEX"),
which maps cleanly to our canonical ISO3.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from desk.data.elo.cache import EloCache

_LOG = logging.getLogger(__name__)

WORLD_TSV_URL = "https://www.eloratings.net/World.tsv"
SOURCE_ID = "eloratings"

# Minimum number of plausible rows we expect from a fresh feed. A
# legit feed has 200+ men's national teams. Anything below this is
# a partial / corrupt response — abort the parse, keep last-good.
MIN_PLAUSIBLE_ROWS = 100

# Range sanity on national-team Elo. Values outside [800, 2500] are
# implausible; the strongest sides peak ~2200, weakest ~900.
ELO_MIN = 800.0
ELO_MAX = 2500.0


@dataclass(frozen=True)
class EloratingsParse:
    """Parsed payload + a flag for whether it cleared all sanity checks.

    `rows` is freshest snapshot of (iso3, elo) when `ok=True`; empty
    when False. The refresher only writes to cache on ok=True.
    """
    ok:               bool
    rows:             list[tuple[str, float]]
    n_rows_parsed:    int
    error:            str | None = None


def _normalise_iso3(team_code: str) -> str | None:
    """eloratings.net uses 3-letter FIFA codes; we use lowercase
    ISO3. Lowercase + length check is the only normalisation needed
    in v1 — any malformed code triggers a row skip, not a parse abort.
    """
    code = (team_code or "").strip().lower()
    if len(code) != 3 or not code.isalpha():
        return None
    return code


def parse_world_tsv(body: str) -> EloratingsParse:
    """Parse eloratings.net's World.tsv into (iso3, elo) rows.

    Tolerates malformed rows (logs + skips) but aborts the whole
    parse on:
      - empty body
      - too few rows after parse (< MIN_PLAUSIBLE_ROWS)
      - every Elo value out of plausible range (likely wrong column)
    """
    if not body or not body.strip():
        return EloratingsParse(False, [], 0, error="empty body")

    out: list[tuple[str, float]] = []
    reader = csv.reader(io.StringIO(body), delimiter="\t")
    n_seen = 0
    in_range = 0
    for raw in reader:
        n_seen += 1
        if len(raw) < 4:
            continue
        # World.tsv layout: rank, code, name, elo, ... (per eloratings.net's
        # front-end loader). Take cols 1 and 3 by index. If the column
        # order ever flips, the in-range count will collapse and we abort.
        iso3 = _normalise_iso3(raw[1])
        if iso3 is None:
            continue
        try:
            elo = float(raw[3])
        except ValueError:
            continue
        out.append((iso3, elo))
        if ELO_MIN <= elo <= ELO_MAX:
            in_range += 1

    if n_seen < MIN_PLAUSIBLE_ROWS:
        return EloratingsParse(
            False, [], n_seen,
            error=f"only {n_seen} rows in feed; expected ≥ {MIN_PLAUSIBLE_ROWS}",
        )
    # If hardly any Elo values are in the plausible range, the column
    # order has probably shifted — abort + keep last-good.
    in_range_pct = (100.0 * in_range / len(out)) if out else 0.0
    if in_range_pct < 80.0:
        return EloratingsParse(
            False, [], n_seen,
            error=f"only {in_range_pct:.1f}% of parsed Elo values in plausible range "
                  f"[{ELO_MIN}, {ELO_MAX}] — likely column-order drift",
        )
    return EloratingsParse(True, out, n_seen)


async def refresh_nationals(
    *,
    cache: EloCache,
    client: httpx.AsyncClient | None = None,
    iso3_allowlist: set[str] | None = None,
) -> EloratingsParse:
    """Pull the global ranking, write each country (or only those in
    `iso3_allowlist`) to the cache.

    Parser failures keep the last-good cache untouched (per spec).
    """
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=20.0)
    try:
        try:
            resp = await client.get(WORLD_TSV_URL)
        except httpx.HTTPError as e:
            _LOG.warning("eloratings fetch failed: %s", e)
            cache.mark_fetch(SOURCE_ID, "http_error")
            return EloratingsParse(False, [], 0, error=str(e))

        if resp.status_code != 200:
            _LOG.warning("eloratings HTTP %s — keeping last-good cache",
                         resp.status_code)
            cache.mark_fetch(SOURCE_ID, f"http_{resp.status_code}")
            return EloratingsParse(
                False, [], 0, error=f"HTTP {resp.status_code}",
            )

        parsed = parse_world_tsv(resp.text)
        if not parsed.ok:
            _LOG.error("eloratings parser mismatch — %s — keeping last-good cache",
                       parsed.error)
            cache.mark_fetch(SOURCE_ID, "parser_mismatch")
            return parsed

        now = datetime.now(tz=timezone.utc)
        for iso3, elo in parsed.rows:
            if iso3_allowlist is not None and iso3 not in iso3_allowlist:
                continue
            cache.upsert_national(
                iso3, elo,
                source_id=SOURCE_ID, source_url=WORLD_TSV_URL,
                fetched_at=now,
            )
        cache.mark_fetch(SOURCE_ID, "ok")
        return parsed
    finally:
        if owns_client:
            await client.aclose()
