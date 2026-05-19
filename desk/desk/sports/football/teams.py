"""Team-id system for football.

National sides use lowercase ISO3. Clubs use `{league}-{short}` where the
short is whatever the league's source feed exposes — Polymarket's slug
fragments today, an editorial registry later.

This module exists so callers don't have to reason about Polymarket's
peculiar codes (`kr` for South Korea, `rsa` for South Africa, etc.).
Anything we know we map; anything we don't, we pass through and TODO.
"""

from __future__ import annotations

# Polymarket → our spec ISO3 for national sides.
# Most are already correct; this dictionary is the exception list.
_NATIONAL_OVERRIDES: dict[str, str] = {
    "kr":  "kor",   # South Korea
    "rsa": "rsa",   # already correct, kept here as a known good
    "che": "che",   # Switzerland
    "ksa": "ksa",   # Saudi Arabia (FIFA code)
    "uae": "uae",
    "ned": "ned",
    "ger": "ger",
    "esp": "esp",
    "por": "por",
    "bra": "bra",
    "arg": "arg",
    "fra": "fra",
    "eng": "eng",
    "mex": "mex",
    "usa": "usa",
    "can": "can",
    "jpn": "jpn",
    "aus": "aus",
    "nzl": "nzl",
    "col": "col",
    "ecu": "ecu",
    "uru": "uru",
    "par": "par",
    "ven": "ven",
    "mar": "mar",
    "egy": "egy",
    "tun": "tun",
    "alg": "alg",
    "sen": "sen",
    "civ": "civ",
    "nga": "nga",
    "gha": "gha",
    "cmr": "cmr",
    "qat": "qat",
    "ira": "irn",
    "irn": "irn",
    "irq": "irq",
    "kor": "kor",
    "prk": "prk",
    "uzb": "uzb",
    "jor": "jor",
    "cze": "cze",
    "cro": "cro",
    "srb": "srb",
    "pol": "pol",
    "swe": "swe",
    "nor": "nor",
    "den": "den",
    "fin": "fin",
    "isl": "isl",
    "tur": "tur",
    "rou": "rou",
    "bel": "bel",
    "aut": "aut",
    "sui": "sui",   # alt for che
    "bih": "bih",
    "alb": "alb",
    "ita": "ita",
    "sco": "sco",
    "wal": "wal",
    "irl": "irl",
    "nir": "nir",
    "rom": "rou",
}

# Competition prefix on Polymarket → our spec competition code/label.
_COMPETITION_MAP: dict[str, tuple[str, str]] = {
    "fifwc":     ("wc26",        "FIFA World Cup 2026"),
    "epl":       ("epl",         "Premier League"),
    "premier":   ("epl",         "Premier League"),
    "esp":       ("laliga",      "La Liga"),
    "es2":       ("laliga2",     "La Liga 2"),
    "ita":       ("seriea",      "Serie A"),
    "ger":       ("bundesliga",  "Bundesliga"),
    "fr1":       ("ligue1",      "Ligue 1"),
    "fr2":       ("ligue2",      "Ligue 2"),
    "ucl":       ("ucl",         "UEFA Champions League"),
    "uel":       ("uel",         "UEFA Europa League"),
    "uecl":      ("uecl",        "UEFA Conference League"),
    "mls":       ("mls",         "Major League Soccer"),
    "tur":       ("superlig",    "Süper Lig"),
    "mar1":      ("botola",      "Botola Pro"),
    "chi1":      ("chilepd",     "Chile Primera División"),
    "col1":      ("colpd",       "Colombia Primera A"),
    "aus":       ("aleague",     "A-League"),
    "nor":       ("eliteserien", "Eliteserien"),
    "jp2":       ("j2",          "J2 League"),
    "isl":       ("isl",         "Indian Super League"),
    "isp":       ("isl",         "Indian Super League"),     # Polymarket alias
    "spl":       ("spl",         "Saudi Pro League"),
    "trsk":      ("trsuperkupa", "Turkish Süper Kupa"),
}


def normalize_team(code: str, *, is_national: bool) -> str:
    """Lowercase + map known overrides. Unknown national codes pass through.

    `is_national` is True for international fixtures (we treat the team as
    a country side) and False for clubs.
    """
    code = code.strip().lower()
    if is_national:
        return _NATIONAL_OVERRIDES.get(code, code)
    return code  # clubs already shipped as their slug fragments


