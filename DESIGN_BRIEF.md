# Design Brief — MarketTipsAI (working name)

*Last updated: 2026-05-02*
*Brand name not yet locked. Working name "MarketTipsAI" used throughout — please treat as placeholder.*

---

## 1. The product in one paragraph

An educational oddschecker for prediction markets. For each event we show the prices side-by-side across Kalshi, Polymarket and other venues, highlight the best price, and explain in plain English what the market actually means. The MVP is a curated 2026 FIFA World Cup edition — one place for fans to compare odds across platforms and actually understand what they're looking at.

We're not a sportsbook. We're not a trading terminal. We're closer to "Wirecutter for prediction-market questions" — opinionated, educational, trustworthy.

## 2. Audience

Primary: a casual-to-engaged sports fan (specifically World Cup viewer) who is curious about prediction markets but doesn't know how they work or where to start. They're price-aware (used to checking odds), but new to the concept of YES/NO contracts, implied probability, and venue differences.

Secondary: existing prediction-market users who want a faster way to compare prices across Kalshi and Polymarket.

The design should feel approachable to the first audience without feeling dumbed-down to the second.

## 3. Brand direction

**Voice:** educational, neutral, confident without being cocky. Plain English. Explains the *why* behind a number, not just the number.

**Personality keywords:** clear, honest, calm, modern, slightly nerdy in a friendly way.

**Avoid at all costs:**
- Casino / sportsbook visual language (no neon greens, no spinning roulette, no flame icons, no "bet now")
- Trading-terminal density (no Bloomberg-style data walls, no green-on-black tickers)
- Crypto-bro aesthetic (no gradients, no laser eyes, no "moonshot")
- Generic SaaS marketing template (no abstract blob illustrations, no "trusted by" logo wall we don't have)

**Lean into:** editorial / publication aesthetic (think The Pudding, FiveThirtyEight, Stat Significant), with a light data-visualization sensibility.

## 4. Visual identity (open to evolve)

The previous prototype used dark mode with JetBrains Mono + DM Sans and green/amber/cyan accents. That can stay or be reset — we're open. If kept, soften the trader-terminal feel; if reset, lean editorial-light with a confident accent color.

**Decisions to make:**
- Light mode default vs dark mode default (recommend light for "educational" positioning, optional dark toggle)
- One accent color for "best price" highlight (recommend a color *not* used by Kalshi green or Polymarket purple to avoid confusion)
- Typography pair — one for UI/body, one for numbers (price displays look better in tabular figures or mono)

## 5. Screens to design (in priority order)

### 5.1 Homepage / World Cup hub
**Purpose:** First impression. Explain what the product is and surface the curated World Cup markets immediately.
**Above the fold needs:** product name, one-line value prop, last-updated timestamp, filter row (Winner / Group winners / Specials), first row of market cards.
**Each market card shows:** market question (plain English), best price + which venue, implied probability %, small "compare" affordance.

### 5.2 Market detail (the comparison view)
**Purpose:** The core repeated experience. Where someone lands when they tap a card. Where the educational positioning lives or dies.
**Must include:**
- Market question prominently
- Side-by-side odds table: each venue (Kalshi, Polymarket, …) with its YES price, NO price, implied probability, last updated. Best price highlighted.
- A 2–3 sentence plain-English explanation of what this market resolves to ("This pays out YES if Brazil wins all three group stage matches…")
- "How to read this" expandable: implied probability, what 0.65 means, fee context
- Affiliate clickout buttons to each venue (clear, not pushy)
- Resolution date / time-until-resolution

### 5.3 Learn page
**Purpose:** The educational differentiator. The page that proves the "educational" claim.
**Sections:** What is a prediction market · How to read odds · What "edge" means · Is this gambling? · Glossary.
**Format:** long-form editorial layout, generous whitespace, occasional small inline diagrams or examples. Not a wall of text.

### 5.4 Movers / live tracker
**Purpose:** The reason a beta user comes back tomorrow. Shows the biggest price changes in the last 24h / last hour.
**Must include:** market question, price now, price then, delta % (up or down), small sparkline if feasible.

### 5.5 About + trust
**Purpose:** Credibility. Who we are, how we source data, what we claim and don't claim.
**Must include:** founder bios (the operator + Faktor) with real photos, methodology summary, data refresh cadence, affiliate disclosure (we earn from clickouts — say so cleanly), full legal footer.

## 6. Cross-cutting design requirements

- **Mobile-first.** Match-time traffic will be 70%+ mobile. Design every screen for a 375–414px viewport first, then scale up. Desktop is a courtesy, not the canvas.
- **Empty states matter.** Every market card and the comparison table need explicit states for: data loading, only one venue has data (very common in MVP), market resolved/closed, no markets in selected filter.
- **No dark patterns.** No fake urgency timers, no "247 people viewing now," no sleazy clickout buttons.
- **Accessibility:** WCAG AA contrast minimums. Don't rely on color alone for "best price" — use a label or icon too.
- **OG / social card template** for shareable links — one match → one auto-generated card with the market question and the best price.

## 7. References to learn from

**Editorial / explanatory data:** The Pudding, FiveThirtyEight (pre-shutdown), Stat Significant.
**Clean financial information design:** Wise, Ramp, modern brokerage explainers.
**Prediction market comparators (competitors to study, not copy):** oddspedia, OddsJam's prediction surfaces, yourpredictionedge.com, Oddpool.

## 8. Out of scope for the beta design

- Account / sign-in / paywall flows
- Payments / subscription
- Personalized watchlists or notifications
- Multi-sport surfaces (only World Cup for MVP)
- Historical price charts beyond the small mover sparkline
- Admin / internal dashboards

## 9. Open decisions the design output should accommodate (not pre-empt)

- **Brand name:** MarketTipsAI vs PredictionEdge vs other still being decided. Keep wordmark/logo system flexible — design assuming a 2-word brand around 12–14 chars.
- **Cross-platform claim:** the live API currently has only Polymarket data. Design assuming the cross-platform comparison works (the product vision), but make the comparison table degrade gracefully when only one venue has prices for a given market.
- **Light vs dark mode:** open. If you produce both, light mode is the priority.

## 10. Deliverables wanted back

- 5 screen designs (mobile + desktop where applicable)
- A small component library / design tokens (color palette, type scale, spacing, button states, card states, empty/loading/error states)
- 1 OG / social card template
- 1 favicon + wordmark exploration

## 11. Timeline + success criteria

- Design needed in time for a private beta launch ~2026-05-09 (7 days from this brief)
- Success: a non-prediction-market user lands on a market detail page, understands what the market is asking and what the price means, and feels comfortable clicking through to a venue. Without explanation. Without a tooltip war.
