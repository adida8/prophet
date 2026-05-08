# Standing project context — MarketTipsAI

*Upload this as project knowledge / system context for the design tool. It applies to every screen, illustration, social card, OG image, button, and microcopy choice.*

## What the product is

An educational oddschecker for prediction markets. For each event, we show prices side-by-side across Kalshi, Polymarket and other venues, highlight the best price, and explain in plain English what the market actually means. The MVP is a curated 2026 FIFA World Cup edition.

We are NOT a sportsbook. We are NOT a trading terminal. We are closer to a "Wirecutter for prediction-market questions" — opinionated, educational, trustworthy.

## Audience

A casual-to-engaged World Cup viewer who is curious about prediction markets but doesn't know how they work. Price-aware (used to checking odds), new to YES/NO contracts and implied probability. The design has to feel approachable to them without feeling dumbed-down to existing prediction-market users.

## Brand personality

Clear, honest, calm, modern, slightly nerdy in a friendly way. Think "the smart friend who explains things at the bar," not "the Wall Street trader" and not "the casino host."

**Voice in microcopy:** plain English, neutral, confident without being cocky. Explains the *why* behind a number, not just the number.

**On-brand microcopy examples:**
- "Brazil is currently priced at a 19% chance to win the World Cup."
- "Best YES price: PredictIt"
- "What 'implied probability' means →"
- "This market resolves on July 19, 2026."
- "Updated 2 minutes ago."

**Off-brand microcopy — never use:**
- "🔥 Hot pick: Brazil!"
- "BET NOW — limited time"
- "Lock in your edge"
- "247 traders viewing this market"
- "Don't miss out"

## Visual direction

- **Mode:** Light mode default. Dark mode is secondary, optional.
- **Density:** Editorial. Generous whitespace. Not Bloomberg, not Robinhood.
- **Typography:** One sans for UI/body, one mono or tabular-figure family for numbers. Numbers must not shift width as they update.
- **Best-price highlight:** A single accent color (recommend deep teal `#0F766E` or amber `#D97706` — must avoid Kalshi green and Polymarket purple to prevent venue-color confusion). Subtle background tint + a "Best" label. Never a flashing or pulsing element.
- **Buttons:** Rounded corners but not pill-shaped. Confident, not aggressive. Primary = solid accent. Secondary = outlined.
- **Imagery:** Avoid stock photos of people cheering or money raining. If illustration is needed, use simple geometric or editorial line art.

## Anti-patterns — never produce these

- Sportsbook visual language: neon, animated gradients, flame/lightning icons, "BET NOW" CTAs
- Trader terminal density: green-on-black tickers, multi-column data walls
- Crypto-bro aesthetic: gradient logos, hype copy, laser eyes, "to the moon"
- Generic SaaS template: abstract blob illustrations, "trusted by" logo walls we don't have, hero illustrations of businesspeople pointing at upward charts
- Dark patterns: fake urgency timers, fake "X people viewing now," manipulative clickout buttons, scarcity copy

## Recurring components (use consistently across all screens)

- **Market card** — appears on homepage and list views. Shows: market question (truncated to 2 lines), best price + venue + implied probability %, small "compare" affordance. Tappable. Light card, subtle border or shadow, generous internal padding.
- **Comparison table** — the heart of the product. Each row = one venue. Columns: venue name, YES, NO, implied probability, last-updated, clickout button. Best YES and best NO get a subtle accent background + "Best" label. On mobile (<600px), restructures into a stack of venue cards instead of a horizontal-scrolling table.
- **Educational blurb** — 2–3 sentence plain-English explanation. Sits below the comparison table. Slightly muted background to separate from data, but readable body typography (not small print).
- **"How to read this" expandable** — small toggle revealing an inline glossary. Default collapsed.
- **Affiliate clickout button** — labeled "Trade on [Venue]" with the venue's color as a subtle accent only. Not flashy. Always paired with affiliate disclosure in the footer.
- **Last-updated stamp** — small, low-contrast, lives near every price.

## Page chrome (consistent across all screens)

- **Header:** minimal — wordmark on the left, two nav items ("Learn" and "About") on the right. No login button. No search for MVP.
- **Footer:** affiliate disclosure, "Not financial advice," age and jurisdiction disclaimer, links to Terms / Privacy / About.

## Reference vibes (study these, in priority order)

1. The Pudding — data-driven editorial, calm, illustrative
2. FiveThirtyEight — data tables done well, neutral tone
3. Stat Significant — long-form data writing on Substack, light mode, generous type
4. Wise, Ramp — clean financial-information design without crypto vibes

## Out-of-vibe references (do not pull from)

DraftKings. FanDuel. Stake. Coinbase. Robinhood. Bloomberg Terminal. Any sportsbook landing page. Any "intro to crypto" landing page.

## What's out of scope (do not design)

Accounts, login, signup, paywalls, payments, multi-sport tabs, notifications, personalized watchlists, historical price charts beyond a small mover sparkline, onboarding tours, complex filters, search.
