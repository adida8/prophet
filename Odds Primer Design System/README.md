# Odds Primer — Design System

> An educational oddschecker for prediction markets. Compares prices across Kalshi, Polymarket, sportsbooks, and other venues for the same event, highlights the best one, and explains in plain English what the market actually means.

> **Launch surface:** a curated 2026 FIFA World Cup edition.
>
> **Audience:** the curious football fan who wants to follow the World Cup, sees prediction markets popping up on Twitter, and doesn't know what +130 actually means or why Polymarket and Kalshi can disagree on the same outcome.
>
> **Voice:** patient teacher, not tipster. Anti-gambling-promo. Closer to a quality football quarterly or sports-desk longform than to a sportsbook UI.

---

## Direction

After one round of questions, the locked direction is:

| | |
|---|---|
| **Register** | Sports-desk editorial. Magazine voice, built around a live event. The Athletic / ESPN longform, not Polymarket. |
| **Position on publication ↔ product** | **60** — leans product, but reads editorial. A working tool with a column's voice. |
| **Type** | Serif-led. Source Serif 4 carries Display / H1 / H2 (editorial register). Inter Tight handles chrome, subheads, eyebrows, and controls. JetBrains Mono for all numerics. All free Google Fonts substitutes — see *Font substitutions* below. |
| **Palette** | Warm-editorial. Cream paper, navy ink, dustier flame orange. Lives at `:root` in `colors_and_type.css`. |
| **Glyph** | **Probability bars** — four bars on a baseline rule, third bar in flame. The mark IS the system's primary chart, miniaturized. Lives in `branding/locked/glyph-bars.svg` and as a flag in the wordmark. |
| **Imagery** | No photography. Charts ARE the art. Diagrams, comparison rows, sparklines, footnoted explainers. |
| **World Cup edition** | *Editioned*, not skinned. A masthead strip ("World Cup 2026 Edition · Vol. 1") and tournament-flavored section dividers, but the brand stays the brand. |
| **Anchor screen** | An **event explainer** — "Will France win the 2026 World Cup?" — built as the UI kit's `index.html`. It's the only page that proves the three jobs at once: explain the market, compare prices, teach the number. |

---

## On the brief: a few honest reads I gave the user

These are documented so future agents working in this system understand *why* certain choices were made.

