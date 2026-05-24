"""Team-code → ISO2 flag filename map.

The Desk's team short-codes (the `cro`, `fra`, `gb-eng` triplets that
appear in `match_id`) don't always match the ISO-3166-1 alpha-2 code
flag SVGs are filed under. Two examples:

    cro (Croatia)         → hr.svg
    eng (England)         → gb-eng.svg

This module is the **single source of truth** for that mapping. Both
`site/generate.py` (static site) and `frontend/src/desk/teamFlags.js`
(React app) read from the same set of codes; keep the two in sync.

If you add a team here, also add the corresponding SVG under
`site/public/flags/` (served by the static site) and
`frontend/public/flags/` (served by the React app via Vite).
"""

from __future__ import annotations


# team-code (lowercase, from match_id) → ISO2 flag filename stub.
TEAM_CODE_TO_ISO2: dict[str, str] = {
    "alg": "dz",
    "arg": "ar",
    "aus": "au",
    "aut": "at",
    "bel": "be",
    "bih": "ba",
    "bra": "br",
    "can": "ca",
    "che": "ch",
    "civ": "ci",
    "cod": "cd",
    "col": "co",
    "cpv": "cv",
    "cro": "hr",
    "cuw": "cw",
    "cze": "cz",
    "ecu": "ec",
    "egy": "eg",
    "eng": "gb-eng",
    "esp": "es",
    "fra": "fr",
    "ger": "de",
    "gha": "gh",
    "hai": "ht",
    "irn": "ir",
    "irq": "iq",
    "jor": "jo",
    "jpn": "jp",
    "kor": "kr",
    "ksa": "sa",
    "mar": "ma",
    "mex": "mx",
    "ned": "nl",
    "nor": "no",
    "nzl": "nz",
    "pan": "pa",
    "par": "py",
    "por": "pt",
    "qat": "qa",
    "rsa": "za",
    "sco": "gb-sct",
    "sen": "sn",
    "swe": "se",
    "tun": "tn",
    "tur": "tr",
    "uru": "uy",
    "usa": "us",
    "uzb": "uz",
    "nga": "ng",
    "cmr": "cm",
    "crc": "cr",
    "den": "dk",
    "fin": "fi",
    "irl": "ie",
    "isl": "is",
    "ita": "it",
    "jam": "jm",
    "hon": "hn",
    "mli": "ml",
    "nir": "gb-nir",
    "per": "pe",
    "pol": "pl",
    "prk": "kp",
    "rou": "ro",
    "srb": "rs",
    "uae": "ae",
    "ven": "ve",
    "wal": "gb-wls",
    "chi": "cl",
    "alb": "al",
    "bol": "bo",
}


def flag_iso2(team_code: str | None) -> str | None:
    """Return the ISO2 flag filename stub for a team code, or None."""
    if not team_code:
        return None
    return TEAM_CODE_TO_ISO2.get(team_code.strip().lower())


def flag_path(team_code: str | None) -> str:
    """Return the URL path to the flag SVG (falls back to `_unknown.svg`)."""
    return f"/flags/{flag_iso2(team_code) or '_unknown'}.svg"


def team_codes_from_match_id(match_id: str | None) -> tuple[str | None, str | None]:
    """Pull the two team short-codes out of `fb-{comp}-{a}-{b}-{yyyymmdd}`.

    Returns `(None, None)` if the id doesn't match the expected shape.
    """
    if not match_id:
        return (None, None)
    parts = match_id.split("-")
    if len(parts) < 5:
        return (None, None)
    return (parts[2], parts[3])
