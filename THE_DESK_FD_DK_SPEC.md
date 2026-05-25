# The Desk — FanDuel Predicts + DraftKings Predictions Spec (v0.1 draft)

**Status:** draft, for build by Claude Code.
**Engine owner:** Adi — built in the `prophet` repo with Claude Code.
**Date:** 2026-05-25.

**Relationship to existing specs**

- Extends the **Ingest** step of `THE_DESK_SPEC.md`. Adds two venues; touches no
  other pipeline stage. The verdict already reads *best price across venues*
  (`MarketSnapshot.best_for`), so new venues flow through with zero verdict change.
- The handoff/monetization half (§7) is the consumer side of the same US/WC
  traffic play behind the MediaTroopers partnership — these are the two
  CFTC-regulated venues that are legal for US persons nationwide (unlike Polymarket).
- Honours the sport boundary: all FD/DK logic is sport-agnostic ingest under
  `desk/ingest/`, never inside a sport package.

---

## 0. The one principle

**Rent or partner for the feed — do not make a ToS-violating scrape the production data path.**

FanDuel Predicts and DraftKings Predictions are CFTC-regulated event-contract
platforms. Neither publishes an official public API. We want both as *affiliate
handoff partners* — so scraping their book against their ToS while opening a
rev-share conversation is the wrong opening hand. The build is structured so the
data source is a single swappable adapter: a rented Apify actor for v1, replaceable
by a partner-supplied feed the moment one exists, with no change to the ingest
contract above it.

A second principle gates the whole thing: **the contract book is not the sportsbook
book.** A FanDuel *Predicts* contract price ≠ a FanDuel *Sportsbook* moneyline.
Most cheap odds APIs serve the latter. Every data-source decision in this spec is
gated on confirming it returns the CFTC contract price.

---

## 1. Goals / non-goals

**Goals**

- Add FanDuel Predicts and DraftKings Predictions as two new comparison venues,
  ingested behind the existing `Source` ABC and normalized into `VenuePrice`.
- They feed `MarketSnapshot.best_for(side)` exactly like Polymarket/Kalshi — so they
  appear in the oddschecker display *and* in the verdict pricing, same code path.
- A geo-aware handoff component that deep-links US traffic out to FD/DK, with click
  tracking from day one and an affiliate hook ready to attach when a program exists.
- A single swappable data adapter so the Apify feed can be replaced by a
  partner/official feed later with no ripple.

**Non-goals**

- No change to verdict thresholds or the market-reading logic.
- No affiliate revenue assumed in v1 — there is no confirmed CPA program for the
  prediction products yet. Track clicks now; wire payout later.
- Not a market-making or trading integration. Read-only price ingest + outbound links.

---

## 2. What these venues are (the facts that shape the build)

