"""FIFA metadata adapter — venue + group + kickoff for international fixtures.

PR 3 only handles WC 2026 — the launch wedge. Other tournaments
(Euros, Copa, Africa Cup of Nations) plug in later by adding their
venue tables under `data/`.
"""

from __future__ import annotations

from desk.sports.football.data.wc26_venues import (
    WC26_HOST_ISO3,
    WC26_VENUES,
    WC26Venue,
)


def host_iso3_for_competition(competition_code: str) -> set[str]:
    """Return the ISO3 host nations for a given international competition."""
    if competition_code == "wc26":
        return WC26_HOST_ISO3
    return set()


def venue_for_match(competition_code: str, stadium_name: str | None) -> WC26Venue | None:
    """Find a WC 2026 venue by stadium common name. Returns None for
    competitions we don't yet have venue data for, or stadiums we don't
    recognise — the caller falls back to "no venue", which means no host
    bonus and no altitude bonus.
    """
    if competition_code != "wc26" or not stadium_name:
        return None
    target = stadium_name.strip().lower()
    for v in WC26_VENUES.values():
        if v.stadium.lower() == target:
            return v
    return None
