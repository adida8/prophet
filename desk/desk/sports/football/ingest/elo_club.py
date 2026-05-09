"""Club Elo ingest.

PR 3 reads from a frozen seed table (`data/elo_seed.py`). v1.1 will
replace this with a ClubElo / FBref live adapter respecting the rate
limits noted in `THE_DESK_SPEC.md` §5 (FBref ≤ 1 req / 3s).
"""

from __future__ import annotations

from desk.sports.football.data.elo_seed import club_elo


def get_elo(club_id: str) -> float:
    return club_elo(club_id)
