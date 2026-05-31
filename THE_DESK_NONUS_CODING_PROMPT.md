# Coding prompt — The Desk: non-US sportsbook integration + cross-venue price comparison

_Paste this into a coding session working in the `prophet` repo. Companion specs:
`THE_DESK_NONUS_SPORTSBOOK_SCOPING.md` (methodology + pipeline impact) and
`the-desk-positioning.md` (why). Read both before starting._

---

## Context

You're working in The Desk — a verdict engine inside the `prophet` repo (`desk/`). It evaluates priced
football markets and emits a per-match `verdict.json` (Pick / Pass / Avoid) plus editorial copy. Pipeline:
**ingest → features → model → verdict → explainer → publish.** Read `desk/`'s section in the root
`CLAUDE.md` and `desk/THE_DESK_SPEC.md` for the full picture.

We are re-orienting the site to **non-US traffic**. The comparison stops being Polymarket-vs-Kalshi and
becomes **Polymarket vs sportsbooks/exchanges**. The hard part is that a
prediction-market price and a sportsbook price are not directly comparable — the book bakes in a hidden
margin. This task makes them comparable and surfaces where they disagree.

## Non-negotiable invariants (do not break)

1. **The model never reads markets.** `model_p` is computed with no knowledge of any price. Keep it that way.
2. **Sport boundary.** Sport-agnostic code (`verdict/`, `publish/`, `runner.py`, the new pricing module)
   must NOT import from `desk/sports/football/`. Cross only through the `Sport` Protocol.
3. **Contract is additive-only.** Adding fields to the published JSON requires an ADR in `desk/docs/adr/`
   + a `CONTRACT_CHANGELOG.md` entry + a regenerated `desk/contract.schema.json` (the in-sync test enforces it).
4. **Backtest must stay byte-identical with the feature flag OFF.** WC-2022 replay Brier + verdict counts
   must not move unless the flag is on. There's an existing test asserting `replay.py` never imports live ingest — keep it green.
5. Work on `staging`. Keep `pytest` green (currently 553 tests). Add tests for everything new.

## Goal

Given a match and a set of venues, for **each side** compute one comparable number — the **true price**
(effective implied probability you actually pay) — rank venues by it, compute the model edge against the
best price, and publish per-venue prices so the site can render the cross-venue comparison card
(`desk-comparison-mockup.html`).

## Methodology (implement exactly — full derivation in the scoping doc §2)

For each side, per venue, compute two separate numbers:

**(A) True price `e`** — effective implied probability paid, all-in. This drives edge + best-venue.

| Venue type | `e` |
|---|---|
| Sportsbook (margin in price, no commission) — Pinnacle, William Hill, Sky Bet | `e = 1/decimal` |
| Exchange (back odds `b`, commission `c` on net win) — Betfair Exchange | `d_eff = 1 + (b−1)(1−c)`; `e = 1/d_eff` |
| Prediction market — Polymarket | `e = ask + taker_fee + half_spread` (sports fee ≈ 0.75% at the 50/50 peak, scaling toward tails; add slippage on thin books) |

**(B) Fair probability `fair_p`** — margin-stripped opinion, for the "market consensus" line ONLY. Never used for edge.
- v1: multiplicative — `fair_i = implied_i / Σ implied` over the full outcome set.
- Leave a pluggable seam for Shin/power de-vig (needed for outrights later) — don't implement Shin in v1.

**Derived:**
```
edge_pp        = (model_p − min_venue(e)) × 100        # the verdict's number
best_venue     = argmin_venue(e)                        # cheapest place to act
consensus_fair = sharp-weighted blend of fair_p across venues   # narrative only
```
Value exists on a side iff `model_p > e`. Comparing `model_p` to `fair_p` instead of `e` is the bug to avoid.

## File-by-file plan (match existing repo patterns)

1. **Odds source** — new external provider under `desk/desk/data/oddsapi/` mirroring the `api_football/`
   pattern: `client.py` (async httpx, The Odds API v4, `regions=uk,eu`, `oddsFormat=decimal`, key from env),
   `status.py` (quota probe), `cache.py` (sqlite, gitignored; Railway path override env). Then a football-side
   glue in `desk/sports/football/` that resolves Odds-API events → existing `FixtureRef` + canonical outcome
   set `{home, draw, away}` (entity resolution like the Poly title→ISO3 work).
