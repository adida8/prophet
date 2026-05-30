# The Desk — Non-US pivot: sportsbook integration + cross-venue price comparison

_Scoping doc · 2026-05-29 · build target: Adi. Companion to `the-desk-positioning.md`._

## 0. What this is

The site re-orients to **non-US traffic**. The comparison surface becomes **Polymarket vs sportsbooks/exchanges**, not Poly vs Kalshi. This doc scopes (a) **how a prediction-market price and a sportsbook price are made comparable** — the load-bearing problem — and (b) **what changes in each Desk pipeline stage.**

**Locked launch venues (all verified pullable — see §note):**

| Venue | Role | Source / key |
|---|---|---|
| Polymarket | Prediction-market spine | existing gamma client (not via odds API) |
| Pinnacle | Sharp fair-value anchor | The Odds API `pinnacle` (eu) |
| Betfair Exchange | Exchange (commission model) | The Odds API `betfair_ex_uk` / `betfair_ex_eu` |
| William Hill | Consumer book | The Odds API `williamhill` (uk+eu) |
| Sky Bet | Consumer book | The Odds API `skybet` (uk) |

**Bet365 was dropped — it is NOT available via The Odds API for UK/EU football** (only `bet365_au`, AFL/NRL). Don't design around it. Markets used: `h2h` (1X2 moneyline).

The model invariant holds: the engine still produces `model_p` without ever reading a market. Everything below sits in the **ingest → features (normalize) → verdict → explainer → publish** path that *does* see prices.

---

## 1. The core problem

A Polymarket price and a William Hill price are not the same kind of number.

- **Polymarket** quotes a price that *is* a probability. A share at $0.18 means 18%; it pays $1 on YES. Its only costs are the bid-ask spread, a ~0.75% sports taker fee (introduced 2026 — it is no longer free), and slippage.
- **A sportsbook** quotes **margined odds**. Decimal 5.00 implies 20%, but the implied probabilities of *all* outcomes sum to **more than 100%**. That excess is the bookmaker's margin (the "overround" / "vig") — ~104–107% on a sharp 3-way football match, and **120–150%+ on an outright tournament-winner market**. The book's price is not its honest opinion; it's its opinion *plus* a built-in edge.
- **The Betfair exchange** is a third shape — peer-to-peer back/lay like Polymarket, near-zero margin, but a **commission on net winnings** (~2–5%). It is structurally closer to Polymarket than to a book like William Hill. **Do not lump it with the books.**

So before anything compares, every venue's quote has to be reduced to two distinct numbers.

---

## 2. The two numbers that matter

For every **side** of every market, compute per venue:

**(A) Effective entry cost `e`** — the all-in implied probability you actually pay to back this side, *including* margin, fee, spread, and commission. This drives **"where is the best value / which venue to act on."**

**(B) Fair probability `fair_p`** — the venue's margin-stripped opinion of the true probability. This drives **"market consensus"** and lets you compare what each venue *believes* against the model and against each other.

These are different and the difference is the whole point. A book can hold the **most bearish fair opinion** on a team yet still offer the **cheapest price** to back it.

### Formulas

Implied probability from a quote:
- Decimal odds `d` → `implied = 1/d`
- Polymarket ask price `p` (0–1) → `implied = p`

**Effective entry cost `e` (per venue):**

| Venue type | `e` (effective implied you pay) |
|---|---|
| Sportsbook (Pinnacle / William Hill / Sky Bet — margin is in the price, no commission) | `e = 1/d` |
| Exchange (Betfair — back odds `b`, commission `c` on net win) | effective payout `d_eff = 1 + (b−1)(1−c)`, then `e = 1/d_eff` |
| Polymarket | `e = ask + taker_fee + half_spread` (fee ≈ 0.75%·position at the 50/50 peak, less toward the tails; add slippage on thin books) |

**Fair probability `fair_p` (de-vig):** strip the margin across the full outcome set.
- *Multiplicative (default):* `fair_i = implied_i / Σ implied`
- *Shin / power method (recommended for outrights):* solves for the longshot bias so favourites aren't over-shaded — matters a lot on a 130%+ outright book.

**The unifying result:** value exists on a side iff `model_p > e`. So:

```
edge_pp(venue) = (model_p − e_venue) × 100
best venue     = argmin_venue(e_venue)         # cheapest place to act
Desk edge      = model_p − min_venue(e_venue)  # the number the verdict uses
consensus_fair = sharp-weighted blend of fair_p across venues  # for the "market says" line
```

This is the cleanest framing: **everything collapses to one comparable number per side per venue — the effective entry cost `e`.** The model supplies `model_p`. The verdict compares them. The de-vigged `fair_p` is a *separate* number used only for the consensus narrative, never for the edge.

> Why this matters: comparing `model_p` to the *de-vigged fair* (instead of to `e`) is the classic mistake — it claims value the margin will eat. You only have value if the model beats the price you actually pay.

---

## 3. Worked example — Argentina to win the World Cup

`model_p = 21%`. (Numbers illustrative.)

| Venue | Raw quote | Effective entry `e` | De-vigged `fair_p` |
|---|---|---|---|
| Polymarket | ask $0.18 | **18.6%** (+fee +spread) | 16.9% |
| Pinnacle (sharp anchor) | decimal 5.40 | **18.5%** | 16.8% (overround ~110%) |
| William Hill | decimal 5.50 | **18.2%** (1/5.50) | 14.6% (overround ~135%) |
| Betfair Exchange | back 5.00, 2% comm. | **20.4%** | 18.7% |

