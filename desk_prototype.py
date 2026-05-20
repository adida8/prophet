"""Desk prototype — outrights + matches, using the engine's ingredients only.

NOT the production engine. A throwaway script that:
  - reads the static Elo table from `desk/desk/sports/football/data/elo_seed.py`
    (supplemented with rough public Elo for WC 2026 teams missing from the seed),
  - reuses the engine's pairwise probability function (`_probs_from_elos`),
  - pulls current Polymarket prices (soccer match events + the WC winner event),
  - for matches:    computes a Pick/Pass/Avoid per side using the existing
                    3/1/-1.5 pp thresholds (no liquidity / stub / band gates —
                    deliberately bare, this is a sanity check, not the engine),
  - for outrights:  runs a Monte Carlo over the WC 2026 group→knockout bracket
                    using the same pairwise primitive, counts each team's wins,
                    computes per-team edges, applies Pick/Pass/Avoid.

Limitations baked in (and the point):
  - Static Elo (stale, no live update). Teams not in the seed table get a
    rough public-Elo top-up so the prototype isn't dominated by 1500 stubs.
  - No host/altitude per-match bonuses (we don't have the venue per fixture).
  - No injuries, weather, form, news.
  - Knockout draws resolved by Elo-weighted coin flip.
  - R32 bracket uses standard seeded single-elimination — FIFA's actual
    cross-group bracket differs in detail; the headline P(win) is close.
  - No confidence band — bootstrapping would triple runtime.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
import urllib.request
from collections import defaultdict
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Elo — from the repo's seed table, plus rough public top-ups for WC teams
# missing from the seed. Top-ups are approximate and flagged in output.
# ─────────────────────────────────────────────────────────────────────────────

SEED_NATIONAL_ELO: dict[str, float] = {
    # Copied verbatim from desk/sports/football/data/elo_seed.py:NATIONAL_ELO
    "fra": 2050.0, "arg": 2070.0, "esp": 2030.0, "bra": 2000.0, "eng": 1990.0,
    "ger": 1970.0, "por": 1950.0, "ned": 1940.0, "ita": 1930.0, "bel": 1880.0,
    "usa": 1820.0, "mex": 1830.0, "cro": 1900.0, "uru": 1880.0, "col": 1870.0,
    "ecu": 1810.0, "sen": 1800.0, "mar": 1830.0, "jpn": 1810.0, "kor": 1790.0,
    "aus": 1760.0, "can": 1720.0, "qat": 1720.0,
    "rsa": 1620.0, "alg": 1740.0, "cmr": 1730.0, "egy": 1730.0, "tun": 1670.0,
    "gha": 1660.0, "civ": 1740.0, "irn": 1750.0, "uzb": 1640.0, "ksa": 1640.0,
    "che": 1840.0, "sui": 1840.0, "par": 1700.0, "ven": 1690.0, "bol": 1700.0,
    "cze": 1830.0, "srb": 1850.0, "bih": 1700.0, "isl": 1680.0, "wal": 1810.0,
}

# Rough public Elo for teams not in the seed table (eloratings.net region).
# Approximate to within ~30-50 Elo — flagged in output where used.
SUPPLEMENT_NATIONAL_ELO: dict[str, float] = {
    "sco": 1760.0,  # Scotland
    "tur": 1830.0,  # Turkey/Türkiye
    "swe": 1790.0,  # Sweden
    "nor": 1840.0,  # Norway
    "aut": 1820.0,  # Austria
    "jor": 1640.0,  # Jordan
    "cod": 1670.0,  # DR Congo
    "pan": 1640.0,  # Panama
    "irq": 1650.0,  # Iraq
    "nzl": 1530.0,  # New Zealand
    "cpv": 1620.0,  # Cape Verde
    "hai": 1520.0,  # Haiti
    "cuw": 1540.0,  # Curaçao
    "den": 1820.0,  # Denmark
    "pol": 1780.0,  # Poland
    "ukr": 1770.0,  # Ukraine
    "fin": 1690.0,  # Finland
    "rom": 1690.0,  # Romania
    "hun": 1690.0,  # Hungary
    "gre": 1740.0,  # Greece
    "ire": 1710.0,  # Ireland
    "nir": 1610.0,  # Northern Ireland
    "sct": 1760.0,  # alt for Scotland
}

NATIONAL_ELO = {**SEED_NATIONAL_ELO, **SUPPLEMENT_NATIONAL_ELO}

def elo_source(iso3: str) -> str:
    k = iso3.lower()
    if k in SEED_NATIONAL_ELO:   return "seed"
    if k in SUPPLEMENT_NATIONAL_ELO: return "public-approx"
    return "stub-1500"

def national_elo(iso3: str) -> float:
    return NATIONAL_ELO.get(iso3.lower(), 1500.0)

# Club Elo seeds — verbatim from the seed file.
CLUB_ELO: dict[str, float] = {
    "epl-mun": 1810.0, "epl-liv": 1880.0, "epl-mci": 1990.0, "epl-ars": 1940.0,
    "epl-che": 1850.0, "epl-tot": 1830.0, "laliga-rma": 2000.0, "laliga-bar": 1980.0,
    "bundesliga-bay": 1990.0, "bundesliga-bvb": 1860.0, "ligue1-psg": 1980.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# Pairwise probability — verbatim from desk/sports/football/model.py:_probs_from_elos
# ─────────────────────────────────────────────────────────────────────────────

DRAW_PEAK         = 0.30
DRAW_FLOOR        = 0.10
DRAW_DECAY_PER_ELO = 0.0006

def probs_from_elos(elo_a: float, elo_b: float) -> tuple[float, float, float]:
    diff       = elo_a - elo_b
    expected_a = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    p_draw     = max(DRAW_FLOOR, DRAW_PEAK - DRAW_DECAY_PER_ELO * abs(diff))
    win_share  = 1.0 - p_draw
    p_a        = expected_a * win_share
    p_b        = (1.0 - expected_a) * win_share
    s = p_a + p_draw + p_b
    return p_a/s, p_draw/s, p_b/s

# Thresholds — from desk/verdict/thresholds.py defaults
PICK_PP  =  3.0
PASS_PP  =  1.0
AVOID_PP = -1.5

def verdict(edge_pp: float) -> str:
    if edge_pp >= PICK_PP:   return "PICK"
    if edge_pp <= AVOID_PP:  return "AVOID"
    if abs(edge_pp) < PASS_PP: return "pass"
    return "—"

# ─────────────────────────────────────────────────────────────────────────────
# Polymarket gamma fetch
# ─────────────────────────────────────────────────────────────────────────────

GAMMA = "https://gamma-api.polymarket.com"

def http_get(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "desk-prototype/0.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def parse_outcome_prices(raw: Any) -> list[float] | None:
    if raw is None: return None
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except json.JSONDecodeError: return None
    if not isinstance(raw, list): return None
    try: return [float(x) for x in raw]
    except (TypeError, ValueError): return None

def yes_index(outcomes: Any) -> int | None:
    if isinstance(outcomes, str):
        try: outcomes = json.loads(outcomes)
        except json.JSONDecodeError: return None
    if not isinstance(outcomes, list): return None
    for i, o in enumerate(outcomes):
        if isinstance(o, str) and o.strip().lower() == "yes":
            return i
    return None

# ─────────────────────────────────────────────────────────────────────────────
# WC 2026 bracket — pulled from Wikipedia per-group pages (see survey)
# ─────────────────────────────────────────────────────────────────────────────

WC26_GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# Display-name → ISO3 for Elo lookup
NAME_TO_ISO3 = {
    "Mexico":"mex","South Africa":"rsa","South Korea":"kor","Czech Republic":"cze",
    "Canada":"can","Bosnia and Herzegovina":"bih","Qatar":"qat","Switzerland":"sui",
    "Brazil":"bra","Morocco":"mar","Haiti":"hai","Scotland":"sco",
    "United States":"usa","Paraguay":"par","Australia":"aus","Turkey":"tur","Türkiye":"tur",
    "Germany":"ger","Curaçao":"cuw","Curacao":"cuw","Ivory Coast":"civ","Côte d'Ivoire":"civ","Ecuador":"ecu",
    "Netherlands":"ned","Japan":"jpn","Sweden":"swe","Tunisia":"tun",
    "Belgium":"bel","Egypt":"egy","Iran":"irn","New Zealand":"nzl",
    "Spain":"esp","Cape Verde":"cpv","Cabo Verde":"cpv","Saudi Arabia":"ksa","Uruguay":"uru",
    "France":"fra","Senegal":"sen","Iraq":"irq","Norway":"nor",
    "Argentina":"arg","Algeria":"alg","Austria":"aut","Jordan":"jor",
    "Portugal":"por","DR Congo":"cod","Democratic Republic of the Congo":"cod","Uzbekistan":"uzb","Colombia":"col",
    "England":"eng","Croatia":"cro","Ghana":"gha","Panama":"pan",
    # Common aliases that appear in Polymarket
    "USA":"usa","South Korea (Republic of)":"kor",
}

def iso3_for(name: str) -> str | None:
    if name in NAME_TO_ISO3: return NAME_TO_ISO3[name]
    # try without accents
    norm = re.sub(r'[^\w\s\']', '', name).strip()
    return NAME_TO_ISO3.get(norm)

# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo — WC 2026 outright winner
# ─────────────────────────────────────────────────────────────────────────────

def simulate_match(elo_a: float, elo_b: float, knockout: bool, rng: random.Random) -> int:
    """Return 0 (a wins), 1 (b wins). For group games returns 0/1/2 (a/b/draw)."""
    p_a, p_draw, p_b = probs_from_elos(elo_a, elo_b)
    r = rng.random()
    if knockout:
        # Redistribute draw share to winning sides proportionally (Elo-weighted coin flip)
        total_win = p_a + p_b
        if total_win <= 0: return 0
        if r < p_a / total_win: return 0
        return 1
    if r < p_a: return 0
    if r < p_a + p_b: return 1
    return 2

def run_group(teams: list[str], rng: random.Random) -> list[tuple[str, int, int, int]]:
    """Round-robin. Returns standings: [(team, points, GD_proxy, plays)] sorted."""
    pts = {t: 0 for t in teams}
    gd  = {t: 0.0 for t in teams}   # tiebreak proxy from Elo
    for i in range(len(teams)):
        for j in range(i+1, len(teams)):
            a, b = teams[i], teams[j]
            ea = national_elo(iso3_for(a) or "")
            eb = national_elo(iso3_for(b) or "")
            r = simulate_match(ea, eb, knockout=False, rng=rng)
            if r == 0:   pts[a] += 3; gd[a] += 1; gd[b] -= 1
            elif r == 1: pts[b] += 3; gd[b] += 1; gd[a] -= 1
            else:        pts[a] += 1; pts[b] += 1
    # rank: points DESC, gd DESC, Elo DESC (tiebreak proxy)
    standings = sorted(teams, key=lambda t: (-pts[t], -gd[t], -national_elo(iso3_for(t) or "")))
    return [(t, pts[t], int(gd[t]), len(teams)-1) for t in standings]

def simulate_wc(rng: random.Random) -> str:
    """Run one tournament. Return the team that lifts the trophy."""
    # 1. Group stage
    group_results: dict[str, list[tuple[str,int,int,int]]] = {}
    for gid, teams in WC26_GROUPS.items():
        group_results[gid] = run_group(teams, rng)
    # 2. Qualifiers: winners (12) + runners-up (12) + 8 best 3rd-placed
    winners   = [(g, group_results[g][0]) for g in WC26_GROUPS]
    runners   = [(g, group_results[g][1]) for g in WC26_GROUPS]
    thirds    = [(g, group_results[g][2]) for g in WC26_GROUPS]
    thirds_sorted = sorted(thirds, key=lambda gx: (-gx[1][1], -gx[1][2], -national_elo(iso3_for(gx[1][0]) or "")))
    best_8_thirds = thirds_sorted[:8]
    # 3. Seed all 32 qualifiers — simple seeding: winners > runners > thirds, within each by points desc.
    qualified: list[str] = []
    qualified += [t[0] for _, t in sorted(winners, key=lambda gx: (-gx[1][1], -gx[1][2], -national_elo(iso3_for(gx[1][0]) or "")))]
    qualified += [t[0] for _, t in sorted(runners, key=lambda gx: (-gx[1][1], -gx[1][2], -national_elo(iso3_for(gx[1][0]) or "")))]
    qualified += [t[0] for _, t in best_8_thirds]
    # 4. Standard seeded bracket: 1v32, 2v31, ..., 16v17 → R32
    bracket = list(qualified)  # already in seed order
    while len(bracket) > 1:
        # Pair top with bottom in current bracket
        next_round = []
        n = len(bracket)
        for i in range(n // 2):
            a, b = bracket[i], bracket[n-1-i]
            ea = national_elo(iso3_for(a) or "")
            eb = national_elo(iso3_for(b) or "")
            r = simulate_match(ea, eb, knockout=True, rng=rng)
            next_round.append(a if r == 0 else b)
        bracket = next_round
    return bracket[0]

# ─────────────────────────────────────────────────────────────────────────────
# Fetch Polymarket prices
# ─────────────────────────────────────────────────────────────────────────────

WC_WINNER_SLUG = "2026-fifa-world-cup-winner-595"

def fetch_wc_winner_market() -> dict[str, float]:
    """Return {team_display_name: yes_implied_p}."""
    data = http_get(f"{GAMMA}/events?slug={WC_WINNER_SLUG}")
    if not data:
        return {}
    ev = data[0]
    out: dict[str, float] = {}
    for m in ev.get("markets") or []:
        q = (m.get("question") or "").strip()
        # "Will France win the 2026 FIFA World Cup?"
        match = re.match(r"^Will (.+?) win the 2026 FIFA World Cup\??$", q, re.IGNORECASE)
        if not match:
            # Try alt phrasings
            match = re.match(r"^Will (.+?) win", q, re.IGNORECASE)
        if not match:
            continue
        team_name = match.group(1).strip()
        prices = parse_outcome_prices(m.get("outcomePrices"))
        if not prices: continue
        yi = yes_index(m.get("outcomes"))
        if yi is None or yi >= len(prices): continue
        yes = prices[yi]
        if 0.0 <= yes <= 1.0:
            out[team_name] = yes
    return out

def fetch_soccer_match_events(limit: int = 200) -> list[dict[str, Any]]:
    """Mirror PolymarketSoccerEventsSource."""
    data = http_get(f"{GAMMA}/events?tag_slug=games&closed=false&active=true&limit={limit}")
    return [e for e in data if "soccer" in {t.get("slug") for t in e.get("tags", [])}]

# ─────────────────────────────────────────────────────────────────────────────
# Match analysis — engine-style
# ─────────────────────────────────────────────────────────────────────────────

def strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()

def classify_market(question: str, team_a: str, team_b: str) -> str | None:
    q = strip_accents(question)
    a = strip_accents(team_a)
    b = strip_accents(team_b)
    if "draw" in q or "end in a draw" in q: return "draw"
    if a in q and b not in q: return "a"
    if b in q and a not in q: return "b"
    return None

def analyze_match(ev: dict[str, Any]) -> dict | None:
    title = ev.get("title") or ""
    # "France vs. Mexico" → ("France","Mexico")
    title_clean = re.sub(r"\s*-\s*More Markets$", "", title)
    parts = re.split(r"\s+vs\.?\s+", title_clean, maxsplit=1)
    if len(parts) != 2: return None
    team_a, team_b = parts[0].strip(), parts[1].strip()

    # Try ISO3 mapping (international); if either side maps, treat as intl
    iso_a = iso3_for(team_a)
    iso_b = iso3_for(team_b)
    if not iso_a or not iso_b:
        return None  # club fixtures: stub-Elo dominates; prototype skips
    src_a = elo_source(iso_a)
    src_b = elo_source(iso_b)
    if "stub-1500" in (src_a, src_b):
        return None
    elo_a = national_elo(iso_a)
    elo_b = national_elo(iso_b)
    p_a, p_draw, p_b = probs_from_elos(elo_a, elo_b)

    # Market prices: extract per-side YES from each market under the event
    market_p = {"a": None, "draw": None, "b": None}
    for m in ev.get("markets") or []:
        side = classify_market(m.get("question") or "", team_a, team_b)
        if side is None: continue
        prices = parse_outcome_prices(m.get("outcomePrices"))
        if not prices: continue
        yi = yes_index(m.get("outcomes"))
        if yi is None or yi >= len(prices): continue
        v = prices[yi]
        if 0.0 <= v <= 1.0:
            market_p[side] = v
    if None in market_p.values(): return None

    edges = {s: (mp - market_p[s]) * 100 for s, mp in {"a": p_a, "draw": p_draw, "b": p_b}.items()}
    best_side = max(edges.items(), key=lambda kv: kv[1])
    return {
        "team_a": team_a, "team_b": team_b,
        "iso_a": iso_a, "iso_b": iso_b,
        "elo_a": elo_a, "elo_b": elo_b,
        "src_a": src_a, "src_b": src_b,
        "p_a": p_a, "p_draw": p_draw, "p_b": p_b,
        "market_p": market_p,
        "edges": edges,
        "best_side": best_side[0],
        "best_edge_pp": best_side[1],
        "kickoff": ev.get("endDate"),
        "verdict": verdict(best_side[1]),
    }

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def fmt_pp(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.1f}pp"

def main():
    SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    rng = random.Random(42)

    print("=" * 78)
    print(f"DESK PROTOTYPE — {SIMS:,} simulations, seed=42")
    print("Static-Elo + pairwise model, no live data, no bonuses, no bands.")
    print("=" * 78)

    # ── OUTRIGHTS ──
    print("\n[1/3] Running WC 2026 outright Monte Carlo...")
    wins: dict[str, int] = defaultdict(int)
    for _ in range(SIMS):
        wins[simulate_wc(rng)] += 1
    model_p = {t: wins[t] / SIMS for t in {x for g in WC26_GROUPS.values() for x in g}}

    print("[2/3] Fetching Polymarket WC winner market...")
    try:
        market_p = fetch_wc_winner_market()
    except Exception as e:
        print(f"  ! market fetch failed: {e}")
        market_p = {}
    market_p_total = sum(market_p.values()) if market_p else 0.0

    print(f"  market YES prices sum = {market_p_total:.3f} (overround = {(market_p_total-1)*100:+.1f}%)")
    print()
    print("OUTRIGHT WINNERS — WC 2026")
    print("-" * 78)
    print(f"{'Team':<24}{'Model':>9}{'Market':>9}{'Edge':>9}  {'Verdict':<8} {'Elo':>6} {'src':<14}")
    rows = []
    for team in sorted(model_p.keys(), key=lambda t: -model_p[t]):
        iso = iso3_for(team)
        elo = national_elo(iso or "")
        src = elo_source(iso or "")
        mp = market_p.get(team)
        # Try fuzzy name match for market lookup
        if mp is None:
            for mk_name in market_p:
                if strip_accents(mk_name) == strip_accents(team):
                    mp = market_p[mk_name]
                    break
        if mp is None:
            mp_str = "    -"
            edge_str = "    -"
            v = ""
        else:
            edge_pp = (model_p[team] - mp) * 100
            mp_str = f"{mp*100:5.1f}%"
            edge_str = fmt_pp(edge_pp)
            v = verdict(edge_pp)
        print(f"{team:<24}{model_p[team]*100:8.1f}% {mp_str:>9} {edge_str:>9}  {v:<8} {elo:>6.0f} {src:<14}")

    # ── MATCHES ──
    print()
    print("[3/3] Fetching Polymarket priced football matches...")
    try:
        events = fetch_soccer_match_events(limit=300)
    except Exception as e:
        print(f"  ! match fetch failed: {e}")
        events = []

    analyzed: list[dict] = []
    skipped_stub = 0
    skipped_other = 0
    for ev in events:
        try:
            r = analyze_match(ev)
        except Exception:
            r = None
        if r is None:
            # rough reason
            title = ev.get("title") or ""
            parts = re.split(r"\s+vs\.?\s+", title.replace("- More Markets",""), maxsplit=1)
            if len(parts) == 2:
                a = iso3_for(parts[0].strip()); b = iso3_for(parts[1].strip())
                if (not a) or (not b):
                    skipped_other += 1
                else:
                    skipped_stub += 1
            else:
                skipped_other += 1
            continue
        analyzed.append(r)

    print(f"  analyzed {len(analyzed)} matches "
          f"(skipped: {skipped_other} unmapped, {skipped_stub} stub-Elo / missing prices)")
    print()
    print("MATCHES — currently-priced football, model vs Polymarket")
    print("-" * 78)
    print(f"{'Match':<36}{'Side':<7}{'Mdl':>6}{'Mkt':>6}{'Edge':>9}  Verdict")
    analyzed.sort(key=lambda r: -r["best_edge_pp"])
    for r in analyzed[:40]:
        match = f"{r['team_a']} v {r['team_b']}"[:35]
        side = {"a": r["team_a"][:6], "b": r["team_b"][:6], "draw": "draw"}[r["best_side"]]
        mdl = {"a": r["p_a"], "draw": r["p_draw"], "b": r["p_b"]}[r["best_side"]] * 100
        mkt = r["market_p"][r["best_side"]] * 100
        edge = r["best_edge_pp"]
        print(f"{match:<36}{side:<7}{mdl:5.1f}%{mkt:5.1f}% {fmt_pp(edge):>9}  {r['verdict']}")

    print()
    print("=" * 78)
    print("End of prototype run.")
    print("Reminder: thin model, static Elo, no bands/liquidity/bonuses.")
    print("This is a sanity check, not the desk engine.")
    print("=" * 78)

if __name__ == "__main__":
    main()
