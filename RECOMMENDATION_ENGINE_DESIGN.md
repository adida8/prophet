# The Desk — Engine Design v0.2

**Status:** updated 2026-05-08. Supersedes v0.1.
**Internal name:** The Desk. Use this in conversation; never surface in user-facing copy.
**Owner:** Adi + Faktor.
**Surface:** retail B2C inside Odds Primer, World Cup beta (~2026-05-09).

## What it is

For each priced match, The Desk ingests sports-domain data, builds a fundamentals-only probability model, compares that probability to live Kalshi and Polymarket prices, and publishes a per-match JSON containing a **verdict** (Pick / Pass / Avoid) and the **editorial copy** that justifies it. The verdict is the call; the copy is the teaching.

## What it is not

Not a tipster product. Not a sportsbook-arbitrage tool. Not a Kalshi/Polymarket devig model — the model never reads market prices. No stake sizing, no Kelly, no "bet now" CTA. The verdict step compares model to market; that's where the editorial decision lives.

## Architecture — 6 steps, replaceable independently

**1. Ingest.** Scheduled fetchers per source, normalised to a common per-match schema. Cadence depends on whether the input is stable or late-binding. Stable inputs (Elo, FIFA rank, recent form, structural class) refresh weekly. Late-binding inputs (weather, injuries, confirmed XI) only enter the model inside the final ~5-day window before kickoff. The fixture list itself comes from Kalshi and Polymarket (the games we care about are the ones priced as markets); FIFA's official site is the authoritative metadata layer (venue, kickoff, group). News and expert-column sources are tiered and processed by a Haiku fact-extractor that emits structured facts (team, fact_type, direction, magnitude, citation URL) — never opinions.

**2. Feature store.** One row per match, columns are model inputs. Versioned so we can replay a fixture with the features we had at kickoff (critical for evaluation).

**3. Model.** Fundamentals-only probability model. Outputs `p_a`, `p_draw`, `p_b` (the three sum to 1.0) plus expected goals and a ranked driver list. v1 is Elo prior + host-country adjustment (+75 Elo when one of USA / Canada / Mexico plays at one of their own venues — venue-dependent, not team-dependent) + altitude bonus. Dixon-Coles deferred to v2 once tournament data arrives. Deliberately simple — engineering work is in the data, not the maths. **The model never ingests market prices.**

**4. Verdict.** Compares model probability to live Kalshi + Polymarket prices and produces one of three states: **Pick** (we see an edge — names side, market venue, price, and edge in pp), **Pass** (model and market agree within ~1pp — no edge today), **Avoid** (both venues priced inside our number — negative signal, no venue link). This is the cheap hot path — re-runs on every market poll (≈60s). Pass and Avoid look different in the UI deliberately.

**5. Explainer.** Three Haiku prompts, given the feature vector + model output + verdict, produce three editorial strings: `title`, `summary`, `blurb`. Template-constrained — Odds Primer voice, sentence case, no emoji, no traffic-light colour, no gambling-promo language. Re-runs only when the verdict state changes (Pass → Pick, Pick → Avoid, etc.) — keeps Haiku costs bounded.

**6. Output contract.** Per-match JSON written to a CDN-fronted bucket. Faktor's site is the consumer.

## Output contract — what Faktor consumes

Faktor consumes only what's needed to render the verdict block. Model internals (probabilities, xG, drivers, confidence band, raw market data) stay inside The Desk. They inform the verdict but never leave the building.

```json
{
  "match_id": "wc26-d-fra-mex-20260612",
  "kickoff_utc": "2026-06-12T19:00:00Z",
  "group": "D",
  "team_a": "France",
  "team_b": "Mexico",
  "venue": {
    "city": "Guadalajara",
    "stadium": "Estadio Akron",
    "country": "MX"
  },

  "verdict": {
    "state": "pick",
    "side": "France",
    "market_venue": "polymarket",
    "price": "-180",
    "edge_pp": 4.2
  },

  "copy": {
    "title": "France v Mexico · class shows",
    "summary": "Two short sentences in Odds Primer voice.",
    "blurb": "Sixty to ninety words explaining the verdict.",
    "citations": ["https://lequipe.fr/...", "https://globoesporte.com/..."]
  },

  "updated_at": "2026-06-12T17:00:00Z"
}
```

