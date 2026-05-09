"""Club home grounds.

Used by the home-ground bonus. Mutually exclusive with the host bonus —
domestic clubs don't get a host bonus, only the registered home-ground
boost when the venue matches their ground.

Seeded for the obvious early-priced clubs; live ClubElo / FBref ingest
will expand this in v1.1. For unknown clubs, the bonus simply doesn't
fire — the engine always defaults to "no bonus" rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClubGround:
    club_id:     str    # `{league}-{short}`
    stadium:     str
    city:        str
    country_iso2: str
    altitude_m:   float = 0.0


CLUB_GROUNDS: dict[str, ClubGround] = {
    "epl-mun": ClubGround("epl-mun", "Old Trafford",       "Manchester",  "GB", 38.0),
    "epl-liv": ClubGround("epl-liv", "Anfield",            "Liverpool",   "GB", 30.0),
    "epl-mci": ClubGround("epl-mci", "Etihad Stadium",     "Manchester",  "GB", 38.0),
    "epl-ars": ClubGround("epl-ars", "Emirates Stadium",   "London",      "GB", 30.0),
    "epl-che": ClubGround("epl-che", "Stamford Bridge",    "London",      "GB", 30.0),
    "epl-tot": ClubGround("epl-tot", "Tottenham Hotspur Stadium", "London", "GB", 30.0),
    "laliga-rma":      ClubGround("laliga-rma", "Santiago Bernabéu", "Madrid",  "ES", 660.0),
    "laliga-bar":      ClubGround("laliga-bar", "Spotify Camp Nou",  "Barcelona","ES", 12.0),
    "bundesliga-bay":  ClubGround("bundesliga-bay", "Allianz Arena", "Munich",  "DE", 519.0),
    "bundesliga-bvb":  ClubGround("bundesliga-bvb", "Signal Iduna Park", "Dortmund", "DE", 86.0),
    "ligue1-psg":      ClubGround("ligue1-psg", "Parc des Princes", "Paris",   "FR", 35.0),
}


def home_ground_of(club_id: str) -> ClubGround | None:
    return CLUB_GROUNDS.get(club_id.lower())
