---
name: odds-primer-design
description: Use this skill to generate well-branded interfaces, pages, and assets for Odds Primer — an educational oddschecker for prediction markets. Patient-teacher voice, sports-desk editorial register. Works for production code, prototypes, mocks, slides.
user-invocable: true
---

# Odds Primer — design skill

## What Odds Primer is

An educational oddschecker for prediction markets. We compare prices for the same event across Kalshi, Polymarket, and US sportsbooks, highlight the best one, and explain in plain English what the numbers mean. Patient teacher, not tipster. Anti-gambling-promo. Closer to a quality football quarterly than a sportsbook UI.

Launch surface: a curated 2026 FIFA World Cup edition.

## Read these first

1. `README.md` — voice, content rules, visual foundations, iconography, full file index. **Source of truth.**
2. `colors_and_type.css` — every color, type, spacing, radius, shadow, motion token. Load this on every page.
3. `preview/*.html` — visual reference for every token and component, viewable as cards.
4. `ui_kits/web/` — JSX components and three reference pages: `index.html` (event explainer), `tournament.html` (Vol. 1 contents), `match.html` (match-day comparison).
5. `branding/` — locked logo SVGs (`locked/`), full PNG asset set (`assets/`), exploration trail and ChatGPT prompts. Start at `branding/README.md`.

## How to start a new page

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="../../colors_and_type.css">
</head>
<body>
  <div id="root"></div>
  <!-- React + Babel pinned versions, see ui_kits/web/index.html -->
  <script type="text/babel" src="Wordmark.jsx"></script>
  <script type="text/babel" src="Masthead.jsx"></script>
  <!-- Other components as needed -->
  <script type="text/babel">
    /* Build the page here. Use CSS variables only — never hardcode hex. */
  </script>
</body>
</html>
```

The simplest copy-and-modify starting point is `ui_kits/web/index.html`.

## The non-negotiables

These are the rules that make Odds Primer not look like a casino:

1. **No gambling-promo language.** No "bet now," "cash in," "smart money," "lock," "free bet," "boost." Only "View source on [venue] ↗" for handoff — frames the venue as a citation, not a destination.
2. **No emoji.** Ever. Use footnote daggers (`†`, `‡`, `§`) instead.
3. **No traffic-light colors for prices.** "Best" is bold ink + flame highlight, never green. Worst is muted graphite, never red. Green/red is reserved for low-saturation movement deltas on charts.
4. **Sentence case headlines.** Title Case is reserved for the wordmark and proper nouns.
5. **One accent only.** Flame (`--flame: #D9461C`). It marks: best price, footnote daggers, hover states, the highlighted bar. Nothing else.
6. **Charts ARE the imagery.** No photography, no illustrated heroes, no gradients. Probability bars, sparklines, comparison rows.
7. **Tabular numbers everywhere a price lives.** `font-family: var(--font-mono)` + `font-variant-numeric: tabular-nums` for every price/odds/percentage.

## Type stack

- **Display, H1, H2, headlines, prose:** `var(--font-serif)` — Source Serif 4
- **Chrome, subheads, eyebrows, buttons, nav:** `var(--font-sans)` — Inter Tight
- **Wordmark:** Source Serif 4 800, glyph-led, 11px gap from glyph to wordmark. Reads as a publication's masthead, not as product chrome. (Locked v2 · 2026-05-05.)
- **All numerics:** `var(--font-mono)` — JetBrains Mono, tabular.

## Working with palettes

The system ships with one palette: warm-editorial (cream paper, navy ink, dustier flame orange). It lives at `:root` in `colors_and_type.css`. Use the variables; never hardcode.

## When the user invokes this skill

Ask 3–5 short questions about register and surface (what's the page, who's reading, what's the one thing it must do), then act as an expert designer. Do not show all of the brand foundations unprompted — write the design and let it follow the rules.

## What's not in the system yet

- Real Anthropic-stack fonts (we use free Google Fonts substitutes — flagged in README).
- Mobile-specific layouts (components are responsive but no dedicated mobile pass).
- Empty / loading / error states.
- Real venue logos (Kalshi/Polymarket marks need clearance; we use colored dots + name).
- Iconography subset is unbundled (Lucide via CDN; copy what you use into `assets/icons/` when needed).
