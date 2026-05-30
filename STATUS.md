# Overnight status — non-US sportsbook integration + cross-venue price comparison

**As of 2026-05-30 23:00 local.** All eight commits pushed to local
`staging`. Not pushed to remote yet; not promoted to
`init/project-setup` (production). The cross-venue feature flag is
**OFF by default** — flag-flipped behaviour is fully implemented but
not yet live; pre-pivot payloads are byte-identical to today.

WC-2022 backtest re-run **after each commit** + once more at the end
of the build — Brier **0.5806** (model) / **0.5794** (market),
**30 pick / 34 pass / 0 avoid** — unchanged from the baseline
documented in CLAUDE.md. Flag OFF ⇒ byte-identical, as the spec
required.

## What shipped tonight (8 commits, on `staging`)

| # | Commit | Tests added | What changed |
|---|---|---|---|
| 1 | `desk/pricing` module | +28 | Sport-agnostic. `cost.py` (true price per venue type: sportsbook `1/d`, exchange `1/(1+(b-1)(1-c))`, prediction market `ask+fee+spread`), `devig.py` (multiplicative, Shin/power left as `NotImplementedError` seams), `consensus.py` (sharp-weighted blend; Pinnacle weight 3, William Hill 1). Pure functions, no I/O. |
| 2 | `desk/data/oddsapi` adapter | +21 | The Odds API client + sqlite cache + venue table + `/v4/sports` quota probe + event parser. Locked launch venue set: `pinnacle`, `betfair_ex_uk/_eu`, `williamhill`, `skybet`. Drops Unibet (out-of-set) and sub-evens prices silently. `ODDS_API_KEY` env wired through `desk/config.py`; `desk verify-data-sources` now probes the odds-api alongside api-football + openweathermap. |
| 3 | `desk/sports/football/oddsapi_glue.py` | +7 | Odds-API event → canonical `FixtureRef`. Launch surface: EPL (`soccer_epl`); next league = two table edits. Drops unknown teams + unmapped sport_keys instead of misclassifying. |
| 4 | `VenuePrice` + `MarketSnapshot.best_for_true_price` | +14 | `VenuePrice` gains optional `venue_type` / `region` / `decimal_odds` / `true_price` / `fair_p` / `overround`. New `best_for_true_price(side)` ranks by `e` when every candidate has one; falls back to legacy `best_for(side)` (rank by `implied_p`) when any row is missing it — refuses to silently mix apples + oranges. Includes the scope-doc Argentina worked-example flip (William Hill cheapest despite most bearish fair_p). |
| 5 | `decide()` true-price edge + flag | +4 | `cross_venue_edge` kwarg (defaults to `DESK_CROSS_VENUE_EDGE` env, default 0). When ON + every row has true_price, edge = `model_p − true_price`. Phase A.3 lower-bound gate honours the same cost surface. **WC-2022 backtest verified byte-identical with flag OFF.** New env vars: `DESK_CROSS_VENUE_EDGE`, `DESK_ODDS_FETCH`, `DESK_DEVIG_METHOD`, `DESK_REGION`. |
| 6 | Contract ADR 0004 + new top-level fields | +10 | `MatchOutput.market_prices` (per-side, per-venue: raw quote + naive implied + `true_price` + `fair_p` + `overround` + `is_best`), `consensus_fair` (sharp-weighted blend), `region` (`us` / `non-us`). `MarketVenue` enum extended additively with the launch non-US set. Publisher (`desk/publish/market_prices.py`) builds the rows from the snapshot, flagging at-most-one `is_best` per side. Sport adapter returns a 7-tuple; runner tolerates 2/3/4/5/7. Schema regenerated, in-sync test passes. CHANGELOG v1.3.0 entry. |
| 7 | Explainer venue mention | +3 | One extra driver line on a Pick when the cheapest-true-price venue differs from the verdict's headline venue: "Cheapest way in on France is William Hill at an effective 60%." Voice rules still gate the field. Flag-gated; with `DESK_CROSS_VENUE_EDGE=0` the line never appears. |
| 8 | Refresh-loop wiring + CLAUDE.md env table | 0 (CLI only) | `desk/data/oddsapi/refresh.py` orchestrator + `desk fetch-odds` CLI. Refresh loop runs the fetch each scheduled tick when `DESK_ODDS_FETCH=1` + `ODDS_API_KEY` are set. Independent from `DESK_CROSS_VENUE_EDGE` — the operator can prime the cache without flipping the verdict surface. New env vars documented in CLAUDE.md. |

**Suite total:** 1142 green (was 1055 at session start; +87 from this
work).

## Verdict-threshold re-tune on WC-2022 — flag OFF

The brief asked for before/after numbers on the backtest. With
`DESK_CROSS_VENUE_EDGE=0`, **the engine is byte-identical to the
baseline**, so the re-tune is a no-op:

| Metric | Before | After (flag OFF) |
|---|---|---|
| Brier (model) | 0.5806 | 0.5806 |
| Brier (closing market) | 0.5794 | 0.5794 |
| Picks | 30 | 30 |
| Pass | 34 | 34 |
| Avoid | 0 | 0 |