# Display-name → ISO3 disambiguation table. Polymarket reuses some
# slug codes across teams (e.g. `kor` means Korea Republic in most
# slugs but stands for Curaçao — "Kòrsou" in Papiamento — in others).
# When the title gives a clean team name, prefer it for ISO resolution.
_NAME_TO_ISO3: dict[str, str] = {
    # WC26 contenders + common Polymarket title variants.
    "Argentina":               "arg",
    "Australia":               "aus",
    "Austria":                 "aut",
    "Belgium":                 "bel",
    "Bolivia":                 "bol",
    "Bosnia and Herzegovina":  "bih",
    "Brazil":                  "bra",
    "Cameroon":                "cmr",
    "Canada":                  "can",
    "Colombia":                "col",
    "Costa Rica":              "crc",
    "Côte d'Ivoire":           "civ",
    "Ivory Coast":             "civ",
    "Croatia":                 "cro",
    "Curaçao":                 "cuw",
    "Curacao":                 "cuw",
    "Czechia":                 "cze",
    "Czech Republic":          "cze",
    "Denmark":                 "den",
    "Ecuador":                 "ecu",
    "Egypt":                   "egy",
    "England":                 "eng",
    "France":                  "fra",
    "Germany":                 "ger",
    "Ghana":                   "gha",
    "Iran":                    "irn",
    "IR Iran":                 "irn",
    "Iraq":                    "irq",
    "Italy":                   "ita",
    "Japan":                   "jpn",
    "Jordan":                  "jor",
    "Korea Republic":          "kor",
    "South Korea":             "kor",
    "Mexico":                  "mex",
    "Morocco":                 "mar",
    "Netherlands":              "ned",
    "New Zealand":             "nzl",
    "Norway":                  "nor",
    "Paraguay":                "par",
    "Peru":                    "per",
    "Poland":                  "pol",
    "Portugal":                "por",
    "Qatar":                   "qat",
    "Saudi Arabia":            "ksa",
    "Senegal":                 "sen",
    "Serbia":                  "srb",
    "South Africa":            "rsa",
    "Spain":                   "esp",
    "Sweden":                  "swe",
    "Switzerland":             "che",
    "Tunisia":                 "tun",
    "Türkiye":                 "tur",
    "Turkey":                  "tur",
    "United States":           "usa",
    "USA":                     "usa",
    "Uruguay":                 "uru",
    "Uzbekistan":              "uzb",
    "Wales":                   "wal",
    "Algeria":                 "alg",
    "Nigeria":                 "nga",
    "Mali":                    "mli",
    "Cabo Verde":              "cpv",
    "Cape Verde":              "cpv",
    "DR Congo":                "cod",
    "Honduras":                "hon",
    "Panama":                  "pan",
    "Jamaica":                 "jam",
    "Haiti":                   "hai",
    "Venezuela":               "ven",
    "Chile":                   "chi",
    "Iceland":                 "isl",
    "Romania":                 "rou",
    "Scotland":                "sco",
    "Republic of Ireland":     "irl",
    "Ireland":                 "irl",
    "Northern Ireland":        "nir",
    "Finland":                 "fin",
}


def iso3_for_name(name: str) -> str | None:
    """Best-effort resolution of a display name (e.g. "Curaçao") to its
    canonical ISO3 (e.g. "cuw"). Returns None if unknown — callers fall
    back to slug-code resolution.
    """
    return _NAME_TO_ISO3.get(name.strip())


def map_competition(prefix: str) -> tuple[str, str] | None:
    """Polymarket competition prefix → (spec code, human label).

    Returns None for unknown prefixes; callers fall back to the raw prefix
    and emit a TODO log line.
    """
    return _COMPETITION_MAP.get(prefix.lower())


def is_international_competition(competition_code: str) -> bool:
    """True if this competition is fielded by national sides (not clubs)."""
    return competition_code in {
        "wc26", "wc22", "wc18",
        "euro", "copa", "afcon", "asian-cup",
        "wwc", "olympics-football",
    }
