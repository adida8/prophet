# Strategy Snapshot — 13 May 2026

**Participants:** the operator · Claude
**Context:** Pre-launch strategic review of Odds Primer's affiliate-led launch. Started as deep-dive on affiliate economics; evolved into commercial-model architecture and brand-portfolio question.

---

## What landed

### 1. The business shape

**Affiliate-led launch, bootstrap, no capital.** Both founders go full-time when monthly recurring affiliate income covers ~£60–80K each plus operating headroom — roughly **$15–25K MRR**. That's the inflection point, not break-even.

**Exit framing recalibrated.** Originally proposed $100M-in-24-months; recalibrated to "$15M+ would be wonderful." That sits comfortably inside the Y3 optimistic scenario at typical multiples (no engineering required, just landing in the optimistic case).

**No buyer identified yet.** Acceptable — if Y3 lands in the optimistic range, Better Collective / Catena / Gambling.com / Polymarket / a Flutter affiliate-arm will find Odds Primer rather than the other way around.

### 2. Editorial brand global, venue basket regional

Earlier framings narrowed to US-only; the operator corrected. The structure that survived:

| Region | Venues in basket | Per-user value |
|---|---|---|
| **US** | Polymarket US, Kalshi, Robinhood, DK Predictions, FanDuel Predicts | $10–$300 CPA (DK/FD carry the unit economics) |
| **UK** | Smarkets, Betfair Exchange, bet365, Paddy Power, William Hill | £75–£250 CPA, 25–35% rev-share |
| **EU ex FR / BE / PL** | Polymarket international, Bwin, Tipico, Unibet, Betclic | $10 + 30% rev-share / €50–€200 CPA |
| **LatAm / Asia / Africa** | Polymarket international, Limitless (Base), local sportsbooks | $10 + 30% rev-share, 180-day trail |

**Geofence at the CDN, not the page.** Wrong basket reaching the wrong reader is personal liability while still sole-trader.

### 3. Three-phase commercial sequence

- **Phase 1 — Direct affiliate (now → Sep 2026).** WC 2026 wedge. Build editorial brand. Target $20–40K MRR.
- **Phase 2 — Sub-affiliate / aggregator (Sep 2026 → Q1 2027).** Recruit 10–20 creators. Odds Primer is the master affiliate; creators get 40–60% of revenue plus convenience of one link covering 5+ venues. Ramp to $50–100K MRR.
- **Phase 3 — B2B verdict feed (Q2 2027+).** With 12 months of public verdict track record + creator network as proof of operational chops, license The Desk's JSON feed to publishers. ACV £50–150K, 3–6 month cycle.

**Phase 1 only** = Y3 revenue $8–15M (modelled).
**Phase 1 + 2 + 3** = Y3 revenue $12–25M.

### 4. Three-layer architecture (the big clarification)

This was the most important framework that landed today.

- **Layer 1 — The Desk (engine).** Sport-agnostic plugin system. Produces canonical verdict JSON. Internal-only currently. **This is the moat.**
- **Layer 2 — Consumer brand(s).** Each brand is a thin editorial wrapper on The Desk's JSON. Odds Primer is one wrapper. Other verticals get other wrappers as needed. Brands share zero code, share 100% of the engine.
- **Layer 3 — B2B verdict feed.** Same JSON, sold to publishers / media / exchanges / smaller affiliates. "Powered by The Desk" or white-label.

Engineering cost: Phase 2 adds ~6 weeks of work, Phase 3 another ~4 weeks. The model + ingestion + verdict generation is the moat and it's built once.

### 5. Multi-sport, multi-vertical roadmap

the operator's ambition for Odds Primer is "verdict layer for every priced market on earth — football is just where we start." The architecture supports it (sport plugin system already built).

| Year | Verticals |
|---|---|
| Y1 (now → May 2027) | Football (WC 2026 + club). One additional sport added Q1 2027 — likely **NBA** or **NFL** (US peak season, DK/FD CPAs). |
| Y2 (May 2027 → May 2028) | NFL (Sep), NBA (Oct), tennis (year-round), **horse racing** (Cheltenham, Royal Ascot — UK affiliate goldmine). First non-sport: **US 2028 election cycle**. |
| Y3 (May 2028 → May 2029) | 8–12 sports. Politics, economics (Fed, CPI), entertainment (Oscars, Eurovision). Some crypto / weather markets. |

**Trap to avoid:** launching with 5 sports simultaneously because the architecture allows it. Brand fuzz, thin models, wasted WC wedge, two founders running five GTMs.

### 6. Prediction markets vs sports betting (a real distinction)

Forced by the racing-vertical discussion. The clean separation:

