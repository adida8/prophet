# PredictionEdge (working name) — Revised Scope

**Status:** Post-research pivot. Preserving the Prophet codebase, reframing positioning, resequencing monetization. For review before sprint planning.

**Why this revision exists:** Competitor research (Oddpool, Your Prediction Edge, FORS, Prediction Market Tools, FinFeedAPI, PolyRouter, Gambling.com Group post-OddsJam, VegasInsider) confirmed the original "OddsChecker for prediction markets" wedge is commoditized. Two independent AI reviews (Claude, ChatGPT) converged on the same recommendation: pivot from comparison/affiliate to workflow/decision-support. This scope operationalizes that pivot around the one asset we already own and no competitor has — the Prophet paper-trading + risk-management stack.

---

## Positioning (one line)

**A decision-support workspace for serious prediction-market traders — matched-market intelligence, paper trading, and risk-sized strategy execution across Kalshi and Polymarket.**

- Not: an odds aggregator, a Bloomberg terminal for PMs, a sports-betting affiliate site.
- Closer to: TradingView meets backtest.py for event markets, with live execution integrations in later phases.

## Target user

Narrow. Active prediction-market traders who:

- Trade across both Kalshi and Polymarket weekly
- Manage positions by hand or in spreadsheets today
- Would pay for faster, higher-conviction decision-making — strategy testing, risk sizing, matched-market alerts — not prettier dashboards

Approximate segment size: low thousands today. Polymarket reports ~700K MAU; even 1% "serious" is a 7K addressable ceiling, growing with the market. Realistic Year-1 target: 1–3K paid users.

## The wedge

The Prophet codebase already includes `strategies/`, `risk_manager.py`, Kelly sizing, a paper-trading runner, working Kalshi RSA auth, and a Polymarket client. Oddpool (data/API), Your Prediction Edge (consumer comparison), FORS (Solana copy-trading), and media incumbents (Gambling.com / VegasInsider) do not own this. Productizing it is the wedge.

Specifically, Phase 1 builds five interlocking surfaces:

1. **Matched-market engine** — Kalshi + Polymarket pairs with human-readable titles and YES/NO polarity resolved.
2. **Strategy runner** — run a Prophet strategy against live matched-market data in paper mode.
3. **Risk-sized suggestions** — user sets bankroll + risk tolerance; we suggest position sizes via Kelly / fractional Kelly / fixed fraction.
4. **Alerts** — dislocations, price crosses, strategy triggers, delivered via Telegram / Discord / email.
5. **Position tracker + trade journal** — paper portfolio first; live-linked Phase 2.

Comparison is a supporting feature inside the workflow, not the product.

## What's in Phase 1

**Free tier (habit-forming):**
- Matched-market engine, 30–50 curated pairs
- Live prices from Kalshi + Polymarket, auto-refresh
- Watchlist (up to 10 markets)
- 7-day price history
- One strategy template, paper mode only
- Public event pages indexable by search

**Paid tier ($29/mo target; revisit on data):**
- Unlimited watchlists
- Custom alerts (price, dislocation, strategy trigger) via Telegram / Discord / email
- Multi-strategy paper portfolio with Kelly / risk sizing
- 90-day price history
- Backtest against 30-day historical matched-market data
- Weekly intelligence digest (movers, dislocations, high-conviction matched markets)

## What's out of Phase 1

- Live trade execution (future phase; needs exchange API partnership + regulatory sign-off)
- DraftKings / FanDuel / sportsbook columns
- Copy trading
- Whale tracking / on-chain intel (Oddpool / Polymarket Analytics lane; revisit only if a distinct angle emerges)
- Generic arbitrage scanner (fee-adjusted math risk + head-on Oddpool Pro collision)
- Native mobile app (web responsive only)
- B2B API / data licensing (Phase 3)
- Display ads / programmatic SEO pages (Phase 3)

## Monetization sequencing (revised)