A real re-tune of `DESK_PICK_PP` / `DESK_PASS_PP` / `DESK_AVOID_PP`
for the cross-venue cost surface needs the flag ON **and** a
multi-venue backtest sample — the WC-2022 historical CSV only has
single-venue closing odds, so flipping the flag in backtest would
have no effect (no row carries a `true_price` distinct from
`implied_p`). The lever to actually use:

1. Run live `desk fetch-odds` for a week with `DESK_ODDS_FETCH=1`
   while keeping `DESK_CROSS_VENUE_EDGE=0`. Cache fills + we see
   what UK/EU coverage actually looks like.
2. Pick a week with stable Odds-API coverage; run a shadow
   prediction pass with the flag ON in dev. Compare `edge_pp`
   distribution before/after.
3. Re-tune Pick / Pass / Avoid thresholds against the shadow
   distribution **before** flipping the flag in production.

That tuning sits behind the live fetch — see "What's left" below.

## What's left (blockers + follow-ups)

### Blocker — needs an `ODDS_API_KEY` before the live fetch runs

No live API key was set in `.env` during the build; everything was
tested against a fixture EPL event JSON + `httpx.MockTransport` (per
the brief: "NO LIVE API KEY? Don't block."). Until the key lands:

- `desk verify-data-sources` reports `odds-api · SKIP — ODDS_API_KEY
  not set` (soft-skip; doesn't break existing operators).
- `desk fetch-odds` exits with code 2 and the message
  "ODDS_API_KEY not set in .env".
- `desk_refresh_loop.py` skips the step quietly (gated on both
  `DESK_ODDS_FETCH=1` and a non-empty `ODDS_API_KEY`).

**Operator action:** add `ODDS_API_KEY=...` to staging Railway env,
flip `DESK_ODDS_FETCH=1`, leave `DESK_CROSS_VENUE_EDGE=0` — that
primes the cache without changing the verdict surface. Then watch
`desk fetch-odds`'s "venues seen" log line over a few days. Once
Pinnacle + Betfair Exchange + William Hill consistently show up, do
the threshold re-tune above and flip `DESK_CROSS_VENUE_EDGE=1`.

### Follow-up — Avoid redefinition for cross-venue

Per the scope doc §4, "Avoid becomes meaningful again" on a
multi-venue margined set — a side worse than model at every venue,
or a pathological overround = trap. **Not implemented in v1.** The
existing Avoid rule still applies (`every side ≤ avoid_pp` against
the cost surface — true_price under the flag) and remains
structurally impossible to fire on a single-venue normalised market
(per CLAUDE.md). Either:

- Lower the Avoid threshold (`DESK_AVOID_PP`) once the flag is on,
  since true_price is strictly ≥ implied_p so edges shift more
  negative, OR
- Add the proper Avoid-redefinition ADR — max-side edge ≤ avoid_pp,
  or market-distortion overround threshold. Per the brief, this is
  "OPTIONAL in v1 — flag it as a follow-up ADR, don't block on it."

### Follow-up — Outrights through the same pipeline

v1 covers per-match 1X2 only (per the scope guardrails: "NO
outrights"). Outright markets need Shin de-vig (the
`NotImplementedError` seam in `desk/pricing/devig.py`) before they
can join — multiplicative on a 135% overround over-shades favourites.
The flag is already in place (`DESK_DEVIG_METHOD`); Shin is the
next ADR candidate.

### Follow-up — Front-end consumption

The contract now carries `market_prices` + `consensus_fair` +
`region`, but `site/generate.py` still renders only the legacy
single-venue CTA + the existing Polymarket "implied %" pill. No code
in the static-site renderer reads the new fields yet. That's the
next workstream — render the cross-venue comparison card
(`desk-comparison-mockup.html`) from the published JSON.

### Follow-up — Affiliate / responsible-gambling

Out of engine scope, per the brief. Linking out to William Hill +
Sky Bet is gambling promotion; jurisdiction rules + RG notices +
affiliate terms differ from prediction markets. The engine writes
the URLs; whether the front-end shows them on a given page is a
separate workstream.

## Files touched

- New: `desk/desk/pricing/{__init__,cost,devig,consensus}.py`
- New: `desk/desk/data/oddsapi/{__init__,client,cache,venues,events,refresh,status}.py`
- New: `desk/desk/sports/football/{oddsapi_glue,oddsapi_prices}.py`
- New: `desk/desk/publish/market_prices.py`
- New: `desk/docs/adr/0004-cross-venue-prices.md`
- Modified: `desk/desk/verdict/{compare,decide}.py`
- Modified: `desk/desk/publish/{contract,__init__}.py`
- Modified: `desk/desk/sports/football/sport.py`
- Modified: `desk/desk/runner.py`, `desk/desk/explainer/stub.py`
- Modified: `desk/desk/config.py`, `desk/desk/cli.py`
- Modified: `desk/desk/contract.schema.json`, `desk/CONTRACT_CHANGELOG.md`
- Modified: `desk_refresh_loop.py` (project root), `CLAUDE.md`
- Test files: `desk/tests/pricing/`, `desk/tests/data/oddsapi/`,
  `desk/tests/publish/`, `desk/tests/sports/football/test_oddsapi_*.py`,
  appended to `desk/tests/verdict/test_{compare,decide}.py` +
  `desk/tests/test_explainer.py`.