### Field semantics

- **`team_a` / `team_b`** — FIFA convention (team listed first / second). No home/away semantics; the World Cup is played at neutral or host-country venues. Host advantage is a model-internal adjustment based on `venue.country`, not a contract field.
- **`verdict.state`** — `"pick"` | `"pass"` | `"avoid"`. Drives the entire UI rendering.
- **`verdict.side`** — actual team name (e.g. `"France"`) or `"draw"` or `null`. Only meaningful on Pick. Faktor renders directly without lookup.
- **`verdict.market_venue`** — `"kalshi"` | `"polymarket"` | `null`. Only set on Pick. The Desk picks whichever venue offers the better price for the called side. Drives the "Open on [venue] ↗" CTA.
- **`verdict.price`** — string in American odds for now (e.g. `"-180"`). Lockable convention.
- **`verdict.edge_pp`** — gap in percentage points between model probability and market implied probability. Drives the Pick/Pass threshold logic inside The Desk.
- **`copy.*`** — three rendered strings + a citations array. Use verbatim; do not interpolate. Voice rules from the design system are baked into the prompts.
- **`updated_at`** — ISO timestamp of last regeneration. Drives Faktor's stale-detection.

## Boundary — Desk vs. Faktor

| Inside The Desk (never published) | Output contract (Faktor consumes) |
|---|---|
| `p_a`, `p_draw`, `p_b` | `verdict.state` |
| `xg_a`, `xg_b` | `verdict.side` |
| `drivers[]` | `verdict.market_venue` |
| `confidence` band | `verdict.price` |
| Raw Kalshi / Polymarket prices | `verdict.edge_pp` |
| Elo, host bonus, altitude bonus | `copy.title` / `summary` / `blurb` |
| Extracted news facts + sources | `copy.citations` |
| Threshold logic, model coefficients | match identity + venue + `updated_at` |

Faktor never sees the left column. If The Desk swaps Elo for a Bayesian league-strength model, or replaces Haiku with a different LLM, or adds new data sources — the contract on the right doesn't change, so Faktor's code doesn't change.

## Refresh cadence — three speeds

- **Model**: weekly outside the window; daily inside T−5; hourly inside T−3; final at T−1h on confirmed XI.
- **Verdict**: every market poll (≈60s). Markets move all the time even when the model doesn't — a Pass at T−3d can become a Pick at T−1h purely on market drift.
- **Explainer**: only when `verdict.state` transitions. Same Pick across a market price drift keeps `copy` stable; only `verdict.price` and `edge_pp` change.

Faktor doesn't need to know which speed updated. He polls `index.json` every 60s, refetches whatever's changed via ETag.

## Data sources (v1 shortlist)