- **Months 1–3:** Paid subscription only. No affiliate revenue. Expect zero revenue for ~30 days after launch.
- **Months 4–6:** Affiliate routing added where Kalshi/Polymarket programs allow. Garnish, not engine — Polymarket pays 30% revshare × 180d after a $10K volume gate, Kalshi pays credits.
- **Months 6–12:** SEO event pages + programmatic content; B2B API for media partners; explore data licensing.

The original CPA-first thesis is retired. Affiliate becomes a bonus stream on top of subscription, not the foundation.

## Brand / naming

"PredictionEdge" is effectively taken (yourpredictionedge.com ships a direct competitor product). Rebrand required before any public launch. Default direction: revisit the original Prophet name; audit domain + trademark availability. Decision owner: the operator, before Phase 1 public launch.

## Regulatory posture

- Kalshi Third Circuit ruling (April 6, 2026) positive for US regulated venue economics.
- CFTC rulemaking on sports event contracts due Q3 2026 — watch closely.
- Polymarket ToS restricts US persons via UI and API. Do not market US-focused Polymarket execution features to US users.
- The business must survive a scenario where sports event contracts are CFTC-restricted or state-blocked. This is why Phase 1 is cross-category strategy tooling, not sports-first.

## Assets we start with

- Live deploy at https://web-production-9e0f9.up.railway.app/
- FastAPI backend, Vite/React 19 frontend
- Working Kalshi RSA auth
- Polymarket client pulling real prices + volume
- `strategies/`, `risk_manager.py`, Kelly sizing infrastructure
- ~500 markets in current feed (matching broken; needs rebuild)

## Assets we need to build

- Market matching engine (hand-curated pairs file + normalizer)
- Paper-trading loop wired to live matched-market prices
- Alert delivery pipeline (Telegram, Discord, email)
- User accounts + billing (Stripe)
- Backtest harness over historical Kalshi + Polymarket snapshots
- Event pages for SEO
- New brand + domain

## Realistic score ceiling

Original scope scored 44/100 on the earlier GO/NO-GO rubric (NO-GO). This revised scope's realistic ceiling is **62–70** (GO-WITH-CHANGES). The pivot improves differentiation, premium defensibility, and platform independence. It does not meaningfully change market size, competitive whitespace (Oddpool persists in the adjacent data/API lane), incumbent risk (Gambling.com armed post-OddsJam), or regulatory overhang.

A 90/100 requires either category dominance in a faster-growing market or an unusual distribution advantage — neither is on the table today. Do not scope to a 90 ceiling that cannot be delivered.

## Open questions for review

1. Is the Prophet paper-trading stack actually differentiated, or will Oddpool / Your Prediction Edge clone it within two quarters?
2. Is $29/mo defensible when Your Prediction Edge Pro is $9.99 and Oddpool Pro is $30?
3. Is "active PM trader across both Kalshi and Polymarket" a real segment that can sustain 1–3K paying users, or a persona we're inventing?
4. Can cold-start paid SaaS acquire its first 100 users without an existing audience, given AI-Overview-degraded SEO and expensive paid ads in a regulated category?
5. Does this scope invalidate the April 26 soft-launch date, or is there a thin slice (matched-market engine + watchlist + basic alert, gated as private beta) worth shipping anyway?

## Timeline

Phase 1 MVP as written is a **8–12 week build**, not a 1-week sprint. If April 26 matters for other reasons (discipline, audience, accountability), ship a thin private-beta slice on that date — matched-market engine + watchlist + one alert channel — and treat paid tier + rebrand + full feature set as the real launch 8–12 weeks later.

## Success criteria

- **90-day:** 20 paying users, 70%+ week-4 retention on free tier, sub-5% weekly churn on paid.
- **180-day:** 200 paying users at $29 = $5.8K MRR. Validate path to 1K+.
- **12-month:** 1K paid, $29K MRR, Phase 2 affiliate layer live, rebrand complete, measured SEO traction on event pages.

---

## What this document is and isn't

This is a **scope proposal for review**, not a sprint plan. Sprint planning comes after cross-validation with ChatGPT and Gemini. Reviewers should push back on the wedge definition, the target-user sizing, the pricing assumption, and the timeline — those are the load-bearing assumptions most likely to be wrong.
