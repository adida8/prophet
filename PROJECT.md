# Prophet → [brand TBD] — Project Snapshot

**Last updated:** 2026-04-23 (post-OddsJam re-read)
**Status:** Pre-beta. Scaffolding deployed. Pivoted from public-launch aggregator to decision-support workspace. Working name "PredictionEdge" retired. Private-beta target 2026-04-26. Pivot ceiling revised down after OddsJam re-read.

**Two tracks running in parallel** — this doc covers Track A only:
- **Track A (this doc):** Consumer decision-support workspace, $29/mo, private beta 2026-04-26.
- **Track B (separate doc):** B2B market-making infrastructure, 30-day market test ending ~2026-05-22. Unchanged by this snapshot. Reconciliation between the two tracks is an open decision.

---

## What Track A is (post-pivot)

Prophet-MVP-v1 started as a Python/React paper-trading bot for Kalshi demo. The original April pivot — into a public OddsChecker-for-prediction-markets affiliate site — was abandoned after competitor research scored it 44/100 (NO-GO). The current plan productizes the Prophet paper-trading + risk-management stack as a decision-support layer on top of Kalshi and Polymarket. The codebase and deploy are preserved; the product thesis changed.

Positioning, one line: **A decision-support workspace for serious prediction-market traders — matched-market intelligence, Prophet-strategy signals, and Kelly-sized stakes across Kalshi and Polymarket.**

Not: an odds aggregator, a Bloomberg terminal clone, a sports-betting affiliate site.
Closer to: TradingView meets backtest.py for event markets.

---

## Why the pivot (research findings, April 2026)

Cross-validated research (web + Claude review + ChatGPT review) produced a GO/NO-GO score of **44/100 on the original aggregator scope (NO-GO)**. The pivot to decision-support was initially scoped at a 62–70 ceiling. That ceiling has been **revised down to 55–62** after a deeper read on OddsJam.

Key findings:

