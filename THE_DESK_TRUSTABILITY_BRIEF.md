# The Desk — Trustability Brief

**Status:** strategic brief, 2026-05-09.
**Target consumer:** Claude Code (implementation), Adi (decisions).
**Owner:** Adi.
**Sequence:** drives the v1.1 release. Sits on top of PR 4.5 (sanity layer) + PR 5 (explainer) + PR 6 (scheduler). Adds new work where those don't already cover it.
**References:** `THE_DESK_SPEC.md` (architecture), `THE_DESK_PR_4_5_BRIEF.md` (sanity layer), `THE_DESK_PR_BACKTEST_BRIEF.md` (calibration harness, shipped), `RECOMMENDATION_ENGINE_DESIGN.md` (methodology), `feedback_late_binding_features.md` (memory).

---

## 1. Why this brief exists

The Desk is the flagship of Odds Primer. The WC 2022 backtest landed two findings, in plain English:

| Axis | Result | Reading |
|---|---|---|
| **Calibration** (when we say 70%, does 70% happen?) | **0.581 mean Brier** vs **0.579 closing market** — within 0.2% across 64 matches | We forecast outcomes about as accurately as Pinnacle. **This is the credibility number; it holds.** |
| **Selection** (which fixtures we flag as Picks) | **61/64 Picks (95% rate)** | We flag almost everything as a Pick because the v1 model lacks the information the market already has. **Picks are not yet trustworthy.** |

A flagship product can't ship in this state. Calibration earns the right to publish the predictions; selection earns the right to recommend acting on them. The first is real; the second is broken. This brief is the path to fixing it without weakening what already works.

### What "trustable" means here