- **Prediction markets** = CFTC-regulated event contracts (Kalshi, Polymarket US, Robinhood event contracts, DK Predictions, FanDuel Predicts) + offshore P2P (Polymarket international, Limitless). ~5–6M MAU globally. **The empty editorial space is here.**
- **Sports betting** = bookmaker fixed odds + parimutuel pools + exchange (Betfair). £100B+ market. **The editorial category is fully serviced** by Racing Post, oddschecker, Action Network, Better Collective, Catena — 30 years of incumbents.

Horse racing is **sports betting**, not a prediction market. The "empty editorial space" thesis only holds in the prediction-market vertical.

### 7. Brand architecture — multi-brand on shared engine

Resolution from the "spin new brands per sport" discussion:

**Rule:** spin a new brand when the *mental model* of the audience is different enough that voice + UI + vernacular can't be shared with the parent.

| Vertical | Fits under Odds Primer? |
|---|---|
| Football, NBA, NFL, tennis, politics, economics, esports, crypto markets | Yes — native fit |
| **Horse racing** | **No — own brand (independent name, not "Odds Primer Racing")** |

Family naming (Odds Primer X) for prediction-market-native verticals. Independent naming for sports-betting verticals where the mental model diverges.

### 8. B2B vs B2C tension in mature verticals

Critical lesson from the racing scan: **don't compete with B2B customers in their own verticals.** If Racing Post / oddschecker are good Phase 3 customers for the verdict feed, don't simultaneously launch a competing racing consumer brand.

Three resolution patterns:

1. **Vertical-pure brands + horizontal B2B feed.** Multiple consumer brands; B2B sells only to non-competing verticals.
2. **One consumer brand + aggressive B2B.** Keep Odds Primer broad, sell racing/NFL verdict feeds to incumbents.
3. **Skip consumer in some verticals entirely.** Own consumer in prediction-market-native verticals; B2B-only in mature sportsbook verticals (racing, NFL Sunday accumulators, UK/EU sportsbook flow).

**Best-margin play is likely option 3.** Highest-margin per founder-hour, most defensible long-term.

---

## Probability of personal millionaire outcome from this

Rough probability stack:

| Outcome | Probability | the operator's share post-tax (50/50 split) | Millionaire? |
|---|---|---|---|
| Complete failure | ~35% | Loss of 12–24 months | No |
| Lifestyle side-hustle | ~28% | £30–80K/yr while it runs | No, from this alone |
| Modest exit ($1–5M) | ~15% | £400K–£2M | Borderline |
| Solid exit ($5–15M) | ~12% | £2–5.5M | Yes |
| Sustained profitable build, no exit | ~6% | Accumulates past £1M over 4–5 years | Yes |
| Strategic exit ($25–100M) | ~4% | £8–35M | Multi-millionaire |

**Net probability: ~20%.** Higher than the lottery; lower than 10–15 years of aggressive saving at a senior tech job. Asymmetric payoff justifies the bet.

---

## Affiliate-economics gates (what determines paid-media viability)

CAC must be < affiliate revenue per funded account. This means paid media is **only viable** for the high-CPA venues:

- **DraftKings Predictions** ($100–$300 CPA) — paid media on the table if CAC stays below ~$80
- **FanDuel Predicts** ($25–$35 + 35% rev-share 730d) — marginal; rev-share takes 6–12 months to recover CAC
- **Kalshi** — depends on private deal
- **UK sportsbooks** (£75–£250 CPA) — works if CAC stays below ~£40, but market fully serviced by incumbents
- **Polymarket** ($10 + 30% rev-share) — **almost never works for paid media.** Per-funded-account economics can't recover acquisition cost
- **Robinhood** ($20 cap) — too low for paid media

**Paid-media strategy is therefore specifically: US-routed traffic to DK / FD / Kalshi.** Everything else stays organic + sub-affiliate.

## Channel mix to test pre-WC

