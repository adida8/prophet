"""Final-score → 90-minute winner.

Per spec §3.1: penalty shootouts are NOT counted as 90-min wins. The
match's `winner_90min` field on `HistoricalMatch` already reflects this
because it's the field we hand-curated from each match's 90' score, but
this helper exists for callers who only have the score.
"""

from __future__ import annotations

from typing import Literal

Outcome90 = Literal["a", "b", "draw"]


def winner_from_score(goals_a: int, goals_b: int) -> Outcome90:
    """Map a 90-minute final score to the outcome universe."""
    if goals_a > goals_b:
        return "a"
    if goals_b > goals_a:
        return "b"
    return "draw"