1. **The original flame orange (#FF5A1F) was shifted dustier (#D9461C).** The original is the Hermès / construction-signage orange; on a prediction-markets product it reads as alert/danger/buy-now, which is exactly the casino energy we're avoiding. The dustier shade keeps the editorial-accent intent without the alarm.

2. **"Make the user think 'I'll make my prediction now'" sits in tension with "anti-gambling-promo, doesn't tip."** The system resolves it the way good editorial does: show the *value* (best price highlighted, disagreement made legible, plain-English explanation) but never the *call to action*. The user reaches the conviction themselves. The brand never closes the sale. **No CTAs that say "bet," "buy," "cash in," "trade now."** External handoff to the venue is framed as "View source on Kalshi ↗" — the venue is a citation, not a destination. (Updated 2026-05-05 from "Open on Kalshi ↗" — same restraint, but the new phrasing makes the citational stance explicit.)

3. **Best price is not green.** Traffic-light semantics are casino semantics. In Odds Primer, "best" is conveyed by **bold ink + a flame underline + a 'best' eyebrow tag** — the same way a magazine highlights an editor's pick. Green/red is reserved for actual market movement deltas, used at low saturation.

4. **The system has no "buy" button.** It has a "View source on [venue] ↗" link. Always with the venue's name. Never anonymized.

---

## Files in this project

```
README.md                       ← you are here
SKILL.md                        ← agent skill manifest (Claude Code-compatible)
colors_and_type.css             ← all design tokens; load this first
preview/                        ← design-system cards (registered as assets)
  ├─ palette-warm.html
  ├─ palette-warm.html
  ├─ glyph-bars.html
  ├─ glyph-dogear.html
  ├─ type-display.html
  ├─ type-body.html
  ├─ type-numerics.html
  ├─ type-scale.html
  ├─ spacing.html
  ├─ radii-shadows.html
  ├─ buttons.html
  ├─ links-tags.html
  ├─ comparison-row.html
  ├─ footnote-system.html
  ├─ chart-primitives.html
  ├─ masthead.html
  └─ wordmark.html
ui_kits/
  └─ web/
       ├─ README.md
       ├─ index.html            ← event explainer (the anchor screen)
       ├─ Masthead.jsx
       ├─ ComparisonRow.jsx
       ├─ Footnote.jsx
       ├─ ProbabilityBar.jsx
       ├─ EventHero.jsx
       ├─ Glossary.jsx
       └─ Wordmark.jsx
branding/                       ← all brand assets, exploration trail, prompts
  ├─ README.md                 ← branding index — start here
  ├─ locked/                   ← canonical spec + SVGs + reference render
  │   ├─ bars-locked-v2.html
  │   ├─ wc-edition-brief.md
  │   ├─ glyph-bars.svg
  │   ├─ wordmark.svg
  │   └─ odds_primer_logo.png
  ├─ assets/                   ← PNG asset set (lockups, glyph, favicon, etc.)
  │   ├─ README.md
  │   ├─ lockups/  wordmark/  glyph/  glyph-trio/
  │   ├─ favicon/  app-icon/  avatar/  watermark/
  │   └─ wc-edition/           ← WC 2026 edition assets
  ├─ exploration/              ← chronological trail of rejected/superseded directions
  └─ prompts/                  ← ChatGPT review prompts used along the way
fonts/                          ← (empty; fonts loaded via Google Fonts CDN — see flag below)
```

---

## CONTENT FUNDAMENTALS

The voice is **patient teacher, sports-desk register**. Not a tipster. Not a fintech. Not a casino. A columnist who happens to write about probability.

### Tone

- **Informed but humble.** The reader is smart and curious — not a beginner to football, but new to prediction markets. Don't talk down. Don't over-jargon either; if a term needs a footnote, footnote it.
- **Plain English, generous structure.** Short paragraphs. Subheads do real work. Footnotes carry the load when a sentence would otherwise need a parenthetical clause.
- **Curious, not certain.** "Polymarket has France at 16¢, which implies a 16% chance. Kalshi has them at 14¢. The four-cent gap is unusual; here's one reason it might exist." Never "France WILL win" or "Smart money is on…"
- **No exclamation marks. No emoji.** Em-dashes are fine. Footnote daggers are encouraged.

### Pronoun and casing

- **Second person ("you")** when teaching. *"You'll see two numbers next to each market."*
- **First-person plural ("we")** for editorial decisions. *"We compare four venues here; we left Manifold off because their volume is too thin to be informative."* Used sparingly.
- **Never "I."** Even though there are two people on the team, the brand is editorial and impersonal.
- **Sentence case for everything.** Headlines, buttons, labels. The only Title Case allowed is in the masthead (`Odds Primer`) and proper nouns.

### What we do not say

| ❌ Avoid | ✅ Instead |
|---|---|
| "Best bet," "hot pick," "lock," "free bet," "boost" | "Best price," "biggest disagreement," "thinnest spread" |
| "Cash in now," "trade now," "buy now" | "View source on Kalshi ↗" |
| "+130 means…" without context | "+130 is American odds for an implied 43% chance — see *Reading the numbers*" |
| "Smart money," "sharp," "the public" | "Polymarket traders," "sportsbook lines," "Kalshi volume" |
| Emoji, fire, rocket, bullseye | A footnote dagger (†), a sparkline, or nothing |
| "Don't miss" | (just don't) |

### Examples

**Eyebrow / kicker (above headline):**
> WORLD CUP 2026 · GROUP STAGE

**Headline:**
> Why Polymarket and Kalshi don't agree on France

**Standfirst (deck):**
> A four-cent gap on the same outcome looks small. Once you understand who's trading on each venue, it stops looking small.

**Body:**
> Polymarket has France at 16¢ to win the tournament outright. Kalshi has them at 14¢. The same question, two answers.<br>
> Two cents on a binary contract is an implied probability gap of two percentage points† — small in the abstract, large for a market this liquid. The gap usually reflects who's trading where.

**Footnote (rendered as `†`):**
> *† On a "yes" contract priced from 0 to $1, the price is the implied probability. 16¢ ≈ 16%.*

**Comparison label:**
> Best price is the venue offering the highest payout for the same outcome. We don't tell you to bet there — we show you it exists.

**Edition strip:**
> ODDS PRIMER · VOL. 1 · WORLD CUP 2026

---

## VISUAL FOUNDATIONS

### The system in one sentence
A magazine printed on cream paper, where every spread is a working tool. Hairline rules, generous margins, ink-on-paper type, one warm accent used like a highlighter, and tabular numbers everywhere a price lives.

### Color

- **One palette** (`warm-editorial`) — defined at `:root` in `colors_and_type.css`.
- **One accent only.** Flame (`#D9461C`). It marks: best price, "look here," footnote daggers, hover states, the underline for the user's current selection. Nothing else.
- **No traffic-light semantics for prices.** Best is bold ink + flame; not green. Worst is muted graphite; not red.
- **Market deltas (movement over time)** *do* use a muted green/red, but at low saturation and only on charts — never on chrome.
- **Venue colors** are reserved for venue identity (the tiny circle next to "Kalshi" in a comparison row). They're never used as UI accent colors.

### Type

- **Headlines (Display, H1, H2):** Source Serif 4, 600, slight negative tracking. Carries the editorial register; closer to a weekly magazine than a SaaS dashboard.
- **Chrome (H3, subheads, nav, buttons, eyebrows):** Inter Tight, 500–700. Sans for working surfaces.
- **Body:** Source Serif 4, 400. Prose, footnotes, captions, anywhere there's a paragraph.
- **Wordmark:** Source Serif 4 800, glyph-led, 11px gap from glyph to wordmark. Reads as the masthead of a publication, not as product chrome. (Locked v2 · 2026-05-05; previously Inter Tight 700.)
- **Numerics:** JetBrains Mono with `tabular-nums`. Every price, odds line, percentage, and timestamp.
- **Sentence case headlines.** Generous line-height on prose (1.55). Balanced text-wrap on headlines (`text-wrap: balance`).
- **Indented paragraphs** in long-form prose, book-style (first paragraph flush, subsequent indented 1.25em). UI text is not indented.

### Backgrounds

- **No full-bleed photography.** No gradients. No textures.
- The only "art" is **diagrams, sparklines, comparison bars, and probability strips.** Charts ARE the imagery — see `chart-primitives.html`.
- Section breaks use `paper-warm` (#F0ECE2) blocks of ~120–200px height, with a hairline rule top and bottom. Never gradients.
- Cards are **white-on-cream** (paper-pure on paper) with a 1px hairline rule, no shadow. The shadow tier exists (`--shadow-2`, `--shadow-3`) but is reserved for floating menus and the focus state of an active comparison row.

### Borders & rules

- **Hairlines, not borders.** 1px, `var(--rule)`. Most divisions are accomplished with a top-rule on the next element rather than a box border.
- Strong rule (1px ink) reserved for the masthead and section dividers.
- **No rounded containers** unless they're a button (4px) or a tag (pill 999). Cards: 6px max. Magazine spreads have square corners.

### Shadows

- **Three tiers,** all subtle:
  - `--shadow-1`: a 1px bottom rule, used for sticky headers.
  - `--shadow-2`: a 1px hairline + 2px soft shadow, used for the active comparison row.
  - `--shadow-3`: a 24px soft shadow + hairline, used for menus and the footnote popover.
- **No glow. No inner shadows. No colored shadows.** Tinted shadows belong to SaaS dashboards.

### Layout rules

- **Page gutter:** `clamp(20px, 4vw, 64px)`. The page never feels cramped.
- **Reading column:** 62ch max for serif prose. Sidebars 38ch.
- **Masthead:** sticky top, 56px tall on desktop, with a hairline-strong bottom rule. Always shows: wordmark · edition · live event indicator (if any).
- **Section dividers** are `paper-warm` blocks with an eyebrow label — they signal "you've changed parts of the magazine."
- **Footnotes** are inline-marked (`†`, `‡`, `§`) and render in a popover on hover/tap, OR in a footer column on long-form pages — both render with `op-footnote` style.

### Animation

- **Fast and short.** 120ms for hover, 200ms for state changes, 320ms only for the footnote popover.
- **`cubic-bezier(0.2, 0, 0, 1)`** for everything. No bounces. No springs. No fancy easing.
- **Crossfades and underline-grows.** Never slide-ins, never scale-ups, never confetti.
- **Number changes ticker-style** (the implied-probability percentage updates by counting), 320ms ease, only when the price actually changes.
- **No skeleton shimmers.** Use a static "—" placeholder with a quiet "loading…" caption.

### Hover & press states

- **Links:** underline color shifts from `--rule` → `--flame`. Color shifts from `--ink` → `--flame-deep`. No background change.
- **Buttons:** primary (ink) → `--ink-soft` background; secondary (outline) → `--paper-warm` fill. Press: shifts darker 6%; no scale-down.
- **Comparison rows:** hover lifts the row 1px (translateY(-1px)), tightens the rule from soft → strong, and reveals a "Compare across venues →" link that was 0-opacity. No shadow change.
- **Focus-visible:** 2px flame outline, 2px offset, 2px radius. Always visible for keyboard.

### Transparency & blur

- **Almost never.** The only `backdrop-filter` use is the masthead, which becomes 92% paper with a 12px blur once the page scrolls past 0. Otherwise everything is opaque. No frosted modals.
- **No glassmorphism, ever.**

### Corner radii

- Hairline cards: **6px**.
- Buttons: **4px**.
- Inputs: **4px**.
- Tags / pills: **999px**.
- Section blocks, masthead, dividers: **0**. Square is the default.

### Cards

A "card" in Odds Primer is a `--paper-pure` block with `--hairline` border, **6px** radius, no shadow. It has a label eyebrow at top-left, sometimes a meta line at top-right, and content below. Cards do not float — they sit on the cream paper.

### Iconography

See `ICONOGRAPHY` below.

---

## ICONOGRAPHY

### The principle
Odds Primer is a magazine. Magazines do not pepper their pages with icons. **Use type, hairlines, and tabular numbers first; reach for an icon only when language is slower than a glyph.**

### What we use
- **Lucide** (`lucide-static`) is the chosen icon system. 1.5px stroke, sentence-case naming, calm. The subset we actually use is copied into `assets/icons/` so the system is offline-capable. The full set is also linkable from CDN (`https://unpkg.com/lucide-static@latest/icons/`) for prototyping.
- **Stroke weight:** 1.5px. Color: `currentColor`. Size defaults: 16px (inline), 20px (chrome), 24px (masthead).
- **Substitution flag:** Lucide is being used as the closest match to the editorial register we want. It's not custom. If/when a custom icon system is commissioned, replace the subset in `assets/icons/`.

### What we use icons FOR
- The "View source on [venue] ↗" link (a small arrow-up-right; *not* a chevron).
- Footnote markers — but these are *typographic* (`†`, `‡`, `§`), not icons.
- Venue identity — a tiny solid circle of `--venue-{name}` color next to the venue's name. Not a logo.
- Sparkline up/down direction — handled in SVG, not icon font.
- Search, close, expand/collapse in chrome.

### What we do NOT use icons for
- **Buttons.** Primary actions are text. "Compare venues," not a comparison icon.
- **Decoration.** No icon ever sits in a hero just for vibes.
- **Section headers.** An eyebrow label does the job.
- **Emoji.** Never. The brand has no emoji vocabulary at all.

### Unicode characters used as glyphs
- **Footnote daggers:** `†` `‡` `§`
- **Em dash:** `—` (used liberally — replaces colons in editorial prose)
- **Arrow up-right:** `↗` for external venue links (used inline with text, not as an icon)
- **Section mark:** `§` for glossary entries
- **Bullet:** `·` (interpunct) for masthead separators — never `•`

---

## Font substitutions — flagged

You did not provide font files. The system uses **Google Fonts substitutes** for the Anthropic-adjacent stack you asked for:

| You asked for (≈ Anthropic) | I substituted | Why |
|---|---|---|
| Styrene B / Söhne | **Inter Tight** | Closest free geometric sans with tight tracking. Söhne Var would be the upgrade. |
| Tiempos Text | **Source Serif 4** | Closest free editorial serif with optical-size axes. Tiempos is the upgrade. |
| (numerics) | **JetBrains Mono** | Wide tabular numerics; Söhne Mono would be the upgrade. |

**To swap in real fonts later:** drop `.woff2` files into `fonts/`, replace the `@import` in `colors_and_type.css` with `@font-face` rules, and update `--font-sans` / `--font-serif` / `--font-mono`. The rest of the system reads from the variables.

---

## Index — where to look for what

- **Tokens:** `colors_and_type.css`
- **Cards (palette / glyph / type / spacing / components):** `preview/*.html` (also visible in the Design System tab)
- **The anchor product page:** `ui_kits/web/index.html`
- **Reusable components:** `ui_kits/web/*.jsx`
- **Brand assets, locked specs, exploration trail:** `branding/` (start at `branding/README.md`)
- **Agent skill (for Claude Code or skill use):** `SKILL.md`

---

## Caveats / open questions for the team

- **Logo locked v2** (2026-05-05). Source Serif 4 800 wordmark + bare bars glyph (heights 22·38·65·30, flame on 3rd). Canonical spec at `branding/locked/bars-locked-v2.html`. Full asset set at `branding/assets/` (lockups, wordmark, glyph at multiple sizes, favicon, app icon, avatar, watermark — plus `wc-edition/` subfolder). Open: masthead wordmark weight (700 vs 750 vs 800) — currently 800 in code.
- **Logo SVG variants.** `branding/locked/wordmark.svg` references Source Serif 4 inline (works in browsers); for native rasterizers (social cards, email) an outlined-paths variant is needed.
- **Tournament edition motifs** (group-stage divider, knockout-stage divider, tournament-final treatment) — sketched at the comparison row level only. Full edition design comes after brand lock.
- **Venue logos are not bundled.** Kalshi, Polymarket, and sportsbook marks are referenced as colored dots + name. Real logos must be cleared before they're used.
