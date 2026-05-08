---
name: PROJECT_Prophet
description: "Odds Primer — educational oddschecker for prediction markets, World Cup 2026 MVP. Current architecture, deployment status, brand state, open decisions."
type: project
---

# Odds Primer — Project state

## Overview

**Goal.** An educational oddschecker for prediction markets. For each event we show prices side-by-side across Kalshi, Polymarket, and other venues, highlight the best one, and explain in plain English what the market means. MVP launches as a curated 2026 FIFA World Cup edition.

**Status.** Live deploy on Railway with educational-oddschecker scaffolding in place. Cross-platform comparison claim is currently structurally unbacked (single-source data). Design system locked. Logo system still in exploration. Beta target ~2026-05-09.

**Co-founder:** Faktor (since 2026-05-02). 25 years gaming, strategic alignment confirmed.

---

## Live deploy

**URL:** `https://web-production-9e0f9.up.railway.app/`
**Stack:** FastAPI backend + React frontend on Railway (single dyno, auto-deploy on git push).
**Endpoints:** `/api/stats`, `/api/platforms`, `/api/compare`.
**Data:** Polymarket-only as of the 2026-05-02 audit. Cross-platform marketing copy ("Kalshi + Polymarket + DraftKings") is not backed by the API yet.

---

## Pre-launch blockers (2026-05-02 audit)

| Blocker | Decision needed |
|---|---|
| `/api/compare` returns `source: "single"` on every market | Cut A (add Kalshi to back the claim) or Cut B (drop cross-platform framing for beta) |
| World Cup markets exist but buried under volume-sorted Bitcoin/Iran/NBA | Curated WC surface required |
| Educational content layer absent from API | Differentiator unbuilt; needs spec + content |
| Categories mostly "other," only two hand-mapped | WC tagging at minimum |
| Older endpoints from earlier project phases leak that history | Remove before showing outsiders |

---

## Brand & design system

**Direction.** Odds Primer — patient teacher, sports-desk editorial register, anti-gambling-promo. Position 60 on publication↔product axis. Closer to The Athletic / The Economist longform than Polymarket / DraftKings.

**Palette (locked 2026-05-02, refined since).**

- Cream paper `#FAF7F0` · navy ink `#0E2240` · dustier flame `#D9461C` (single accent) · graphite `#3A3F47` · warm rule `#D9D2C0`
- The earlier brighter `#FF5A1F` flame and pure white paper were dropped (read as alarm/casino). The reticle/scope motif is retired — replaced by probability bars as the system glyph.

**Type stack.**

- Source Serif 4 — display, headlines, prose (editorial register)
- Inter Tight — chrome, eyebrows, buttons, wordmark (the only place sans wins at display size)
- JetBrains Mono with `tabular-nums` — every price, percentage, timestamp
- Free Google-Fonts substitutes for the Anthropic stack (Söhne / Tiempos / Söhne Mono); upgrade path documented in `Odds Primer Design System/README.md`.

**Design system folder.** `Odds Primer Design System/` — locked. Components, tokens, voice rules, content rules, mockups. Source of truth: `README.md` + `colors_and_type.css`. Always load these before producing any UI.

**Standalone mockups (work from `file://`):**

- `Odds Primer Design System/mockups/home.html` — homepage / WC hub (markets-first layout)
- `Odds Primer Design System/mockups/home-mobile.html` — mobile-first homepage
- `Odds Primer Design System/mockups/market.html` — market detail / comparison view
- `Odds Primer Design System/mockups/learn.html` — Reading the numbers educational page

The earlier reference pages in `Odds Primer Design System/ui_kits/web/` (`index.html`, `tournament.html`, `match.html`) use Babel/JSX from CDN with relative imports and may render blank from `file://`. Use the standalone mockups instead, or serve via a local server.

---

## Logo system — open

The wordmark and bars-glyph are working drafts. The README flags this explicitly. Fresh exploration brief at `branding/odds_primer_logo_brief.md` asks for four directions (bars properly drawn, typographic-only nameplate, footnote-dagger glyph, quiet monogram), then full system on the chosen one (eight artifacts: primary, reverse, favicon at 3 sizes, app icon, edition lockup, social card, identity sheet, don't-do sheet).

---

## Brand naming — unresolved

Three names appear across artifacts and the live deploy metadata:

- **Odds Primer** — current working name; used throughout the design system
- **MarketTipsAI** — domain candidate
- **PredictionEdge** — appears in live page title and UTM source; collides with `yourpredictionedge.com` (commercial site)
- **Prophet** — internal/codebase legacy name; appears in OpenAPI title

Must collapse to one before launch.

---

## Strategic risks still active

- Google AI Overviews crater betting-affiliate SEO → defense is live-tool surface, not editorial content
- OddsJam can ship PM features fast (Gambling.com Group balance sheet)
- Affiliate economics softer than initial pitch (Polymarket 30% × 180d gated behind $10K traded volume; Kalshi pays $25 trading credits, not cash)
- Brand collision risk if "PredictionEdge" stays anywhere
- Perpetual futures launches at Kalshi + Polymarket are mutating the underlying product
- Kalshi sports-market regulatory standing remains unsettled

---

## Reversal flag (open question)

The 2026-04-20 plan explicitly excluded sports markets for regulatory (Kalshi sports legality) and competitive (OddsJam home turf) reasons. The 2026-05-02 World Cup MVP reverses that. Open question: are sports back in permanently, or just as a launch-event wedge for the WC then back out?

---

## Folder

`/Users/adi/Documents/Claude/Projects/prophet/` — single source of truth for code + Cowork artifacts. The earlier Google Drive mirror no longer exists. Memory is private and local: `./memory/SESSION_LOG_Prophet.md` and `./memory/PROJECT_Prophet.md` (this file). Never copy these to Google Drive.

---

Last updated: 2026-05-02
