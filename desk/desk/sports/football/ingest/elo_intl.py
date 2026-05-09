"""International Elo ingest.

PR 3 reads from a frozen seed table (`data/elo_seed.py`). The live
Wikipedia/eloratings.net adapter ships in v1.1; this stub gives the
model a reasonable prior for every WC 2026 nation today.
"""

from __future__ import annotations

from desk.sports.football.data.elo_seed import national_elo


def get_elo(iso3: str) -> float:
    return national_elo(iso3)
