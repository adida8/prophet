# Prompt for ChatGPT — review WC edition design + UX

Copy everything below the line and paste into ChatGPT. Attach the four files in this folder:

- `odds_primer_logo.png` — locked logo, for visual reference (don't redesign)
- `../mockups/wc-hub-hero.html` — homepage / WC hub
- `../mockups/wc-og-card.html` — three 1200×630 social cards
- `../mockups/wc-match-dossier.html` — in-article match brief module

ChatGPT can read the HTML source directly.

---

You reviewed our strategic framing in the last round and it landed: **Odds Primer is the masthead; World Cup 2026 is the issue.** Cover treatment, not logo modification. We then built three working prototypes that put the framing into practice.

I need a sharp execution-level review of design and UX. Not strategy — that's settled.

## Who we are (recap)

**Odds Primer** is an educational oddschecker for prediction markets and US sportsbooks. Patient teacher, sports-desk editorial register. Anti-gambling-promo. Position 60 on a publication↔product axis (leans product, reads editorial). Launch surface: 2026 FIFA World Cup edition.

## What's locked (don't redesign)

- **Logo:** Source Serif 4 800 wordmark + bare 4-bar glyph (heights 22·38·65·30, flame on 3rd). See attached PNG.
- **Palette:** cream `#FAF7F0`, warm paper `#F2EDE0`, navy `#0E2240`, ink-soft / graphite neutrals, rule `#D9D2BE`, flame `#D9461C`. Single accent.
- **Edition labeling rule:** "World Cup 2026" in navy weight 700, secondary copy in soft ink-soft / graphite. Never the whole label in flame.
- **Venue dot rule:** solid navy = prediction market (Kalshi, Polymarket); outlined navy = sportsbook (DraftKings, FanDuel, BetMGM, Caesars). No third-party brand colors.
- **Best-price copy:** "Lowest listed" = cheapest visible price. "Best net price" = best after fees and venue spread. Never "Cheapest" / "Best after fees."
- **Flame discipline:** one dominant flame moment per module — best-price underline + small `Best` tag is canonical. Body-text emphasis is mono `tnum`, not flame.
- **Anti-patterns:** no trophy, no FIFA "26" treatment, no host-country flag colors, no soccer-ball / pitch / badge / crest decoration, no "WC Edition" baked into the logo, no green for "best," no sportsbook-ticker live states, no CTAs like "lock in" / "cash."

## What I built — three surfaces

1. **`wc-hub-hero.html`** — the homepage. After several iterations of failed magazine-cover compositions, I rebuilt this as a **stack of dossiers**: lead dossier (full module, FRA v ARG match brief) followed by four compact dossiers (France outright, Mexico v RSA opening match, Spain Group F, Mbappé Golden Boot). The masthead and edition strip do the brand work; the dossiers are the issue.

2. **`wc-og-card.html`** — three 1200×630 social cards, each containing a single dossier with a small masthead row above. Same module, sized for social. No big serif cover headline.

3. **`wc-match-dossier.html`** — the in-article match brief module embedded in a longform article. Full + compact variants.

## What I want from you

Be opinionated. Be willing to disagree.

1. **Information hierarchy.** In each surface, what reads first / second / third on first glance? Is the order I want (question → best price → spread → notes) the order the eye actually takes? If not, what's pulling focus?

2. **The dossier as the universal unit.** I'm betting the same module can carry the homepage, the OG card, and an in-article callout. Is that right? Where does it strain — is there a surface where the dossier is the wrong tool?

3. **Density.** Each dossier shows 4–6 venues. Is that the right number? Too many → busy and hard to compare. Too few → trivial. What would you cut or add?

4. **Voice in the notes column.** Each row has a small italic note ("Slowest line to move on Mbappé news," "Standard book hold"). Are these notes earning their space, or are they padding? Are they the right register?

5. **Mobile.** These are designed desktop-first. Where does each surface break at 375–414px width? What needs special handling?

6. **The "Odds Primer Editorial" byline** in the match dossier — does it earn the space, or does it feel like a placeholder?

7. **OG card legibility at thumbnail.** Social previews render at maybe 240px wide in a feed. Does the dossier-as-card hold up that small, or do we need a larger-typography variant for thumbnail-first contexts?

8. **What's missing.** Anything obvious we're not building yet (push notifications? email digest header? In-page module for a WC results page?). Don't list everything — list the **one** missing piece you'd build next.

## Reply format

- 500–800 words total. Tight, opinionated.
- Lead with your single sharpest critique, not a recap of the brief.
- For each issue: name the file, name the section or selector, name what to change. *"In `wc-hub-hero.html`, the lead dossier's d-question line is fighting the d-match for first read — drop the question to italic graphite or move it above d-match"* beats *"the hierarchy could be clearer."*
- If the framing or execution is fundamentally right and only needs polish, say so plainly. Don't manufacture problems.