A user — Adi, Faktor (Adi's partner), an end-reader — must be able to pick up a Pick verdict and:

1. **See why it's a Pick** — drivers attributed to specific factors, not opaque "the model says".
2. **See the model's calibration history** — how often previous Picks at the same probability landed; track-record updates live.
3. **See what we don't know** — features marked unavailable rather than zero-filled. ("Confirmed XI at T−1h" or "no data yet".)
4. **See the cited source** — every fact in the blurb has a footnote pointing to the specific article / dataset / scrape.
5. **Distinguish model probability from market probability** — verdict prose never collapses the two. ("The model rates Brazil at 65%. Pinnacle has them at 58%. The four-cent gap is the basis for the Pick.")
6. **Trust the Pick rate** — when the dashboard says 12 Picks in 100 matches, those 12 are the ones with real edges, not 95 false positives.

These are the six criteria this brief is judged against. Every section below maps back to at least one.

---

## 2. Out of scope

- **Replacing the maths.** The Elo + venue + late-binding cascade in `desk/sports/football/model.py` is fine. The work is data depth and selection discipline, not a new model.
- **A new contract.** `MatchOutput` keeps its shape — verdict.state stays `{pick, pass, avoid}`, copy stays three strings, internals stay private.
- **Real-money flows.** No staking, no Kelly, no portfolio. Read-only forever.
- **A separate inference service.** The engine stays in-process; `desk run --once` plus the cadence ladder is the production runtime.
- **Sport other than football.** Tennis / basketball stay deferred until football is trustable.

---

## 3. The work

Six phases, each independently shippable. Phases A–C are the trustability core; D–F build credibility surface area. **Don't ship D–F before A–C** — public surfacing without the underlying discipline is reputation-damaging.

### Phase A — Selection discipline (4–6 days · highest priority)

**Goal:** Pick rate inside 5–20% target on the live engine and the WC 2022 backtest.

**Work:**

1. **Liquidity filter + extreme-price guard** — already specced in `THE_DESK_PR_4_5_BRIEF.md`. Ship that PR first; it's the smallest dial-down. Extreme implied probabilities (≤ 1% or ≥ 99%) treat the venue as "no opinion" and the verdict defaults to Pass.
2. **Multi-window confirmation** — a Pick must persist across at least two windows (T−5 and T−1h) to fire. A single-window 3pp edge is noise; an edge that holds while the market sees more information is signal. Implement in `desk/verdict/decide.py` by reading the last N persisted snapshots for the same `match_id`.
3. **Confidence intervals around `model_p`** — output a `model_p_lower / model_p_upper` band (jackknife the Elo prior across ±50 of the seed value, take 5th/95th percentile). A Pick fires only when `model_p_lower − best_market_p ≥ pick_pp`. Forces the engine to be honest about what it doesn't know.
4. **Calibration-aware threshold** — once enough rolling history exists (target: 200+ resolved Picks), bin the model's historical Brier by predicted probability and require the Pick threshold to scale with the bin's calibration error. Bins where the model has been over-confident historically need a wider edge to fire.

**Acceptance:**
- Pick rate on WC 2022 backtest drops from 95% to ≤ 20%.
- Pick rate on live engine (78 priced fixtures) drops from 62% to ≤ 20%.
- Mean `edge_pp` on Picks lands in the 4–8 range, not 19.

### Phase B — Late-binding features (5–7 days · highest impact on calibration)

These are the features the closing market prices in but our v1 model doesn't see. They're the reason the model disagrees with the market on 95% of fixtures — not because the model has insight, but because it has less information.

`THE_DESK_SPEC.md` §7 already codifies the binding ladder. This phase implements it.

| Feature | Source | Bind window | Cadence |
|---|---|---|---|
| Recent form (last 10 results, weighted) | football-data.co.uk league CSVs (already free); `desk/backtest/historical/markets.py` carries the loader pattern | Always | Weekly |
| FIFA / Elo rank delta vs opponent | Wikipedia data module (live ingest replaces `data/elo_seed.py`) | Always | Weekly |
| Weather (temperature, wind, rain) | OpenWeatherMap historical + forecast | T−5 days | Daily, then hourly inside T−24h, final at T−2h |
| Injury / availability picture | Tier-1 source list (BBC Sport, ESPN FC, L'Équipe, Globo Esporte for Brazil sides, Marca for Spain, etc.) → Haiku fact extractor | T−3 days | Hourly |
| Confirmed XI | Tier-1 source list, post-XI announcement | T−1h | Once |

Each feature lands as one PR. Acceptance criteria per feature:

- Backtest mean Brier improves measurably (target: 0.579 → 0.55 once all five ship).
- Drivers attributed: when a feature moves the verdict, the explainer's title/summary references it explicitly.
- Late-binding rule enforced — `desk/features/builder.py` raises if a feature is requested outside its window.

**Phase B is the headline number's improvement vector.** Calibration is already at parity with the closing market; these features are how it surpasses it.

### Phase C — Data quality (3 days)

**Goal:** No silent stubs in production. Every input is either real, marked stale, or marked absent.

1. **Live Wikipedia Elo ingest** — replaces `data/elo_seed.py`. MediaWiki revisions API; cache by date; lookahead-prevention reused from `desk/backtest/historical/elo.py`.
2. **Live ClubElo ingest** — replaces club Elo stub. Daily CSV at `api.clubelo.com/{yyyy-mm-dd}` (probed during backtest build; intermittent network — wrap in retry + cache).
3. **WC 2026 fixture-to-stadium map** — bundle FIFA's published assignments. Without it the host bonus rarely fires (only when team_iso3 matches venue_country). With it, every WC fixture knows its stadium + altitude.
4. **Club home-ground table expansion** — currently 11 clubs in `data/club_grounds.py`. Expand to top 5 leagues + top 30 clubs per league via FBref scrape (rate-limited per spec §5: 1 req / 3s).
5. **Source-state surfacing** — `Source.state` carries `enabled / tier / last_fetch_at / last_error`. Surface in the published `MatchOutput.copy` as a footnote line: "data sources: 4 / 5 fresh; weather binding deferred to T−24h."

### Phase D — Backtest expansion (3 days)

**Goal:** ≥150 historical matches in the calibration harness. Walk-forward validation. League coverage to 2024 season finishes.

1. **Euro 2024 + Copa 2024** — already in `desk/backtest/tournaments.py` as commented-out entries. Curate the manual CSVs (51 + 32 = 83 matches). Run the harness across all three tournaments.
2. **EPL 2023/24 + La Liga 2023/24** — football-data.co.uk DOES publish these (`E0.csv`, `SP1.csv`). Wire `historical/markets.py` to read them. ~760 matches across the two leagues — roughly 6× the international set.
3. **Walk-forward validation** — train data through 2022-12-31, test on 2023; advance the cutoff month by month. Catches lookahead bugs that a single-tournament backtest can't.
4. **Calibration trend** — the dashboard adds a per-tournament Brier strip so you see whether calibration is stable or drifting.

**Why the size matters:** one tournament is anecdote, three is a sample. With 800+ matches the calibration claim becomes statistically defensible — confidence interval on mean Brier shrinks below ±0.005, narrower than the difference vs market.

### Phase E — Public track record (2 days)

**Goal:** A live page that shows every Pick The Desk has ever issued, against the actual outcome. Updates automatically.

1. **`/track-record` route** — same masthead + design system as the Ledger and the backtest dashboard. Three sections:
   - **Headline:** rolling-30-day mean Brier vs the market's mean Brier on the same matches; rolling-30-day Pick hit rate.
   - **Reliability diagram:** all Picks since launch, binned by stated probability.
   - **Pick log:** every Pick we've ever issued, immutable, dated, with the actual outcome.
2. **Immutability** — once a Pick is published, the row in the log is frozen. The `MatchOutput` JSON for that match is preserved at `data/output/football/{match_id}-{snapshot_at}.json` (snapshot suffix added at write time). PR 6's scheduler already writes per-snapshot files; this just retains them instead of overwriting.
3. **Auto-refresh** — the page is regenerated by the scheduler whenever a published match's outcome resolves. Same writer pattern as the backtest dashboard.

**The track-record page IS the credibility story.** Faktor — and any reader — doesn't have to take our word for the Brier number; the page shows every prediction we've ever made.

### Phase F — Voice + explainer trustworthiness (overlaps with PR 5; specced here for completeness)

These add to PR 5's existing scope. Implement them inside the explainer step rather than as a separate PR.

1. **Cited blurbs** — every claim in the blurb has a footnote pointing to a URL. The Haiku prompt enforces it; a regex post-check rejects blurbs without ≥1 citation per fact-claim.
2. **Probability triplet always shown** — the title/summary/blurb must reference the model's probability AND the market's, not just one. Enforced via system prompt + post-check.
3. **No false certainty** — banned phrases extend beyond the existing list to include "will win", "is set to", "destined", "lock", "no-brainer". Soft-language requirement: probabilistic verbs only ("rates", "implies", "favours").
4. **Honest miss surfacing** — when a previously-issued Pick resolves as a Miss, the next match for the same team carries a footnote: "Last Pick on this team (Brazil v Cameroon, Dec 2 2022) missed."
5. **Source attribution per driver** — when the explainer references a feature (form, weather, injury), it cites the data source by name in the blurb's footnote. "Form data via FBref; weather via OpenWeatherMap."

---

## 4. Sequencing

```
Today  ──▶ PR 4.5 (already specced — sanity layer; ship first)
       ──▶ Phase A.1 (already covered by 4.5)
       ──▶ Phase A.2  multi-window confirmation
       ──▶ Phase A.3  confidence intervals
       ──▶ PR 5 (explainer; ship in parallel — touches different files)
       ──▶ Phase B  late-binding features (5 PRs, one per feature)
       ──▶ Phase C  data quality
       ──▶ Phase D  backtest expansion
       ──▶ PR 6 (scheduler; needed by Phase E)
       ──▶ Phase E  public track record
       ──▶ Phase F  voice trustworthiness (lands inside PR 5 + iterations)
       ──▶ Phase A.4  calibration-aware threshold (needs Phase E rolling history)
```

Phases A–C are the v1.1 release; landing them lifts calibration from "matches market" to "beats market on Brier" and selection from 95% Picks to discipline. Phases D–F are v1.2; they're the public-credibility bundle.

---

## 5. Acceptance — the v1.1 release as a whole

A v1.1 release ships when, in this order:

1. **Calibration improves.** WC 2022 backtest mean Brier ≤ 0.55, beating the closing market by ≥ 0.025 across 64+ matches.
2. **Selection earns trust.** Pick rate on both the WC 2022 backtest AND the live engine sits in 5–20%; Pick hit rate roughly matches mean Pick probability (within ±10pp).
3. **No silent stubs.** Every `Source` in the registry reports `last_fetch_at` within its declared cadence; sources that fail surface as footnotes.
4. **Explainer earns trust.** Voice tests pass on 100 generated samples; every blurb cites ≥1 source per fact claim; no banned phrases.
5. **Backtest covers ≥ 150 matches.** WC 2022 + Euro 2024 + Copa 2024 + at least one club league season.

When all five hold, The Desk is trustable. Until then, internal-only.

---

## 6. Open questions for Adi (block these before A.3 ships)

- **Confidence-interval breadth.** Spec proposes ±50 Elo jackknife. Is that aggressive enough to catch the v1 model's blind spots, or do we want a tighter band?
- **Friendlies in form features.** Include / downweight / exclude? (Same question as in `THE_DESK_SPEC.md` §10.) Need answer before B.1 ships.
- **Track-record page audience.** Internal-only at v1.1; public at v1.2? Or hold public until WC 2026 group stage finishes so the launch carries real-time live results alongside?
- **Calibration-aware threshold timing.** Should A.4 wait until Phase E's rolling history exists, or do we ship a simpler version (per-bin threshold from the WC 2022 backtest) earlier?
- **Source-tier weighting.** Tier-1 sources outweigh tier-2 in the Haiku fact-extractor today. Should that be configurable per-sport (e.g. Globo Esporte tier-1 for Brazil sides, tier-3 for everyone else)?

---

## 7. What this brief does NOT promise

- That The Desk will beat the closing market on Brier in production. We're closing the gap; "beating" is a stretch goal.
- That selection discipline lands at 5%. 5–20% is the target; 8–12% is realistic.
- A schedule. The ordering above is logical, not dated. Each phase is independently shippable.

---

## 8. Why this is the flagship spec and not a sub-spec

Three other Desk specs already exist (`THE_DESK_SPEC.md`, `4_5`, `BACKTEST`). This one differs because it's not implementation-first — it's the **trust contract** between the engine and its consumers (the website Faktor is building, then end-readers). Every other spec answers "how do we build this?" This one answers "what makes it credible to ship?"

Land the work below and the dashboard's Bottom-line card flips from red to green. That's the bar.
