# Prophet → [brand TBD] — Project Snapshot

**Last updated:** 2026-04-20 (post-pivot)
**Status:** Pre-beta. Scaffolding deployed. Pivoted from public-launch aggregator to decision-support workspace. Working name "PredictionEdge" retired — see "Brand" below. Private-beta target 2026-04-26.

---

## What this is (post-pivot)

Prophet-MVP-v1 started as a Python/React paper-trading bot for Kalshi demo. The original April pivot — into a public OddsChecker-for-prediction-markets affiliate site — was abandoned after competitor research showed the wedge was already commoditized. The current plan productizes the Prophet paper-trading + risk-management stack as a decision-support layer on top of Kalshi and Polymarket. The codebase and deploy are preserved; the product thesis changed.

Positioning, one line: **A decision-support workspace for serious prediction-market traders — matched-market intelligence, Prophet-strategy signals, and Kelly-sized stakes across Kalshi and Polymarket.**

Not: an odds aggregator, a Bloomberg terminal clone, a sports-betting affiliate site.
Closer to: TradingView meets backtest.py for event markets.

---

## Why the pivot (research findings, April 2026)

Cross-validated research with web search and two AI reviews (Claude, ChatGPT) produced a GO/NO-GO score of **44/100 on the original scope (NO-GO)**. Key findings:

- Market size is real. Kalshi $12–13B/mo + Polymarket $10.5B/mo (March 2026). Bernstein backs $1T/2030 at ~80% CAGR.
- Competitive whitespace is gone. [yourpredictionedge.com](https://yourpredictionedge.com) ships a near-identical product at $9.99/mo; Oddpool ($30 Pro, $100 Premium), FORS (Solana), Prediction Market Tools, FinFeedAPI, PolyRouter are all live. VegasInsider and Gambling.com Group (post-OddsJam $160M acquisition) already publish PM comparison content with affiliate codes.
- Affiliate economics are softer than the onepager claimed. Polymarket pays 30% revshare × 180d gated behind $10K traded volume; Kalshi pays $25 in trading credits, not cash. No verified public CPA at the claimed $60–300/depositor level.
- AI Overviews cratered betting-affiliate SEO. 96% of betting affiliate sites hit; CTR 15%→8%. The Month 6+ SEO revenue plan runs into a structural headwind.
- Regulatory posture is net positive but has overhang. Third Circuit ruled 2–1 for Kalshi (April 6, 2026), CEA preempts state gambling law. But CFTC rulemaking due Q3 2026, SCOTUS review possible, Washington state challenge active.

The pivot is to a product that (a) doesn't compete head-on with the now-crowded comparison lane, (b) productizes an asset we already own (the Prophet strategies + risk_manager.py stack), and (c) can support a paid subscription business without depending on affiliate attribution holding up.

Realistic score ceiling after the pivot: **62–70 (GO-WITH-CHANGES)**, not 90. The pivot improves differentiation, premium defensibility, and platform independence. It does not change market size, competitive whitespace, incumbent risk, or regulatory risk.

---

## The wedge

The Prophet codebase already includes `strategies/`, `risk_manager.py`, Kelly sizing, a paper-trading runner, working Kalshi RSA auth, and a Polymarket client. Oddpool, Your Prediction Edge, FORS, and media incumbents do not own this. Productizing it is the wedge.

Phase 1 builds five interlocking surfaces on top of it:
1. Matched-market engine (Kalshi ↔ Polymarket with polarity resolved)
2. Strategy runner (paper mode, live matched-market data)
3. Risk-sized suggestions (Kelly / fractional Kelly)
4. Alerts (Telegram in beta; Discord/email later)
5. Position tracker + trade journal (paper first, live-linked later)

Comparison is a supporting feature inside the workflow, not the product.

---

## Monetization stack (resequenced)

The CPA-first thesis is retired.

- **Months 1–3:** Paid subscription only ($29/mo target; revisit on data). No affiliate revenue. Expect ~30 days of zero revenue after launch.
- **Months 4–6:** Affiliate routing added where Kalshi/Polymarket programs allow. Garnish, not engine.
- **Months 6–12:** SEO event pages, programmatic content, B2B API for media partners, explore data licensing.

---

## Current build state (2026-04-20)

**Live deploy:** https://web-production-9e0f9.up.railway.app/

Working:
- FastAPI backend + Vite/React 19 frontend, deployed on Railway
- Polymarket client pulling real prices, real 24h volume, real URLs
- Kalshi RSA-PSS auth (`core/auth.py`)
- ~500 markets in feed

Broken or missing (current sprint addresses all of these):
- Kalshi pricing returns 0.0 across the board (likely wrong field — should read `yes_bid`/`yes_ask`)
- Categories all `"other"` (normalizer not applying a dictionary)
- Titles are raw ticker strings instead of English
- Expired markets in the feed
- Zero matched markets (matching engine is a stub)
- Per-market URLs lack UTM params
- No signal engine; the Prophet strategies aren't wired into any live product surface
- No alert mechanism
- No beta gate

---

## Private beta MVP (2026-04-26 target)

A trimmed 7-day sprint to a private-beta URL, invite-only, shared-password gated. See [SPRINT.md](SPRINT.md) for day-by-day execution.

**Must-have (definition of done):**
1. 10–12 hand-verified matched pairs (politics / macro / crypto; no sports)
2. Live prices from both venues, polarity resolved, dislocation computed
3. One Prophet signal per market — action, edge %, Kelly-sized stake, rationale. `hold` is a valid outcome.
4. `MatchedMarketsTable` rendering the above
5. Detail drawer on row click (no sparkline, no P&L)
6. Watchlist (localStorage)
7. Simple password gate

**Stretch (only if must-haves land by Thursday):**
- Telegram alerts, stripped-down (hardcoded 3% threshold, no UI)

**Out of scope this sprint:**
Paper portfolio UI, P&L sparkline, threshold slider, HMAC auth, multi-channel alerts, sports markets, billing, accounts, rebrand, SEO, arbitrage UI, DraftKings.

**Success metric Sunday evening:** 10 invitees visit, 5 interact with at least one drawer, 2 reply with substantive feedback.

---

## Brand

"PredictionEdge" is effectively taken — [yourpredictionedge.com](https://yourpredictionedge.com) is an active direct competitor. The current deploy still renders "PredictionEdge" branding; this is acceptable for a private, invite-only beta but not for any public surface. Rebrand owner: Adi, before Phase 1 public launch. Default direction: revisit original "Prophet" name; audit domain + trademark availability.

---

## Strategic context — the five open questions

These are the load-bearing assumptions behind the pivot. Cross-reviewers (ChatGPT, Gemini) should pressure-test these, not the feature list.

1. Is the Prophet paper-trading stack actually differentiated, or will Oddpool / Your Prediction Edge clone it within two quarters?
2. Is $29/mo defensible when Your Prediction Edge Pro is $9.99 and Oddpool Pro is $30?
3. Is "active PM trader across both Kalshi and Polymarket" a real segment that can sustain 1–3K paying users, or a persona we're inventing?
4. Can cold-start paid SaaS acquire its first 100 users without an existing audience, given AI-Overview-degraded SEO and expensive paid ads in a regulated category?
5. Does the one-week private-beta slice produce a meaningful read on whether the wedge resonates, or do we need to go broader faster?

---

## Regulatory posture

- Kalshi Third Circuit ruling (April 6, 2026) positive for US regulated venue economics.
- CFTC rulemaking on sports event contracts due Q3 2026 — watch; drives the decision to keep sports out of the beta mapping.
- Polymarket ToS restricts US persons via UI and API. Do not market US-focused Polymarket execution to US users.
- The business must survive a scenario where sports event contracts are CFTC-restricted or state-blocked. The cross-category (non-sports) wedge is deliberate.

---

## Artifacts

- [REVISED_SCOPE.md](REVISED_SCOPE.md) — the post-pivot scope doc (for ChatGPT/Gemini review before big decisions)
- [SPRINT.md](SPRINT.md) — current week's day-by-day execution plan (private-beta target 2026-04-26)
- `prediction_market_platform_mockup.html` (user upload) — design reference (dark mode, JetBrains Mono + DM Sans, green/amber/cyan). Aesthetic survives the pivot; brand name does not.
- `prediction_market_onepager.pdf` (user upload) — original research thesis. **Superseded in parts:** the affiliate-CPA-first monetization claim and the "competitive gap" claim were contradicted by April 2026 research; treat the onepager as historical context, not current plan.
- Live deploy: https://web-production-9e0f9.up.railway.app/

---

## Technical stack (unchanged)

- Backend: Python 3.11+, FastAPI, async
- Frontend: Vite + React 19
- Data: SQLite (migrate to Postgres when user accounts land)
- Deploy: Railway
- Auth to Kalshi: RSA-PSS signing via `core/auth.py`
- Environment: `.env` for API keys, endpoints, `BETA_PASSWORD`, `TELEGRAM_BOT_TOKEN` (stretch)

---

## Open decisions (not resolved 2026-04-20)

1. **Rebrand timing:** rebrand before Phase 1 public launch (~8–12 weeks out), or during the beta if a strong name emerges.
2. **Phase 2 wedge:** once the beta validates signals + stakes, is the Phase 2 priority execution integration, backtesting UI, or intelligence/whale tracking? Reviewed by the 5 strategic questions above.
3. **Pricing:** $29/mo is a placeholder. Real pricing decision comes after beta feedback and a competitive pricing review against $9.99 (Your Prediction Edge) and $30 (Oddpool Pro).
