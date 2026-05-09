"""Club metadata adapter — home grounds and club identity.

Wraps `data/club_grounds.py` behind the same interface the FIFA adapter
exposes for international fixtures, so the model code can reason about
"is this team playing at its registered ground?" without branching on
sport.
"""

from __future__ import annotations

from desk.sports.football.data.club_grounds import (
    CLUB_GROUNDS,
    ClubGround,
    home_ground_of,
)

__all__ = ["CLUB_GROUNDS", "ClubGround", "home_ground_of"]
