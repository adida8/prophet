# MarketTipsAI — Beta Launch Brief

*Last updated: 2026-05-02 · Owners: Adi + Faktor*

## MVP scope

> An educational oddschecker for prediction markets: for each event we show the prices side-by-side across Kalshi, Polymarket and other venues, highlight the best one, and explain in plain English what the market means. The MVP launches as a curated 2026 World Cup edition — one place for fans to compare odds across platforms and actually understand what they're looking at.

**Beta target:** ~2026-05-09 (7 days)
**Launch event:** 2026 FIFA World Cup (~6 weeks)
**Live deploy today:** https://web-production-9e0f9.up.railway.app/

---

## Three blocking decisions (lock in next 24h)

- [ ] **Name + domain** — MarketTipsAI vs PredictionEdge vs other. Confirm domain ownership / DNS plan.
- [ ] **Cross-platform claim** — *Cut A:* ship Kalshi ingestion so the comparison view actually compares. *Cut B:* drop "cross-platform" from copy, position as smart Polymarket lens for beta and add the second venue post-launch.
- [ ] **Mobile-first vs desktop-first** for mockups. Recommendation: mobile-first — match-time traffic is phones.

---

## Branding

- [ ] Lock product name
- [ ] Confirm domain (purchase if not owned)
- [ ] Wordmark / logo (type-only is fine for beta)
- [ ] Color palette + favicon
- [ ] 1–2 brand typefaces
- [ ] Tagline / hero line
- [ ] Brand voice rules: educational, neutral, not casino-y, not finance-jargon-heavy

## Design

- [ ] Mockup — Homepage / World Cup hub
- [ ] Mockup — Market detail (comparison view)
- [ ] Mockup — Learn / education page
- [ ] Mockup — Movers / live tracker
- [ ] Mockup — About + trust
- [ ] Mobile layouts for screens 1, 2, 4
- [ ] Empty / loading / error states for the comparison view
- [ ] Trust visual language — clean, neutral, distinctly NOT sportsbook
- [ ] OG image template for shareable links (one match → one social card)

## Product / content

- [ ] Hand-curate 15–20 World Cup markets for the MVP
- [ ] Write a 2–3 sentence educational blurb for each curated market
- [ ] Learn page — "What is a prediction market"
- [ ] Learn page — "How to read odds (probability vs implied price)"
- [ ] Learn page — "What 'edge' means"
- [ ] Learn page — "Is this gambling?" (responsible-use framing)
- [ ] Learn page — glossary
- [ ] About page — bios for Adi + Faktor
- [ ] About page — methodology + data refresh cadence
- [ ] Beta welcome / onboarding copy + feedback prompt
- [ ] Legal — Terms of Service
- [ ] Legal — Privacy Policy
- [ ] Legal — Affiliate disclosure (FTC requires)
- [ ] Legal — Not-financial-advice + age + jurisdiction disclaimer

## Dev / engineering

- [ ] **Decision: Cut A or Cut B** (see blockers above) — drives the rest of dev
- [ ] Tag World Cup markets in data layer (`category: "world_cup"`)
- [ ] Add `educational_blurb` field to market schema and surface in `/api/compare`
- [ ] Build curated WC surface (filtered + ordered, not volume-sorted)
- [ ] Build market detail page route + view
- [ ] Build Learn page route + view
- [ ] Build About page route + view
- [ ] Hide trading-bot endpoints from public surface (`/api/positions`, `/api/orders`, `/api/kill`, `/api/balance/live`)
- [ ] Rebrand sweep — page title, OpenAPI title, UTM source, favicon, meta tags
- [ ] DNS + HTTPS for chosen domain
- [ ] Mobile responsiveness audit + fixes
- [ ] 404 page
- [ ] OG meta tags for shareable links
- [ ] robots.txt + sitemap.xml
- [ ] *(If Cut A)* Kalshi ingestion + RSA auth port from existing Prophet code
- [ ] *(If Cut A)* Hand-built market-ID mapping table for the 15–20 curated WC pairs

## Analytics + feedback

- [ ] Define beta success metrics (e.g. X visitors → Y detail views → Z clickouts → ≥2 substantive feedback notes)
- [ ] Install Plausible or GA4
- [ ] Event tracking — market detail open, Learn page scroll, venue clickout
- [ ] Feedback channel — Tally embed or mailto in footer
- [ ] Shared sheet for signups + feedback notes

## Launch / marketing / ops

- [ ] Beta tester list — who, how many, which channels
- [ ] Invite copy — Twitter DM / email / WhatsApp template
- [ ] Faktor's role + credit visible on About page
- [ ] Launch announcement plan (LinkedIn, X, communities)
- [ ] 48-hour post-launch monitoring plan — who watches what, fix-vs-ignore criteria

---

## Out of scope for beta (parking lot)

- Accounts / login / payments
- More than one sport
- Notifications / alerts
- Personalized watchlists
- Historical price charts
- Backtested signals (the original Prophet feature — punt)
- B2B / market-maker infrastructure (Track B)