| Source | Use | Binding | Access | Cost |
|---|---|---|---|---|
| Kalshi + Polymarket APIs | Fixture list + market prices for the verdict step | Continuous | REST | Free |
| FIFA official site | Match metadata (venue, kickoff, group) | Stable | Scrape (JS-rendered) | Free |
| World Football Elo (Wikipedia data module) | Strength prior | Stable | Scrape | Free |
| StatsBomb Open Data | Historical event data + xG (training set) | Stable | GitHub repo | Free (CC-BY-NC) |
| FBref | Player-level form, advanced stats | Stable | Scrape (≤1 req / 3s) | Free |
| OpenWeatherMap | Match-day venue weather | **T−5 onward, daily** | REST | Free 1k/day |
| Tier-1 expert columns (Romano, L'Équipe, The Athletic, Globo) | Reporter-confirmed facts | **T−3 onward, hourly** | RSS / scrape | Free |
| Tier-2 federations + global news | Corroborating facts | **T−3 onward, hourly** | RSS / scrape | Free |
| Tier-3 local press (Marca, AS, Bild, etc.) | Lower-confidence signals | **T−3 onward, hourly** | Scrape | Free |

Market prices feed only the verdict step (4) — never the model (3). Tiered news sources are processed by a Haiku fact extractor that emits structured `{team, fact_type, direction, magnitude, citation_url, source_tier}` records. A fact promotes to model feature only when it's confirmed by ≥1 Tier-1 source OR ≥2 Tier-2 sources; otherwise it stays at the blurb-context layer.

## Model — v1 plan

International football is data-poor: 7 games per team max, lots of friendlies of dubious signal, rosters shift cycle to cycle. v1 is honest about uncertainty rather than overfit.

The baseline is Elo (Wikipedia data module), with adjustments for venue host country (+75 when one of USA/Canada/Mexico plays at one of their own stadiums) and altitude. Dixon-Coles bivariate Poisson is deferred to v2 once tournament data arrives. Output is `p_a`, `p_draw`, `p_b` plus expected goals.

We track Brier score and log-loss against actuals across the tournament. If the model is poorly calibrated after the group stage we retreat to a wider posterior — we'd rather show "this is close to a coin flip" than a confident wrong number.

## Blurb design

Voice rules from the design system are non-negotiable. The blurb opens with the matchup framing, names two or three concrete drivers, attributes any sourced facts to the publication, and closes with where the verdict lands and why a reader might disagree. It never says "bet" or "back" or "lock." Example skeleton (Pick state):

> France meet Mexico in Guadalajara on Friday. The class gap is the story — France's qualifying xG is double Mexico's, and Modrić-style midfield experience isn't on the team sheet. Globo Esporte reported on Tuesday that Mexico's first-choice keeper is doubtful. The Desk lands on a 4pp gap to Polymarket, which feels like the market underweighting the keeper situation.

That last clause is the teaching move — we're showing the reader *how to think*, not telling them what to do.

## Calibration & evaluation

Two metrics, both visible to us internally throughout the tournament: Brier score on 1X2, and reliability diagram bins. If our 70% picks land at 50%, we're miscalibrated and we widen. We do not ship a leaderboard or hit-rate to users in v1 — that pulls the product toward tipster framing, which we said no to.

## Open questions (carried from v0.1)

- **Sample size.** Is 7-games-per-team enough to justify a proprietary model, or should v1 lean harder on Elo + xG and let the explainer do the heavy lifting? My instinct is the latter.
- **Friendlies.** Include them in form features, downweight them, or exclude? Each WC cycle has a different answer.
- **Late-news refresh.** What's the cutoff for re-running the model? Confirmed XI lands ~1h before kickoff and that's a real signal.
- **Disclaimer surface.** Where does the "this is educational, not advice" disclaimer live — per match card, footer, both?
- **Scope creep risk.** Beta is days out. v1 may need to be Elo + manual injury flags + LLM blurb, with the Dixon-Coles model arriving in v2 once we have live tournament data.

## Suggested next step

If this shape is right, the fastest path is: pick three WC matches from the group stage, hand-build the feature vector, run the explainer prompt against it, and see whether the blurbs read as Odds Primer — *before* writing any ingest code. Voice failure is the biggest risk; data plumbing is the boring part.

## Changelog

- **v0.2 (2026-05-08)** — Renamed engine "The Desk." Added explicit Verdict step (now 6 layers, not 5). Slimmed output contract to verdict + copy only — model internals stay inside The Desk. Replaced `home`/`away` with `team_a`/`team_b` (no home/away in tournament play). Renamed `verdict.venue` → `verdict.market_venue` to avoid collision with physical match venue. Expanded data sources to include tiered news/expert-column ingestion via Haiku fact extractor.
- **v0.1 (2026-05-03)** — Initial 5-layer architecture, Elo + altitude model, Haiku blurb explainer.