2. **Pricing module** — NEW sport-agnostic package `desk/desk/pricing/`: `devig.py` (multiplicative now,
   Shin seam), `cost.py` (`e` per venue type — the table above), `consensus.py` (sharp-weighted fair blend).
   Pure functions, no I/O. This is where the math lives and where most unit tests go.
3. **MarketSnapshot / compare** — extend the price object (`desk/desk/verdict/compare.py` +
   `ingest/polymarket_prices.py`) to hold **multiple venues per side**, each with: raw quote, venue type,
   region, `e`, `fair_p`. `best_for(side)` returns the min-`e` venue.
4. **Verdict** — `decide.py`: edge = `model_p − min_venue(e)`. Re-tune Pick/Pass/Avoid thresholds against the
   backtest (they were set on Poly-only normalized odds). Avoid-redefinition is OPTIONAL in v1 — flag it as a
   follow-up ADR, don't block on it.
5. **Contract** — `publish/contract.py` (Pydantic v2): `market_prices` carries per-venue, per-side
   {raw_quote, true_price, fair_p, overround}, plus `best_venue`, `consensus_fair`, and a top-level
   `region` (`us` | `non-us`). ADR + changelog + regenerate schema. **Do this behind the ADR before touching the publisher.**
6. **Explainer** — minimal in v1: `drivers` / blurb reference best venue + true price (e.g. "cheapest way in is
   William Hill at an effective 60%"). Respect `voice.py` rules + citation rules. Full editorial rewrite is a follow-up.
7. **Config/env** — `desk/desk/config.py`: `ODDS_API_KEY`, `DESK_REGION` (default `non-us`),
   `DESK_ODDS_FETCH` (default `0`, gates the fetch in `desk_refresh_loop.py`), `DESK_DEVIG_METHOD`
   (default `multiplicative`). Document each in the root `CLAUDE.md` env table.

## Scope guardrails

- **Start with ONE league's 1X2 match markets** (e.g. a single competition), NOT outrights. Outrights have
  huge overround + need Shin + thin Poly liquidity — explicitly out of scope for v1.
- Feature-flagged + region-bucketed throughout. Flag OFF ⇒ behaviour byte-identical to today.
- Don't wire affiliate links / responsible-gambling compliance — that's a separate non-engine workstream.
- If The Odds API coverage/quota for the target competition is unclear, STOP and report rather than guess.

## Tests (add these)

- `devig`: known overround set → `fair_p` sums to 1.0; favourite-longshot sanity.
- `cost`: each venue type → correct `e` (commission on exchange, fee+spread on Poly, plain `1/d` on book).
- `best_venue`: lowest `e` wins regardless of which venue holds the lowest `fair_p` (the mockup's William-Hill-vs-Pinnacle case).
- Contract round-trips; schema in-sync test passes.
- **Backtest byte-identical with flag OFF.**

## Build order (from scoping doc §6)

1. Odds-API client + cache + status probe.
2. Event→FixtureRef resolution onto `{home,draw,away}`.
3. `pricing/` module + unit tests (do this before wiring anything — it's the core).
4. Multi-venue MarketSnapshot + `best_for`.
5. Verdict edge rewrite + threshold re-tune on backtest.
6. Contract ADR + fields + publisher + schema regen.
7. Minimal explainer venue mention.
8. Flag into the refresh loop.

Deliver as commits on `staging` with `pytest` green at each step. Open a short summary of what changed +
the threshold re-tune results (before/after Pick rate + Brier on WC-2022) when done.

## Decisions already locked (don't re-litigate)

- Source = The Odds API (paid aggregator). Region focus = non-US (`uk,eu`). Market = `h2h` (1X2).
- **Launch venue set (verified pullable):** Polymarket (gamma client, not the odds API) · Pinnacle `pinnacle` (eu, sharp anchor — weight highest in consensus) · Betfair Exchange `betfair_ex_uk`/`betfair_ex_eu` (commission model) · William Hill `williamhill` (uk+eu) · Sky Bet `skybet` (uk). **Bet365 is NOT available via The Odds API for UK/EU football — do not attempt to add it.**
- De-vig = multiplicative for v1; Shin seam left for outrights later.
- User-facing label for `e` = **"true price"**; public explainer = the supermarket price-per-litre line
  (see `desk-comparison-mockup.html`). Keep probability math out of the user's view.