Reading it:
- **Consensus fair ≈ 16.8%** — anchored on Pinnacle (sharp, lowest margin), not a flat average. Model at 21% sits well above → the model thinks Argentina is underpriced.
- **Cheapest place to act = William Hill at `e` = 18.2%.** Edge = `21 − 18.2 = +2.8pp` → **Pick, back Argentina on William Hill.**
- The nuance only a cost-aware engine catches: **William Hill holds the *lowest* fair opinion (14.6%, most bearish) yet offers the *best price* (18.2%)** — its raw longshot line is generous relative to its own inflated book. Naive "compare the percentages" logic would pick the wrong venue or miss the trade. Pinnacle's fair (16.8%) is what the consensus trusts; William Hill's price is where you act.

This is the dislocation story the product sells, made precise.

---

## 4. Impact on each Desk stage

| Stage | Change | New? |
|---|---|---|
| **Ingest** | Add a paid odds-API adapter (The Odds API — `regions=uk,eu`, `oddsFormat=decimal`, football `h2h` for 1X2 + outrights). Keep the Polymarket gamma client. Each venue's market must resolve to the canonical match + outcome set — a real entity-resolution job (team-name + market-type matching), parallel to the existing Poly title→ISO3 work. | **New adapter**, extends existing ingest |
| **Features / normalize** | **New module — the heart of this work.** De-vig each book (`§2`), compute `fair_p` per venue, `e` per venue per side, the consensus blend, per-book overround, and a `best_venue` pointer. Pluggable de-vig method (multiplicative vs Shin). | **New** |
| **Model** | Unchanged. Still emits `model_p`, still never reads markets. | No |
| **Verdict** | Edge redefined: `model_p − min_venue(e)` instead of edge vs a single normalized Poly price. Re-tune Pick/Pass/Avoid thresholds — they were set on Poly-only normalized closing odds; a multi-venue margined set behaves differently. **Avoid becomes meaningful again** (currently structurally impossible on single-venue normalized odds — see CLAUDE.md): a side worse than model at *every* venue, or a market with pathological overround = trap. | Reworked |
| **Explainer** | Copy now names venue + price + cross-venue-type disagreement and the best place to act. ("Poly implies 19%, William Hill's line 22% before its margin; the model is at 21%; best value to back Argentina is William Hill at 5.50.") Voice rules + citation rules unchanged. | Extended |
| **Publish / contract** | `market_prices` must carry **per-venue, per-side**: raw quote, `e`, `fair_p`, overround, plus `best_venue` and `consensus_fair`. Add a `region` bucket (`us` / `non-us`) so the site serves the right venue set. **This is a contract change → ADR required** (repo rule: adding contract fields needs an ADR). | Contract change |

---

## 5. Hard problems / decisions to resolve

1. **De-vig method is a real fork.** Multiplicative is fine for low-margin 1X2; **outrights need Shin or power** or favourites get over-shaded on a 135% book. Pick, document, make it swappable. *(ADR candidate.)*
2. **Outrights are the hard case and your flagship example.** Huge overround, many outcomes, noisy de-vig, thin Poly liquidity. Expect the WC-winner market to be the least stable signal — treat its confidence accordingly.
3. **3-way football (the draw).** Books quote home/draw/away; some prediction markets split YES/NO per outcome or omit the draw. Normalize onto a canonical `{home, draw, away}` before comparing.
4. **Price synchronisation.** Odds move; books move faster than Poly settles. The comparison is only valid at a **timestamped snapshot** — capture all venues within the same window or the dislocation is an artifact.
5. **Liquidity & limits.** A "best price" you can't get matched at (thin Poly market) or that a book limits/voids for winning accounts is a false signal. Flag low-liquidity sides; don't headline them.
6. **Exchange ≠ book.** Model Betfair with commission-adjusted effective odds; don't apply book de-vig to it.
7. **Odds-API budget & coverage.** Confirm WC-2026 + target leagues are covered on `uk/eu`, the request quota, and refresh cadence vs cost. Cache like the other Desk sources (mounted volume on Railway).
8. **Affiliate / legal.** Linking to bookmakers is gambling promotion — jurisdiction rules, responsible-gambling notices, and affiliate terms differ from prediction markets. Out of engine scope but gates launch.

---

## 6. Recommended build order

1. Odds-API ingest adapter + entity resolution onto canonical matches (start with one clean surface — e.g. a single league's 1X2, *not* outrights).
2. Normalization module: implied → `e` and `fair_p`, de-vig (multiplicative first), per-venue + consensus.
3. Wire the new edge (`model_p − min e`) into the verdict; re-tune thresholds on the backtest before trusting it.
4. Extend the contract (`region`, per-venue prices) behind an ADR; update the publisher + site to show the cross-venue board.
5. Add the exchange (Betfair commission model) and Shin de-vig for outrights.
6. Only then turn on outright markets.

**Validate on one non-US 1X2 surface (Poly vs Pinnacle vs William Hill vs Betfair) before adding outrights or the US bucket.** The math is identical across buckets; prove it on the easy case first.
