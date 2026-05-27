"""Team popularity tiers + match-level multipliers for the activity seed engine.

Tier classification reflects expected reader interest, not on-pitch quality.
Names normalise through `iso3_for_name` so the same tier applies regardless
of which display variant the upstream feed uses (Côte d'Ivoire vs Ivory Coast,
Korea Republic vs South Korea, etc.). Unknown names fall to Tier 3 (1×) —
the editorial baseline.

Spec: ACTIVITY_SIGNALS_SPEC.md §"Popularity weighting".
"""

from __future__ import annotations

from desk.sports.football.teams import iso3_for_name

# Keyed by ISO3 lowercase. Anything not listed (including names that fail to
# resolve to an ISO3 at all) resolves as Tier 3 — the editorial default.
POPULARITY_TIER: dict[str, int] = {
    # Tier 1 — Global icons (4×)
    "arg": 1, "bra": 1, "fra": 1, "ger": 1, "esp": 1,
    "ita": 1, "eng": 1, "ned": 1, "por": 1,
    # Tier 2 — Major draws (2×)
    "usa": 2, "mex": 2, "cro": 2, "bel": 2, "uru": 2,
    "jpn": 2, "kor": 2, "sen": 2, "mar": 2,
    "civ": 2, "col": 2, "chi": 2, "che": 2,
    "pol": 2, "den": 2, "aut": 2, "swe": 2,
    # Tier 4 — Niche (0.4×)
    "ksa": 4, "irn": 4, "cuw": 4, "hai": 4, "cpv": 4,
    "jor": 4, "nzl": 4, "irq": 4, "qat": 4, "pan": 4,
    "hon": 4, "slv": 4, "tto": 4,
    "bol": 4, "ven": 4,
}

TIER_MULTIPLIER: dict[int, float] = {1: 4.0, 2: 2.0, 3: 1.0, 4: 0.4}
BLOCKBUSTER_TIERS: frozenset[int] = frozenset({1, 2})
WC26_HOST_ISO3: frozenset[str] = frozenset({"usa", "can", "mex"})

_DEFAULT_TIER = 3
_BLOCKBUSTER_BONUS = 1.25
_HOST_BONUS = 1.5


def tier_for_team(name: str) -> int:
    iso3 = iso3_for_name(name)
    if iso3 is None:
        return _DEFAULT_TIER
    return POPULARITY_TIER.get(iso3, _DEFAULT_TIER)


def match_popularity_multiplier(team_a: str, team_b: str) -> float:
    """Combined seed-target multiplier for a fixture.

    Base = max(tier multipliers across both teams).
    ×1.25 if both teams are Tier 1 or 2 (blockbuster bonus).
    ×1.5  if either team is a WC26 host (USA / Canada / Mexico).
    """
    tier_a = tier_for_team(team_a)
    tier_b = tier_for_team(team_b)
    mult = max(TIER_MULTIPLIER[tier_a], TIER_MULTIPLIER[tier_b])
    if tier_a in BLOCKBUSTER_TIERS and tier_b in BLOCKBUSTER_TIERS:
        mult *= _BLOCKBUSTER_BONUS
    if iso3_for_name(team_a) in WC26_HOST_ISO3 \
            or iso3_for_name(team_b) in WC26_HOST_ISO3:
        mult *= _HOST_BONUS
    return mult
