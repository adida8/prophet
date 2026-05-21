"""Football → signals-registry tag builder.

The signals registry is sport-agnostic and resolves sources by tag
intersection — `country:fr`, `country:ar`, `league:wc26`, etc. This
module turns a football `FixtureRef` into that tag set.

Kept here (not in `desk/signals/`) to preserve the sport boundary:
`desk/signals/` never imports from `desk/sports/*`.
"""

from __future__ import annotations

import unicodedata

from desk.sport import FixtureRef
from desk.sports.football.teams import is_international_competition, iso3_for_name

# Mapping the WC26 field + the major club nations from ISO3 to the
# ISO-2 codes the signals registry uses. Kept small on purpose: when a
# competition adds new countries (Série A, Saudi Pro League, etc.),
# extend this. Don't reach for `pycountry` — the seed registry is
# small and a typo in one place is easier to spot than a stack of
# transitive dependencies.
_ISO3_TO_ISO2: dict[str, str] = {
    # WC26 nations (qualified + plausible play-offs)
    "arg": "ar", "aus": "au", "aut": "at", "bel": "be", "bih": "ba",
    "bra": "br", "can": "ca", "che": "ch", "civ": "ci", "cmr": "cm",
    "col": "co", "crc": "cr", "cze": "cz", "dnk": "dk", "deu": "de",
    "ecu": "ec", "egy": "eg", "eng": "gb", "esp": "es", "fra": "fr",
    "ghn": "gh", "gha": "gh", "irn": "ir", "isr": "il", "ita": "it",
    "jpn": "jp", "kor": "kr", "mar": "ma", "mex": "mx", "ned": "nl",
    "nga": "ng", "nor": "no", "nzl": "nz", "pan": "pa", "par": "py",
    "per": "pe", "pol": "pl", "por": "pt", "qat": "qa", "rou": "ro",
    "rsa": "za", "rus": "ru", "sau": "sa", "sco": "gb", "sen": "sn",
    "srb": "rs", "svk": "sk", "svn": "si", "swe": "se", "tun": "tn",
    "tur": "tr", "ukr": "ua", "ury": "uy", "uru": "uy", "usa": "us",
    "ven": "ve", "wal": "gb", "irl": "ie", "fin": "fi", "alb": "al",
    "hrv": "hr", "hun": "hu",
    "cuw": "cw",  # Curaçao — separate from KOR per the team-id collision fix
    "nir": "gb",
}


def iso2_for_name(name: str) -> str | None:
    """Football team display name → ISO-2 country code (lowercase).
    Returns None if either step fails — callers should fall back to
    other tag sources (e.g. league: tag).
    """
    iso3 = iso3_for_name(name)
    if iso3 is None:
        return None
    return _ISO3_TO_ISO2.get(iso3)


def tags_for(fixture: FixtureRef) -> frozenset[str]:
    """Build the signals-registry tag set for a fixture.

    Always present:
      * "global"                        — tier-1 outlets carrying the global game
      * f"sport:{fixture.sport}"        — football
      * f"league:{competition_code}"    — e.g. league:wc26

    For internationals: `country:{iso2_a}` and `country:{iso2_b}` —
    derived from the team's display name via the football team
    registry.

    For club competitions: `club:{team_a_slug}` / `club:{team_b_slug}`
    — derived from the team's display name with a coarse slug. (Per
    the news-signals spec the club-slug shape is intentionally fuzzy
    until the football club registry sharpens it; today this means
    "Real Madrid" → "real-madrid".)
    """
    tags: set[str] = {
        "global",
        f"sport:{fixture.sport}",
        f"league:{fixture.competition_code}",
    }

    if is_international_competition(fixture.competition_code):
        for name in (fixture.team_a, fixture.team_b):
            iso2 = iso2_for_name(name)
            if iso2:
                tags.add(f"country:{iso2}")
    else:
        for name in (fixture.team_a, fixture.team_b):
            slug = _club_slug(name)
            if slug:
                tags.add(f"club:{slug}")
        # Many country-tagged outlets cover their domestic league too
        # (Marca on La Liga, kicker on the Bundesliga). The fixture
        # carries its venue country — use that as a coarse fallback.
        if fixture.venue_country:
            tags.add(f"country:{fixture.venue_country.lower()}")

    return frozenset(tags)


def _club_slug(name: str) -> str:
    """Coarse name → slug. Fine until we add a club registry; ‘Manchester
    United’ → ‘manchester-united’, ‘Bayern München’ → ‘bayern-munchen’.

    Diacritics are stripped via NFD normalisation + dropping combining
    characters — `ü` is Unicode-alphanumeric, so a naïve `isalnum`
    filter would keep it and produce a non-ASCII slug that wouldn't
    match the all-ASCII tag set in the source seed.
    """
    decomposed = unicodedata.normalize("NFD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = []
    for ch in ascii_only.lower():
        if ch.isascii() and ch.isalnum():
            cleaned.append(ch)
        elif ch.isspace() or ch in "-_/":
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug
