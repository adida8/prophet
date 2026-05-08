# Odds Primer · branding

Everything brand-related — locked specs, ready-to-use assets, the exploration trail that got us here, and the ChatGPT review prompts used along the way.

---

## Start here

If you just want to use the logo, go to `locked/` for the canonical spec and SVGs, or `assets/` for ready-to-drop-in PNGs at every size.

If you want to understand *why* the brand looks like it does, read `locked/wc-edition-brief.md` then skim `exploration/` chronologically.

---

## Folder map

```
branding/
├── README.md                              ← you are here
│
├── locked/                                ← THE final, canonical brand
│   ├── bars-locked-v2.html               ← spec page (open in browser): primary, editorial, favicon stack, masthead, social card, venue handoff, technical spec
│   ├── wc-edition-brief.md               ← WC 2026 edition strategic brief — "Odds Primer is the masthead; World Cup 2026 is the issue"
│   ├── glyph-bars.svg                    ← the 4-bar glyph alone (heights 22 · 38 · 65 · 30, flame on 3rd)
│   ├── wordmark.svg                      ← full lockup as SVG (Source Serif 4 800 referenced inline)
│   └── odds_primer_logo.png              ← reference render at 2400×1400 — used for cross-LLM design reviews
│
├── assets/                                ← READY-TO-USE PNG asset set
│   ├── README.md                          ← which file to use for which surface
│   ├── lockups/                           ← primary + editorial lockups, cream + navy
│   ├── wordmark/                          ← wordmark only
│   ├── glyph/                             ← glyph only at 32 / 64 / 128 / 256 / 512 / 1024 px (cream / navy / transparent)
│   ├── glyph-trio/                        ← 3-bar fallback for tiny sizes (16 / 32)
│   ├── favicon/                           ← favicon set: 16 / 32 / 48 / 192 / 512
│   ├── app-icon/                          ← iOS touch icon (180), App Store master (1024)
│   ├── avatar/                            ← square profile pictures, 400 + 1024, cream + navy
│   ├── watermark/                         ← low-opacity overlays for image annotation (transparent bg)
│   └── wc-edition/                        ← WC 2026 ISSUE-specific assets
│       ├── README.md
│       ├── lockups/                       ← logo + edition strip, cream + navy, horizontal + stacked
│       ├── avatars/                       ← square profile pictures with WC 2026 edition mark
│       └── banners/                       ← Twitter cover, LinkedIn banner, email header, Instagram square
│
├── exploration/                           ← chronological trail (kept as historical record — not for use)
│   ├── 01-logo-explorations.html         ← original 4 directions: bars, typographic, footnote-dagger, monogram
│   ├── 02-bars-iterations.html            ← 6 bar variants once "bars" was chosen
│   ├── 03-bars-flame-treatments.html      ← 5 alternatives to the rejected caret
│   ├── 04-bars-synthesis.html             ← caret synthesis (rejected — caret felt UI-ish)
│   ├── 05-bars-locked-v1.html             ← v1 spec with Inter Tight wordmark (superseded by v2 serif)
│   ├── 06-wordmark-tuning.html            ← 4 wordmark variants (sans vs serif, full vs trimmed)
│   ├── 07-bars-wc-edition-quiet.html      ← WC edition: 6 quiet attachments (rejected — too quiet)
│   ├── 08-bars-wc-edition-banner.html     ← WC edition: 6 louder banner attachments (rejected — wrong category)
│   └── 09-bars-wc-edition-26.html         ← WC edition: FIFA-style "26" digit treatment (rejected — derivative)
│
└── prompts/                               ← ChatGPT review prompts used to stress-test the work
    ├── 01-bars-iterations-review.md       ← review of the 6 bar variants — produced the A2/A5 cross-breed pick
    ├── 02-wc-edition-strategy.md          ← strategic framing prompt — produced "Odds Primer is the masthead"
    └── 03-wc-design-execution-review.md   ← execution review of the three WC mockups — produced the punch list
```

---

## Locked decisions (don't redesign)

- **Glyph:** four bars on a navy baseline rule. Heights 22 · 38 · **65** · 30. Flame on the third bar only. ViewBox `0 0 56 50`.
- **Wordmark:** Source Serif 4 weight 800, letter-spacing −0.012em, OpenType `ss01` on. Glyph-led, 11px gap from glyph to wordmark.
- **Trio fallback:** at 16px the glyph collapses to 3 stocky bars (heights 18 / 34 / 24 in a 48×44 viewBox). Use this for favicon-16 only.
- **Palette:** cream paper `#FAF7F0`, warm paper `#F2EDE0`, navy ink `#0E2240`, ink-soft `#3D4F6A`, rule `#D9D2BE`, dustier flame `#D9461C`. Single accent — flame appears only on the third bar of the glyph and as the "best price" semantic in product UI.
- **WC 2026 edition is a cover treatment, not a logo modifier.** "World Cup 2026" in Inter Tight Bold navy + secondary copy in graphite. No FIFA imagery, no trophy, no host-country flag, no soccer ball, no badge.

---

## What's still open

- **Masthead wordmark weight** — 700 vs 750 vs 800 still TBC. Currently 800 in code. See `locked/bars-locked-v2.html` §02 for the side-by-side test.
- **Outlined-paths variant of `wordmark.svg`** — current SVG references Source Serif 4 inline (works in browsers, fails in native rasterizers without web fonts). Needs a one-time export through a design tool.

---

## How to regenerate the PNG asset set

The render scripts live in your scratch directory during build (`/tmp/render_*.py`). They use `PIL` + Source Serif 4 ExtraBold + Inter Tight (downloaded from fontsource and converted woff2 → ttf via `fontTools`). To rebuild after a logo geometry tweak: open the relevant script, update the `draw_glyph` function, rerun. Output goes to `branding/assets/`.
