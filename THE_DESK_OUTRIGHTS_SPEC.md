# The Desk — Outrights Build Spec

**Status:** v0.1 build spec, 2026-05-11.
**Target consumer:** Claude Code (agentic CLI).
**Owner:** Adi.
**Scope:** WC 2026 outright winner only.
**Source market:** [Polymarket — "2026 FIFA World Cup Winner"](https://polymarket.com/event/2026-fifa-world-cup-winner-595).

---

## 1. Mission

Extend The Desk from a per-match verdict engine to also evaluate the **tournament outright** — for each of the 48 teams priced in the WC 2026 Winner market, produce a fair P(win) from a Monte Carlo simulation of the bracket and compare it to Polymarket's implied probability. Output a sister contract `outright.json` per tournament, consumed by the website the same way per-match `MatchOutput` JSONs are consumed.

WC 2026 is the launch wedge. The architecture must admit club outrights (UCL winner, EPL champion, La Liga winner) in v1.1 without a refactor — so the sport boundary stays clean, and "tournament" is a first-class concept the way "match" already is.

The model **does not** read market prices. Fair P(win) is derived purely from the existing Elo + host + home + altitude pipeline, simulated forward through the tournament's actual fixture graph.

## 2. Out of scope (do not build)

- Live in-play probability shifts (we revisit when PR 6's scheduler ships — outrights refresh on the same cadence as match verdicts).
- Real-money sizing, Kelly, "place bet" CTAs.
- A separate goal model bolted onto match verdicts. The Poisson tilt used here is **outright-internal** — match verdicts continue to use the existing `p_a/p_draw/p_b` triplet untouched.
- Group-stage subdivision Picks (e.g. "to win Group D") — only the tournament winner ships in v1.
- Top-N markets (top scorer, golden boot) — separate ingest shape, deferred.
- Non-football outrights — the abstraction admits them but v1 ships football only.
- Polymarket fees and slippage. Outright edge_pp is computed against the mid as published by gamma.

## 3. Output contract — `TournamentOutright`

A new sibling shape to `MatchOutput`, living in the same `desk/publish/contract.py` Pydantic module. The schema generation step extends `desk/contract.schema.json` so consumers validate independently.

```jsonc
{
  "tournament_id": "fb-wc26",
  "sport": "football",
  "competition": { "code": "wc26", "label": "FIFA World Cup 2026" },
  "kickoff_utc": "2026-06-11T18:00:00Z",       // first match of the tournament
  "final_utc":   "2026-07-19T19:00:00Z",       // scheduled final
  "market_url":  "https://polymarket.com/event/2026-fifa-world-cup-winner-595",
  "teams": [
    {
      "team":     "Spain",
      "team_id":  "esp",
      "verdict": {
        "state":        "pick",
        "market_venue": "polymarket",
        "price":        "+650",                 // best market price for the side
        "model_p":      0.182,
        "market_p":     0.133,
        "edge_pp":      4.9,
        "market_url":   "https://polymarket.com/event/2026-fifa-world-cup-winner-595/will-spain-win-the-2026-fifa-world-cup",
        "model_p_lower": 0.142,                 // 5th percentile from bootstrap
        "model_p_upper": 0.224                  // 95th percentile from bootstrap
      },
      "copy": {
        "title":   "Spain — the model's pick to lift it",
        "summary": "Two sentences in Odds Primer voice.",
        "blurb":   "Sixty to ninety words explaining the Pick.",
        "citations": [],
        "drivers": [
          "Highest Elo of any tournament entrant by 22 points",
          "Strong path: Round-of-32 draw avoids top-eight seeds",
          "No host-nation discount; venues neutral for La Roja"
        ]
      }
    },
    /* one entry per priced team — 48 in total for WC 2026 */
  ],
  "summary": {
    "picks":  ["Spain", "Brazil"],
    "passes": 41,
    "avoids": ["Iran", "South Africa", "Algeria", "Canada", "Mexico"]
  },
  "updated_at": "2026-05-11T08:00:00Z"
}
```

### Field rules

- **`tournament_id`** is canonical: `fb-{competition_code}` (no kickoff date — a tournament is identified by competition).
- **`teams`** carries every team Polymarket prices, including ones we'd call Pass — so the website can render the full ladder. Order is descending by `verdict.model_p`.
- **`teams[].verdict`** uses the **same `VerdictState` enum** as `MatchOutput.verdict` (Pick / Pass / Avoid) — thresholds in §6 — but `side` and `market_outcomes` are absent (the team itself is the side). `model_p_lower` / `model_p_upper` carry the bootstrap band, mirroring `MatchOutput.verdict.model_p` per the optimization spec.
- **`teams[].copy.drivers`** is the structured "Why this call" list, capped at 4 entries per the existing `Copy` model. Distinct from match-level drivers (no `Driver(name, value, side)` here — outright drivers are plain prose).
- **`summary`** is a denormalized convenience block so the front-of-house can render a hero row without re-scanning `teams`.
- **`updated_at`** advances on each scheduler tick. Outrights ETag (SHA-256 of canonical JSON) tracks the file the same way per-match ETags do today.

### Validation invariants

- `sum(verdict.model_p) over teams` ∈ [0.98, 1.02]. We tolerate ±2pp from MC noise + the "no team wins" tail (extra-time exhaustion, abandoned tournament — modelled as 0 mass). A model that returns more than 2pp off triggers a publish refusal with a clear error.
- `sum(verdict.market_p) over teams` ∈ [0.95, 1.10]. Polymarket overrounds — typical sum is ~1.04. We refuse a publish below 0.95 (something is missing).
- Every team's `model_p_lower ≤ model_p ≤ model_p_upper`.
- Exactly one of `state` is set per team. Pick requires `price`, `market_venue`, `edge_pp`, `model_p`, `market_p`, `market_url` (same invariants as match Pick).

## 4. Ingest — Polymarket outrights

New source class `PolymarketWorldCupWinnerSource` in `desk/ingest/polymarket_outrights.py` (file is sport-agnostic by convention but the source ID encodes WC 2026 because the market does). Registers itself the same way the existing soccer-events source does.

### Endpoint shape

Polymarket gamma has two relevant endpoints:

- `GET /events/{slug-or-id}` — one event with embedded `markets[]`. For WC 2026 Winner, each child market is "Will {team} win the 2026 FIFA World Cup?" with a `lastTradePrice` and `outcomes` array of `["Yes", "No"]`. The slug is `2026-fifa-world-cup-winner-595` (URL fragment confirmed).
- `GET /markets?event_id=...` — alternative; less ergonomic.

We pull the event by slug, iterate `markets[]`, extract `(team_name, p_yes)` pairs. Team names are human-readable ("Argentina", "Saudi Arabia") so we run them through `desk/sports/football/teams.py:normalize_team(name, is_national=True)` to land on the canonical ISO3 (`arg`, `sau`).

### Failure modes

- A market that fails to map to a team (e.g. "Field" / "Any other team") is logged + skipped. We never publish a `team_id="field"` row in v1.
- A market with `archived=true` or `closed=true` is excluded (teams already eliminated). The summary's `avoids` count is the call-state count, not the eliminated count.
- Per the spec's failure-mode rule, an empty gamma response logs a warning and the publisher **leaves the previous `outright.json` in place**. We never publish a degraded outrights file.

### Match-graph ingest (separate from price ingest)

The MC sim needs the bracket structure, not just prices. The schedule comes from `desk/sports/football/data/wc26_venues.py` (already partial — needs the fixture list, not just venues). We extend that module with the canonical WC 2026 group draw + bracket, sourced from FIFA's official schedule once the December 2025 draw is final. Until then, the source-of-truth file carries a `draw_complete: bool` flag — if false, the sim uses Elo-weighted random groups (and the explainer says so).

## 5. Model — Monte Carlo from Elo

Lives at [desk/sports/football/outrights.py](desk/sports/football/outrights.py) (new file). Sport-specific by design — basketball outrights would get their own `desk/sports/basketball/outrights.py`. The sport-agnostic orchestration sits in `desk/outrights/` (new directory) and calls `Sport.simulate_tournament(...)` through the protocol.

### Per-match probability inside the sim

The existing `desk/sports/football/model.py:compute()` returns `(p_a, p_draw, p_b)`. The MC sim uses these directly for group-stage outcomes (W / D / L). No new maths.

For **tiebreakers** within a group (points → GD → GF → head-to-head → fair play → lots), we need goals, not just outcomes. We derive expected goals from the same Elo diff:

```
λ_total = 2.6                            # WC 2026 baseline goals per match (configurable)
expected_a = 1 / (1 + 10**(-elo_diff/400))
λ_a = λ_total * expected_a
λ_b = λ_total * (1 - expected_a)
goals_a ~ Poisson(λ_a)
goals_b ~ Poisson(λ_b)
```

This Poisson layer is **outright-internal**. It does not feed back into match verdicts. The `compute()` triplet remains the authoritative match-level probability — the MC just needs a scoreline to break ties.

### Knockout matches

There's no draw in knockout. In the sim we draw `(p_a, p_draw, p_b)` from the model and:

```
if uniform() < p_a / (p_a + p_b):
    winner = team_a
else:
    winner = team_b
```

i.e. we redistribute the draw mass proportionally to the two sides' win shares — equivalent to assuming penalty shootouts split by relative strength (a simplification; pure 50/50 is the alternative). Decision: **proportional split**, because a stronger side outperforms in extra time even if penalties are coin flips, and the lit on penalties is mixed enough that we don't claim 50/50 is more honest than proportional.

### Bracket structure (WC 2026)

- 48 teams, 12 groups of 4.
- Round of 32 = top 2 from each group (24) + 8 best third-place teams (ranked by points → GD → GF across all 12 groups).
- Bracket from R32 onward is **fixed** by FIFA — we encode it in the schedule file.
- Final at MetLife Stadium, NJ, USA on 2026-07-19.

### Sim parameters

| Constant | Default | Why |
|---|---|---|
| `OUTRIGHTS_BASELINE_SIMS` | 50,000 | Stable P(win) for tail teams (P < 1%). |
| `OUTRIGHTS_BOOTSTRAP_SAMPLES` | 20 | Each samples a perturbed Elo prior; 20 × 5,000 = 100K bracket sims for the band. |
| `OUTRIGHTS_BOOTSTRAP_SIMS` | 5,000 | Per bootstrap sample. |
| `OUTRIGHTS_GOALS_PER_MATCH` | 2.6 | WC 2022 was 2.69; we round to 2.6. Override via `.env`. |
| `OUTRIGHTS_RNG_SEED` | 42 | Deterministic for diffable backtests. |

Baseline runs once with the unperturbed Elo prior. Bootstrap reuses the same Elo perturbation magnitudes as the match-model band (`ELO_PERTURBATION = 50`, `HOST_BONUS_PERTURBATION = 15`, etc. — see `model.py`). The 5th / 95th percentile across the 20 × 5,000 bracket sims gives `model_p_lower` / `model_p_upper`.

### Performance

A single bracket sim is 12 × 6 = 72 group matches + ~31 knockout matches = ~103 match draws. Each match draw is two Poisson + one categorical → maybe 50µs in pure Python. 150K sims × 100 matches × 50µs ≈ 12 minutes. Acceptable for a daily refresh — outrights aren't on the per-minute cadence match verdicts are. If profiling shows the sim is hot, vectorise over numpy: 150K sims × ~100 matches in <30 seconds with batched Poisson draws.

PR 1's acceptance bar is **correctness over speed**. Profile and vectorise in a follow-up PR if the daily refresh slips past 5 minutes.

## 6. Verdict thresholds

Reuse the match verdict thresholds with one adjustment for the longer tail:

| State | Match rule | Outright rule |
|---|---|---|
| Pick | `model_p − market_p ≥ 3.0pp` | `model_p − market_p ≥ 3.0pp` **and** `model_p_lower − market_p ≥ 0pp` |
| Pass | `\|model_p − market_p\| < 1.0pp` | `\|model_p − market_p\| < 1.0pp` |
| Avoid | `model_p − market_p ≤ −2.0pp` | `model_p − market_p ≤ −2.0pp` |
| Default | else → Pass | else → Pass |

The lower-bound gate on Pick is the same honesty rule the match engine uses post-Phase A.2: even if the central estimate clears 3pp, we don't Pick when the confidence band crosses the market — too noisy to ride.

Override via `.env`: `DESK_OUTRIGHTS_PICK_PP`, `DESK_OUTRIGHTS_PASS_PP`, `DESK_OUTRIGHTS_AVOID_PP`. Default to the match values unless explicitly set.

### Why no separate threshold tier

A team priced at 5% with model 8% has a 3pp edge but a 60% relative gap — by ratio, a much bigger call than a 50% match with a 53% model. We considered relative-edge thresholds (e.g. `model_p / market_p ≥ 1.5`) but **rejected**: outright tail teams are noisy precisely *because* the sim is rare-event sensitive, and a relative threshold rewards exactly the noise we don't trust. The 3pp + lower-bound rule keeps the engine conservative on long shots, which matches editorial taste.

## 7. Explainer

Reuses the existing `desk/explainer/stub.py` + voice rules. Outright explainer lives at `desk/sports/football/explainer_outrights.py` and emits the same `Copy` shape (title / summary / blurb / drivers).

### Driver attribution

Each outright Pick blurb cites 2–4 drivers, ranked by influence on the model's P(win):

1. **Elo rank delta** — where this team sits in the prior vs the market's implied rank.
2. **Bracket path** — average opponent strength on the most-probable knockout path.
3. **Host / altitude advantage** — does this team benefit from venue effects? (USA, Canada, Mexico get host bonus; Andean / high-altitude sides get altitude bonus in Mexico City / Guadalajara.)
4. **Group strength** — easy vs. hard group of 4.

These are derived from the MC sim's per-team aggregates (counted draw outcomes, mean opponent Elo by round, advance rate from group), not hand-written per team. The driver text is templated; PR 5's Haiku replacement rewrites them in voice.

### Voice rule

Outright blurbs follow the same banned-phrase suite (no "bet/back/lock", no emoji, sentence case, attribution required for sourced facts). Two outright-specific rules:

- **No leaderboards.** Never say "the favourites" or "the dark horse" — those are tipster framings. Say "the model rates X at Y%" instead.
- **No false certainty on long shots.** If `model_p < 5%`, the blurb must contain the words "the model rates" or "the model gives" — never a declarative "X will…".

Both rules are post-generation regex assertions in `tests/test_outrights_voice.py`.

## 8. Publish

New publisher path: `data/output/football/outrights/wc26.json`. Index entry added to `data/output/football/index.json` under a new `outrights:` key — sibling to `matches:` — so existing consumers continue to read `matches[]` unchanged.

```jsonc
{
  "sport": "football",
  "matches": [...],                                  // existing per-match index
  "outrights": [
    { "tournament_id": "fb-wc26",
      "kickoff_utc":  "2026-06-11T18:00:00Z",
      "updated_at":   "2026-05-11T08:00:00Z" }
  ],
  "updated_at": "2026-05-11T08:00:00Z"
}
```

Adding `outrights` to `OutputIndex` is a contract change → ADR required.

ETag on `outrights/wc26.json` is SHA-256 of canonical JSON, same as match files.

## 9. Build order — three PRs

Each PR ships green tests + a README update + a regenerated dashboard (where applicable). Don't open the next until the previous is merged.

### PR O1 — outright contract + ingest + stub model (1 day)

- Extend `desk/publish/contract.py` with `TournamentOutright`, `OutrightTeam`, `OutrightSummary` models.
- Regenerate `desk/contract.schema.json` (the in-sync test enforces this).
- Add `PolymarketWorldCupWinnerSource` in `desk/ingest/polymarket_outrights.py`.
- Add `desk/sports/football/outrights.py` with `compute_outright(market_snapshot, draw)` returning a `TournamentOutright` built from a **stub model**: P(win) = `softmax(elo / 100)` normalized across the 48 priced teams. No MC yet.
- `desk run --once --outrights` writes `data/output/football/outrights/wc26.json`. Verdict will be Pass-heavy because the stub model is uninformative, but the contract round-trips.

**Acceptance.** `pytest tests/test_outrights_contract.py` green. Curl `/output/football/outrights/wc26.json` returns a schema-valid file with 48 teams. ADR-0002 for the `outrights[]` index field shipped.

### PR O2 — Monte Carlo simulator (1.5 days)

- Encode WC 2026 fixture graph in `desk/sports/football/data/wc26_schedule.py`. Until the December 2025 draw is final, ship with `draw_complete = False` and Elo-weighted random groups inside the sim.
- Implement `simulate_tournament(elo_priors, schedule, n_sims, seed) -> dict[team_id, float]` in `desk/sports/football/outrights.py`. Pure Python first — vectorise only if profiling demands.
- Wire it into PR O1's `compute_outright()` — replace the stub with MC P(win).
- Add Poisson goal model + tiebreaker logic. Frozen-input test: a 1500-vs-1500 group of 4 should produce ~25/25/25/25% advance rates ±1pp at N=50K sims.
- Add bootstrap band over 20 perturbed Elo samples → `model_p_lower` / `model_p_upper`.

**Acceptance.** `pytest tests/test_outrights_sim.py` green — covers a frozen WC 2022 retrospective (run the sim with 2022 Elo priors and 2022 schedule; Argentina's modeled P(win) should land in [0.10, 0.25] at N=50K — the closing market was at 0.11). Sim deterministic at seed=42. `desk run --once --outrights` writes a meaningful `outright.json` with at least one Pick at `edge_pp ≥ 3.0`.

### PR O3 — explainer + dashboard + publisher integration (1 day)

- Add `desk/sports/football/explainer_outrights.py` with templated `Copy` generation.
- Voice tests in `tests/test_outrights_voice.py` — banned-phrase suite + the two outright-specific rules from §7.
- Extend the backtest dashboard (`desk/backtest/writers/`) with an outright section: ladder of teams, model P vs market P, Picks highlighted.
- Wire outrights into the FastAPI route table so `/desk` (and the website) can fetch the outright file the same way they fetch match files.

**Acceptance.** Backtest dashboard renders the outright ladder. Three picks (or however many fire) read in Odds Primer voice and pass the banned-phrase suite. Live `/desk` page links to the outright ladder.

## 10. Scheduler cadence

Outrights refresh **daily**, not per-minute. Reasons:

- Polymarket outright prices move on news cycles, not by the minute.
- The MC sim is the expensive step in the engine. Running it on the verdict job's 60s cadence would dominate compute.
- Confidence is built by *not* re-publishing on every gamma jitter. A daily ETag advance is a stronger signal than a minute-by-minute one.

PR 6 (the scheduler PR) will register an `outrights` job at `0 8 * * *` UTC (08:00 daily) alongside the existing match-verdict and explainer jobs. T−7d through T+0 of the tournament itself, we'd accelerate to hourly — wire as a config switch, not hardcoded.

## 11. Backtest

The existing backtest harness (`desk backtest --tournament wc-2022`) replays match-level verdicts. We extend it to **also** replay outrights:

```bash
cd desk && PYTHONPATH=. python3 -m desk backtest --tournament wc-2022 --outrights
```

This runs the sim with WC 2022's frozen Elo prior + WC 2022's actual schedule, then compares the model's pre-tournament P(win) per team against:

1. The 2022 closing market (Polymarket / Betfair historical) — calibration check.
2. The actual winner (Argentina) — single-sample, but useful as a sanity headline.

Acceptance bar from the backtest:

- Argentina's modeled P(win) ∈ [0.10, 0.25]. (Closing market was ~0.11; we want to be in the same neighbourhood, not 0.50.)
- Brazil + France together ≤ 0.45 of mass. (They were the market favourites; our model shouldn't concentrate more than the market.)
- Brier vs closing market ≤ market's self-Brier + 0.02. (We tolerate being slightly noisier than the market but not wildly miscalibrated.)

These bars are advisory in PR O2; they become required gates in PR O3.

## 12. Open questions for Adi

- **WC 2026 schedule source.** FIFA's official fixture list isn't fully fixed until the December 2025 draw. Until then: ship with `draw_complete = False` and Elo-weighted random groups, or freeze a placeholder draw and re-run when real one lands? Default: random groups + a banner on the dashboard.
- **Confidence band on the website.** Per-team `model_p_lower`/`upper` is in the contract. Render it as a range ("12–22%") or just the central estimate ("17%")? Match Picks render the central estimate only — keep consistent? Default: central estimate only; lower bound used internally to gate Picks.
- **Polymarket-only or also Kalshi outrights?** Kalshi has a WC winner market too. v1 = Polymarket only; v1.1 adds Kalshi. Confirm.
- **Penalty-shootout split.** §5 picks proportional; the alternative is 50/50. Confirm proportional before PR O2 lands the knockout logic.
- **Brier acceptance bar.** §11 sets ≤ market's self-Brier + 0.02. Tighter? Looser? This is the line between "model is good enough" and "model needs work".

## 13. Forward-compat — what v1.1 needs

These are pre-conditions baked into PR O1–O3 so v1.1 (club outrights) is additive:

- `TournamentOutright` is sport-agnostic in `desk/publish/contract.py`. UCL would publish to `data/output/football/outrights/ucl-2026-27.json` with `tournament_id = "fb-ucl-2026-27"`.
- The MC sim is parameterised by a `Schedule` object — group structure, knockout bracket, host metadata. Club tournaments swap in a different `Schedule`; the sim code is unchanged.
- The Polymarket source class is parameterised by event slug. WC 2026, UCL 2026/27, EPL 2026/27 each have their own `PolymarketOutrightSource(slug=...)` instance registered.
- The explainer template is parameterised by competition (clubs say "Premier League title" not "World Cup", etc.) — driver text stays templated.

## 14. References

- `THE_DESK_SPEC.md` — six-PR build plan; this spec is additive to the existing pipeline, not a rewrite.
- `THE_DESK_OPTIMIZATION_SPEC.md` — Phase A bootstrap CI; the outright band reuses the same perturbation magnitudes.
- `desk/sports/football/model.py` — match-level Elo model. Outrights call into this for per-match probabilities inside the sim.
- `desk/publish/contract.py` — Pydantic source of truth. Extended (not replaced) by PR O1.
- `Odds Primer Design System/` — voice + visual rules for the outright dashboard section in PR O3.