Reddit Ads (gambling-tolerant, precise targeting), newsletter sponsorships (Action Network's own, Sherwood, Sportico, indie betting newsletters), small podcast sponsorships ($500–$2K per episode on shows with 5–25K listeners), YouTube pre-roll during WC.

**Avoid:** Google Search Ads (gambling certification nightmare for sole trader), Meta (gambling restrictions), TikTok (compliance maze), programmatic display (no scale advantage early).

## Attribution non-negotiable

Before £1 hits an ad platform:
1. UTM tagging discipline on every link
2. Each venue's postback URL configured to fire on funded-account events
3. Live dashboard showing CAC per channel per venue, refreshed daily

---

## Comparables locked

| Business | Revenue | Exit / cap | Note |
|---|---|---|---|
| Better Collective | $365M | $675M mkt cap | The rollup — buys $10M+ EBITDA |
| Gambling.com Group | $165M | $158M mkt cap | Best-run pure-play; OddsJam data pivot |
| Oddschecker | ~$70M | Acq $215M (2021) | Category-defining brand |
| Catena Media | $57M | $20M mkt cap | Cautionary tale — Google dependency |
| Action Network | ~$35M | Acq $240M (2021) | Closest analogue to Odds Primer |
| OLBG | ~$7M | Private | Niche-but-durable; never sold |
| VSiN | sub-$10M | Acq $70M (2021), written down | Strategic-buyer-vibes pricing, didn't work |
| Spotlight Sports Group (Racing Post) | ~£75M | ~£500M target sale 2026 | Being prepped for exit; buyer may accelerate verdict product |
| The Athletic | $220M | NYT acq $550M | Different DNA — subs, not affiliate |

## Exit multiples by positioning

| Comp set | Revenue multiple |
|---|---|
| Sport affiliate site (football only) | 4–7× |
| Multi-sport affiliate platform | 6–10× |
| Cross-vertical data + editorial (politics + sport + econ) | 10–15× |

---

## Horse racing competitive landscape (May 2026 snapshot)

Researched in this session. Key findings:

- **The model-driven verdict space is crowded at the bottom and empty at the top.**
- **Top end:** Racing Post (SSG / Exponent PE, being sold), Timeform (Flutter), Geegeez (~£35/mo niche tools play).
- **Bottom end:** FormGenie, Racing Oracle, AI Race Day, PaddockAI, Race-AI, Tippertoo — all read like 2009 affiliate landing pages.
- **The "model + editorial credibility + per-runner Pick / Pass / Avoid" position is open.** Timeform has model, no edge framing. Racing Post has editorial, no model.
- **HKJC is the canary** — even a statutory monopoly is rolling out gen-AI Interactive Selection stations. Category direction is unambiguous.
- **Wedge if entering racing:** Cheltenham 2027 ante-post, window opens December 2026.
- **SSG sale is the strategic risk** — buyer could accelerate verdict-style product within 18 months.

---

## Strategic risks priced in

- US state AG action against Kalshi (9 states currently restricted/contested)
- UK CAP Code (Sept 2025) caught non-paid affiliate content for unlicensed operators — TGP Europe £3.3M precedent
- DK/FD CPAs compressing toward Polymarket levels
- SSG sale buyer building competing racing-verdict product
- Founder split / focus across two people splitting attention
- Sole-trader personal liability — must incorporate before launch traffic

---

## Anti-patterns identified

Things to NOT do:

- Don't launch with 5 sports simultaneously (architecture allows it; market doesn't reward it)
- Don't promote unlicensed operators (Polymarket, Kalshi, DK, FD) to UK readers (Section-33 risk)
- Don't try all three commercial layers (B2C / sub-affiliate / B2B) simultaneously — sequence them
- Don't buy paid media to Polymarket (economics don't work)
- Don't engage UK gambling-affiliate friends as strategists (execution fine, strategy not)
- Don't run as sole trader past launch traffic (personal liability)
- Don't compete with B2B customers in their verticals
- Don't lead with "prediction markets" framing if the long-term vision is "every priced market"

---

## 30-day focus items (pre-launch checklist)

1. Apply to affiliate programmes in all 3 regions (US, UK, RoW)
2. Geofence at the CDN before any traffic
3. Talk to UK gambling-affiliate solicitor (TLT / Wiggin / Harris Hagan)
4. Run 30-day affiliate experiment at launch; pick routing defaults by real numbers
5. UK Ltd before launch traffic; transfer affiliate accounts to entity

---

## Open questions deferred for future

- Which sport for Y1 Q1 2027 expansion — NBA or NFL?
- Independent brand for racing — name and when to start building?
- B2B feed pricing model — per-call API, monthly subscription, or white-label?
- Sub-affiliate rev-share split — 40 / 50 / 60% to creator?
- Externalize "The Desk" as a platform brand, or keep internal-only and lead with consumer brand(s)?
- Resolution to B2B-vs-consumer tension in mature verticals — option 1, 2, or 3?
- Specific UK solicitor engaged — and when?
- Cheltenham 2027 race launch — go / no-go decision by when?

---

## Deck artefacts produced

- `Odds-Primer-affiliate-strategy-review-May-2026.pptx` — 13-slide full review (US-only framing, superseded)
- `Odds-Primer-affiliate-summary-May-2026.pptx` — 5-slide US-only summary (superseded)
- Drafted but not shipped: global-frame 5-slide summary (build script in outputs folder, three QA issues outstanding on slides 1, 3, 4)

The decks should not be referenced for venue / regional positioning — they pre-date the global reframe, the multi-brand resolution, and the prediction-vs-sportsbook clarification.

---

## The line that sticks

> The wedge isn't a venue or a market. It's the editorial space prediction markets have created and nobody has filled — the "model says X%, market says Y%, here's why" verdict format applied to every priced market on earth. Football is just the launch wedge because WC 2026 concentrates audience and ante-post liquidity gives the model time to publish before prices firm.

Internal short form: **"Verdict layer for every priced market on earth — football is just where we start."**