- Market size is real. Kalshi $12–13B/mo + Polymarket $10.5B/mo (March 2026). Bernstein backs $1T/2030 at ~80% CAGR.
- Competitive whitespace is gone. [yourpredictionedge.com](https://yourpredictionedge.com) ships a near-identical product at $9.99/mo (direct name collision); Oddpool ($30 Pro, $100 Premium), FORS (Solana), Prediction Market Tools, FinFeedAPI, PolyRouter are live. VegasInsider and Gambling.com Group already publish PM comparison content.
- Affiliate economics are softer than the onepager claimed. Polymarket pays 30% revshare × 180d behind a $10K traded-volume gate; Kalshi pays $25 in trading credits, not cash.
- AI Overviews cratered betting-affiliate SEO. 96% of betting-affiliate sites hit; CTR 15%→8%.
- Regulatory posture is net positive but has overhang. Third Circuit ruled 2–1 for Kalshi (April 6, 2026), CEA preempts state gambling law. CFTC rulemaking due Q3 2026; SCOTUS review possible; Washington state challenge active.

## OddsJam re-read (added 2026-04-23)

OddsJam — acquired by Gambling.com Group for up to $160M in Jan 2025 — is more of a direct tools competitor than earlier reads treated it. Specifically:

- **[oddsjam.com/prediction/traders](https://oddsjam.com/prediction/traders)** and **[/prediction/insiders](https://oddsjam.com/prediction/insiders)** — dedicated Kalshi + Polymarket surfaces with "unlimited pre-match and live recommendations from algorithmically-selected traders, optimal bet sizing, and deep links directly to Polymarket & Kalshi."
- **[Kelly Criterion calculator](https://oddsjam.com/betting-calculators/kelly-criterion)** and **[EV calculator](https://oddsjam.com/betting-calculators/expected-value)** shipped as standalone tools.
- **Push notifications for +EV opportunities** on the Platinum plan. The alert layer we planned for Phase 1–2 is already shipped on their sports side.
- **[Prediction-market-to-betting-odds converter](https://oddsjam.com/betting-calculators/prediction-market-converter)** — PM prices are already a first-class odds type in their data layer.
- Pricing: Plus $39/mo, Gold $199.99/mo, Global $399.99/mo. Different monetization class than a $29/mo prosumer tool, but proves ceiling for serious tools.

**Impact on the pivot:** Differentiation and incumbent-risk rubric lines both drop. OddsJam effectively has the Prophet pivot wedge (Kelly + EV + matched markets + alerts) already shipped — just sports-first. One seam remains: OddsJam's "EV" in PMs is definitionally weaker than in sports (no Pinnacle-equivalent no-vig line for PMs), so their PM surface is really dislocation + trader-copy, not strategy-driven decision support. That's narrow, but it's the seam the Prophet stack can still claim.

## Perpetual futures development (added 2026-04-23)

Both Kalshi and Polymarket are launching perpetual futures products. Polymarket is in early-access sign-ups for perps with 10x leverage on gold, stocks (NVDA, COIN), BTC. Kalshi is following. This expands the market scope but also means the workflow tooling being built is aimed at a product surface that is mutating. Perps need different risk management (funding rates, leverage, liquidation) than binary YES/NO. Existing Prophet strategies may or may not transfer cleanly. Known before committing beyond the beta.

---

## The wedge

The Prophet codebase already includes `strategies/`, `risk_manager.py`, Kelly sizing, a paper-trading runner, Kalshi RSA auth, and a Polymarket client. Productizing this stack as signals + Kelly-sized stakes is the wedge.

Five interlocking surfaces in Phase 1:
1. Matched-market engine (Kalshi ↔ Polymarket with polarity resolved)
2. Strategy runner (paper mode, live matched-market data)
3. Risk-sized suggestions (Kelly / fractional Kelly)
4. Alerts (Telegram in beta; Discord/email later)
5. Position tracker + trade journal (paper first, live-linked later)

Comparison is a supporting feature inside the workflow, not the product.

**Post-OddsJam re-read, the narrower wedge is:** Prophet's backtested paper-trading framework and strategy-driven signals for **non-sports** PM categories. Sports is out both for regulatory overhang and because it's OddsJam's home turf.

---

## Monetization stack (resequenced)

The CPA-first thesis is retired.

- **Months 1–3:** Paid subscription only ($29/mo target; revisit on data). No affiliate revenue.
- **Months 4–6:** Affiliate routing as garnish where programs allow.
- **Months 6–12:** SEO event pages, programmatic content, B2B API, data licensing.

$29 sits between Your Prediction Edge ($9.99) and OddsJam Plus ($39). The price only holds if the product is narrower and better for PM-native workflow than either.

---

## Current build state (2026-04-23)

**Live deploy:** https://web-production-9e0f9.up.railway.app/

Working:
- FastAPI backend + Vite/React 19 frontend on Railway
- Polymarket client pulling real prices, volume, URLs
- Kalshi RSA-PSS auth (`core/auth.py`)
- ~500 markets in feed

Broken/missing (sprint addresses):
- Kalshi pricing returns 0.0 (wrong field — should read `yes_bid`/`yes_ask`)
- Categories all `"other"`
- Titles are raw ticker strings
- Expired markets in feed
- Zero matched markets (engine is a stub)
- Per-market URLs lack UTM params
- No signal engine; Prophet strategies not wired to a live product surface
- No alert mechanism
- No beta gate

---

## Private beta MVP (2026-04-26)

Trimmed 7-day sprint to a private-beta URL, invite-only, shared-password gated. Day-by-day in [SPRINT.md](SPRINT.md). Per-task Claude Code prompts in [CLAUDE_CODE_TASKS.md](CLAUDE_CODE_TASKS.md).

**Must-have:**
1. 10–12 hand-verified matched pairs (politics / macro / crypto; no sports)
2. Live prices from both venues, polarity resolved, dislocation computed
3. One Prophet signal per market — action, edge %, Kelly-sized stake, rationale. `hold` is a valid outcome.
4. `MatchedMarketsTable` rendering the above
5. Detail drawer on row click (no sparkline, no P&L)
6. Watchlist (localStorage)
7. Simple password gate

**Stretch (only if must-haves land by Thursday):** stripped-down Telegram alerts, hardcoded 3% threshold.

**Out of scope this sprint:** Paper portfolio UI, P&L sparkline, threshold slider, HMAC auth, multi-channel alerts, sports markets, billing, accounts, rebrand, SEO, arbitrage UI, DraftKings.

**Success metric Sunday:** 10 invitees visit, 5 interact with a drawer, 2 reply with substantive feedback.

---

## Brand

"PredictionEdge" is effectively taken — [yourpredictionedge.com](https://yourpredictionedge.com) is an active direct competitor. Current deploy still renders "PredictionEdge"; acceptable for a private, invite-only beta, not for any public surface. Rebrand owner: Adi, before Phase 1 public launch. Default: revisit original "Prophet"; audit domain + trademark.

---

## Strategic context — six load-bearing questions

One added post-OddsJam re-read.

1. Is the Prophet paper-trading stack actually differentiated, or will Oddpool / Your Prediction Edge / OddsJam clone it within two quarters?
2. Is $29/mo defensible when Your Prediction Edge Pro is $9.99, Oddpool Pro is $30, and OddsJam Plus is $39?
3. Is "active PM trader across both Kalshi and Polymarket" a real segment that can sustain 1–3K paying users, or a persona we're inventing?
4. Can cold-start paid SaaS acquire its first 100 users without an existing audience, given AI-Overview-degraded SEO and expensive paid ads in a regulated category?
5. Does the one-week private-beta slice produce a meaningful read on whether the wedge resonates?
6. **New (post-OddsJam):** Is there a wedge structurally out of reach for OddsJam — something their sports-bettor audience, product DNA, and team composition would never ship — that Prophet's strategy stack can own? Current best answer: backtested strategy-driven signals on non-sports PM categories. If that doesn't hold up in beta feedback, margin for error is very small.

---

## Regulatory posture

- Kalshi Third Circuit ruling (April 6, 2026) positive for US regulated venue economics.
- CFTC rulemaking on sports event contracts due Q3 2026 — watch; drives sports exclusion from beta mapping.
- Polymarket ToS restricts US persons via UI and API. Do not market US-focused Polymarket execution to US users.
- Business must survive sports event contracts being CFTC-restricted or state-blocked. The cross-category (non-sports) wedge is deliberate.

---

## Artifacts (in this folder unless noted)

- [REVISED_SCOPE.md](REVISED_SCOPE.md) — post-pivot scope doc (for Gemini/ChatGPT review before big decisions)
- [SPRINT.md](SPRINT.md) — current week's day-by-day execution plan
- [CLAUDE_CODE_TASKS.md](CLAUDE_CODE_TASKS.md) — per-task prompts to feed Claude Code, one at a time
- `prediction_market_platform_mockup.html` (user upload) — design reference. Aesthetic survives the pivot; brand name does not.
- `prediction_market_onepager.pdf` (user upload) — original research thesis. **Partially superseded:** affiliate-CPA-first monetization and "competitive gap" claims were contradicted by April 2026 research. Treat as historical context.
- Live deploy: https://web-production-9e0f9.up.railway.app/
- Session log (across sessions, both tracks): `~/Google Drive/My Drive/Claude/memory/SESSION_LOG_Prophet.md`

---

## Technical stack (unchanged)

- Backend: Python 3.11+, FastAPI, async
- Frontend: Vite + React 19
- Data: SQLite (migrate to Postgres when accounts land)
- Deploy: Railway
- Kalshi auth: RSA-PSS via `core/auth.py`
- `.env` holds API keys, endpoints, `BETA_PASSWORD`, `TELEGRAM_BOT_TOKEN` (stretch)

---

## Open decisions

1. **Track reconciliation (URGENT, carried forward from previous session).** Track A private beta 2026-04-26 vs Track B 30-day test ending ~2026-05-22. Decide: run both in parallel, delay A for B, or kill one.
2. **Rebrand timing:** before Phase 1 public launch (~8–12 weeks out), or during the beta if a strong name emerges.
3. **Phase 2 wedge:** after the beta, is the priority execution integration, backtesting UI, or intelligence/whale tracking?
4. **Pricing:** $29/mo is a placeholder; real decision after beta feedback.
5. **Perpetual futures exposure:** scope Phase 2 to include perps support on Kalshi/Polymarket, or stay binary-YES/NO-only until the perps market shakes out?
