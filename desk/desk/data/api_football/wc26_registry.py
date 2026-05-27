"""WC 2026 national-team registry — canonical ISO3 → api-football search.

Inputs to the api-football `/teams?search=...` endpoint when bootstrapping
a missing team_id. Search strings are the form api-football's payload
returns under `team.name` for the national side. Curated rather than
derived because:

  * National-side names on api-football have idiosyncratic spelling
    (e.g. "USA" not "United States", "Korea Republic" not "South Korea").
  * Bootstrapping is rare — once a team's id is in the cache, it's
    permanent. The cost of a wrong search hit is high (every form_delta
    for that team would be wrong), so we name-match deliberately.

Coverage: every team currently rated >= 1500 in the seed Elo + every
likely WC26 qualifier. ~70 entries to give the resolver headroom; the
fetcher only resolves teams that actually appear in upcoming priced
fixtures.
"""

from __future__ import annotations

# Canonical ISO3 → exact `team.name` string returned by api-football's
# /teams endpoint for the **national** side. Verified against
# api-football v3 docs sample payloads as of 2026-05-27.
WC26_NATIONAL_REGISTRY: dict[str, str] = {
    # Top tier
    "arg": "Argentina",
    "fra": "France",
    "esp": "Spain",
    "bra": "Brazil",
    "eng": "England",
    "por": "Portugal",
    "ned": "Netherlands",
    "ger": "Germany",
    "ita": "Italy",
    "bel": "Belgium",
    "cro": "Croatia",
    # Strong mid
    "col": "Colombia",
    "uru": "Uruguay",
    "che": "Switzerland",
    "mex": "Mexico",
    "aut": "Austria",
    "den": "Denmark",
    "usa": "USA",
    "mar": "Morocco",
    "srb": "Serbia",
    "sen": "Senegal",
    "ecu": "Ecuador",
    "jpn": "Japan",
    "kor": "Korea Republic",
    "egy": "Egypt",
    "nor": "Norway",
    "alg": "Algeria",
    "tur": "Turkey",
    "sco": "Scotland",
    "nga": "Nigeria",
    "aus": "Australia",
    "irn": "Iran",
    "cze": "Czech Republic",
    "civ": "Ivory Coast",
    "ven": "Venezuela",
    "par": "Paraguay",
    "wal": "Wales",
    "pol": "Poland",
    "irl": "Republic of Ireland",
    "chi": "Chile",
    "can": "Canada",
    # Lower tier
    "rou": "Romania",
    "mli": "Mali",
    "cmr": "Cameroon",
    "isl": "Iceland",
    "tun": "Tunisia",
    "ksa": "Saudi Arabia",
    "gha": "Ghana",
    "rsa": "South Africa",
    "crc": "Costa Rica",
    "cod": "DR Congo",
    "qat": "Qatar",
    "bol": "Bolivia",
    "uzb": "Uzbekistan",
    "swe": "Sweden",
    "fin": "Finland",
    "per": "Peru",
    "bih": "Bosnia and Herzegovina",
    "nir": "Northern Ireland",
    "pan": "Panama",
    "cpv": "Cape Verde Islands",
    "irq": "Iraq",
    "jor": "Jordan",
    "jam": "Jamaica",
    "nzl": "New Zealand",
    "hon": "Honduras",
    "cuw": "Curacao",
    "hai": "Haiti",
    "slv": "El Salvador",
    "tto": "Trinidad and Tobago",
}


def search_query_for_iso3(iso3: str) -> str | None:
    """Return the search string to pass to api-football's
    `/teams?search=` endpoint for a given canonical ISO3. None if the
    team isn't in the WC26 registry (the resolver then skips it rather
    than guessing)."""
    return WC26_NATIONAL_REGISTRY.get(iso3.lower())