| | **FanDuel Predicts** | **DraftKings Predictions** |
|---|---|---|
| Exchange | CME Group | Railbird (DK's own CFTC DCM) + Crypto.com (player markets) |
| Regulator | CFTC event contracts | CFTC event contracts |
| US availability | All 50 states; sports contracts ~18 states | ~38 states for sports contracts |
| Contract shape | YES/NO, settles $1/$0 → price *is* implied prob | Same |
| Official public API | No | No |
| Ready-made Apify actor | **No** — only a FanDuel *sportsbook* scraper exists (wrong book) | **Yes** — a DraftKings Predictions actor exists |
| WC 2026 markets | Building around the World Cup | Building around the World Cup |

The contract shape is the gift: YES/NO at $1/$0 is mechanically identical to Kalshi,
so normalization is the same `price → implied_p` map already in
`desk/ingest/polymarket_prices.py`. The asymmetry is the cost driver: **DK has a
turnkey actor; FanDuel needs a custom one** (see §6, §8).

---

## 3. Where it sits in the pipeline

```
Ingest → Features → Model → Verdict → Explainer → Publish
   ▲
   │  new venues
   └── desk/ingest/prediction_venues/
```

Sport-agnostic. Adds `VenuePrice` rows tagged `venue="fanduel_predicts"` /
`venue="draftkings_predictions"` to the existing `MarketSnapshot`. The verdict
step does not learn these names exist — `best_for(side)` already minimises implied
prob across whatever venues are present.

---

## 4. Architecture — the swappable adapter

```
desk/ingest/prediction_venues/
├── base.py            # PredictionVenueSource(Source) — shared normalise + match-binding
├── provider.py        # DataProvider protocol: fetch_board() -> list[RawContract]
├── apify_provider.py   # ApifyProvider — calls a rented/custom actor, returns RawContract[]
├── partner_provider.py # stub — official/partner feed; same protocol, drops in later
├── fanduel.py         # FanDuelPredicts(PredictionVenueSource) — venue id + market map
├── draftkings.py      # DraftKingsPredictions(PredictionVenueSource)
└── match_binding.py   # FD/DK market title → Desk match_id (reuse iso3_for_name)
```

Two seams that make the feed swappable:

1. **`DataProvider` protocol** — `fetch_board()` returns provider-neutral
   `RawContract` objects (`{venue, market_title, outcome_label, yes_price, asof}`).
   `ApifyProvider` today; `PartnerProvider` the day a partner feed lands. The venue
   sources never know which one they got.
2. **`match_binding`** — FD/DK label their markets in their own words ("France to win
   the World Cup", "France vs Mexico — France"). Bind to the canonical `match_id`
   the same way ingest already does: title → ISO3 via `iso3_for_name`
   (`desk/sports/football/teams.py`), never the venue's own slug. Unbindable
   contracts are dropped with a counted reason, never guessed.

`PredictionVenueSource` extends the existing `Source` ABC (`desk/ingest/base.py`)
— `id`, `label`, `async fetch()`, registers on import. Identical lifecycle to the
Polymarket source.

---

## 5. PR ladder

- ⬜ **PR 1 — Feasibility spike (read-only, throwaway).** Confirm both unknowns
  before any ingest code is trusted:
  (a) the DK Predictions Apify actor returns the **contract** book (YES/NO prices),
  not sportsbook lines;
  (b) a workable path exists for **FanDuel Predicts** (custom actor vs. wait vs.
  partner feed);
  (c) WC market coverage + how FD/DK contract prices compare to Poly/Kalshi on the
  same fixture (is the edge real or is it the same number?).
  Output: a one-page findings note + go/no-go on each venue. No production code.
- ⬜ **PR 2 — Adapter skeleton.** `DataProvider` protocol, `RawContract`,
  `PredictionVenueSource`, `match_binding`. Unit tests on binding + normalization
  with fixture JSON. No live calls.
- ⬜ **PR 3 — DraftKings live.** `ApifyProvider` + `DraftKingsPredictions`, gated on
  `DESK_FDDK_FETCH=1`. Flows into `MarketSnapshot`. Stale-guard reuses the existing
  5-min rule in `compare.py`.
- ⬜ **PR 4 — FanDuel live.** Custom Apify actor (or partner feed if PR 1 found one).
  Same gate. If FD coverage is not viable yet, ship DK alone and leave FD dark
  behind the flag — explicitly an acceptable v1.
- ⬜ **PR 5 — Handoff + click tracking.** Geo-aware outbound component (§7).
  Affiliate hook present but inert. Click events recorded.
- ⬜ **PR 6 — Affiliate wiring.** Only when a real program exists. Attach the
  partner/CPA params to the handoff links; reconcile click → conversion.

Ship PR 1 alone first and read it before committing to the rest. It can kill FanDuel
for now without wasting a line of ingest code.

---

## 6. Cost — exact WC 2026 figures (Apify)

**Workload assumptions** (stated so the math is auditable):

- WC 2026: 104 matches + 1 outright winner market, 48 teams.
- Tournament window: 2026-06-11 → 2026-07-19 ≈ **39 days / spans 2 billing months**.
- One actor run returns the whole WC board: ~105 markets × ~3 outcomes ≈ **~315 rows/poll**.

**DraftKings Predictions — rented actor (turnkey).** Two pricing models:

| Model | Rate | WC total |
|---|---|---|
| Monthly pass (unlimited polls while active) | $49 / 30 days | 2 passes → **$98** |
| Pay-per-use, hourly polling | $0.01/req + $0.0002/row = ~$0.073/poll × 936 polls | **~$68** |
| Pay-per-use, every 30 min | ~$0.073 × 1,872 | ~$137 |
| Pay-per-use, every 15 min | ~$0.073 × 3,744 | ~$273 |

→ **Monthly pass wins above hourly polling.** Recommend the pass: **~$98** for the
whole tournament, poll as often as you like.

**FanDuel Predicts — custom actor (no turnkey option).** Built on the Apify platform,
billed as platform subscription + compute (not a per-actor rental):

| Item | Rate | WC total |
|---|---|---|
| Apify Starter platform plan | ~$39/mo | 2 months → ~$78 |
| Low-volume scrape compute | within/near included usage | ~$10–30 |

→ **~$80–110** for the tournament, **plus a one-time engineering cost to build the
actor** (the real variable — eng time, not platform fees).

**Headline:**

> **≈ $180–210 for the entire World Cup, both sites, polling generously.**
> (~$98 DraftKings monthly passes + ~$80–110 FanDuel custom actor.)
> Drops to **~$160** if DraftKings runs pay-per-use at hourly cadence.

Caveat the FanDuel number carries: it assumes the custom actor is viable, which PR 1
must confirm. If FanDuel can't be scraped cleanly, the WC cost is just the **~$98
DraftKings** line until a FanDuel partner feed lands.

For comparison, the alternatives priced out at: The Odds API $30–249/mo (but likely
sportsbook book, not contracts — fails the §0 gate); OpticOdds ~$5,000/mo/sport
(enterprise, wrong scale for this site).

---

## 7. Handoff + monetization

- Geo-aware: read state availability (DK ~38 states for sports, FD ~50). A user in a
  state where a venue isn't live never sees that venue's outbound link.
- The handoff is an **outbound deep link** to the relevant FD/DK market, rendered
  next to the venue's price in the comparison card. Mirror the existing
  "View source on [venue]" pattern (already used for Poly/Kalshi).
- **Click tracking from day one** — record `{match_id, venue, state, ts}` on click so
  there's a conversion baseline before any affiliate deal.
- **Affiliate hook inert until a program exists.** Build the link-decoration seam
  (append partner/CPA params) but leave it unconfigured. There is no confirmed CPA
  program for the prediction products today; do not block the build on it.
- Disclosure: one clean line that these are CFTC-regulated event-contract venues and
  that links are informational — consistent with the educational-only, pre-incorporation
  posture. Not gambling-affiliate framing.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Cheap API serves sportsbook book, not contracts | §0 gate; PR 1 confirms the contract price explicitly before any reliance |
| No FanDuel actor exists | PR 1 decides custom-actor vs wait vs partner feed; DK-only is an acceptable v1 |
| ToS / partner-conflict from scraping | Swappable adapter; treat Apify as bridge, pursue partner feed as part of the affiliate talks |
| Anti-bot / geo-gated price endpoints | Apify handles host rotation; if FD needs a logged-in geo-verified session, that's a PR 1 finding that may push to partner feed |
| Silent stale prices break a live verdict | Reuse `MarketSnapshot.stale()` 5-min guard; missing venue → that side simply isn't in `best_for`, verdict falls back to Pass |
| No affiliate revenue in v1 | Expected. Track clicks; monetize when a program lands |

---

## 9. Env vars (proposed)

| Variable | Default | Purpose |
|---|---|---|
| `DESK_FDDK_FETCH` | `0` | Master gate — enable FD/DK ingest on the refresh tick |
| `DESK_FDDK_PROVIDER` | `apify` | `apify` \| `partner` — selects the `DataProvider` impl |
| `APIFY_TOKEN` | unset | Apify API token; required when provider=`apify` |
| `DESK_FDDK_DK_ACTOR` | unset | Apify actor id for the DraftKings Predictions board |
| `DESK_FDDK_FD_ACTOR` | unset | Apify actor id for the custom FanDuel Predicts actor |
| `DESK_FDDK_POLL_SEC` | `1800` | Poll cadence for the FD/DK board |
| `DESK_FDDK_STATES_DK` | (built-in list) | DK sports-contract state allowlist for geo-aware handoff |

All gated off by default — a fresh deploy does not hit FD/DK until the operator opts in.

---

## 10. Open questions for PR 1 to close

1. Does the DK Predictions actor return contract YES prices, and at what latency?
2. Is a FanDuel Predicts custom actor viable, or is the price endpoint behind a
   geo-verified login that makes a partner feed the only clean path?
3. On a shared WC fixture, do FD/DK contract prices differ enough from Poly/Kalshi to
   produce *new* edges — or do they track the same number (in which case they add
   coverage/legitimacy but not verdict signal)?
4. Is there any early-access affiliate/partner contact at FD or DK worth opening now,
   so the feed and the rev-share land together?
