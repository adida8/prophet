# Odds Primer — v4 handover

14 self-contained HTML pages, one stylesheet, three brand assets. Drop-in
deployable as a static site, or use as the source of truth for a React /
Next.js port.

---

## What's in this folder

```
README.md                       ← you are here
colors_and_type.css             ← design tokens (palette, type, spacing, hairlines)
home.html                       ← /
outrights.html                  ← /outrights
matches.html                    ← /matches
about.html                      ← /about
learn.html                      ← /learn
methodology.html                ← /methodology
privacy.html                    ← /privacy
terms.html                      ← /terms
affiliate-disclosure.html       ← /affiliate-disclosure
responsible-use.html            ← /responsible-use
cookies.html                    ← /cookies
corrections.html                ← /corrections
404.html                        ← server's 404 handler
assets/
  ├─ glyph-bars.svg             ← the 4-bar mark (favicon, social, app icon)
  ├─ wordmark.svg               ← glyph + "Odds Primer" wordmark
  └─ wordmark-tagline.svg       ← canonical lockup with tagline
```

All HTML files reference `./colors_and_type.css` from the same directory.
All brand SVGs are also embedded inline in each page — `assets/` is for
favicons, social cards, and any future React/Next port that wants
standalone files.

---

## Fastest path to live

The whole folder is a deployable static site. To ship a private preview:

1. Drag the folder onto **Vercel** or **Netlify** as a static deploy.
2. Configure the host to serve `home.html` at `/` and `404.html` as the
   404 page. On Vercel, that means adding a rewrite `/ → /home.html`
   (or rename `home.html` → `index.html` before upload — see below).
3. Done.

If you prefer the index-page convention, rename `home.html` → `index.html`
and update internal links: every page references `./home.html` in the
masthead brand-lock and in the footer. A one-line sed will sort it out:

```bash
sed -i '' 's|"\./home\.html"|"./"|g' *.html  # mac
sed -i    's|"\./home\.html"|"./"|g' *.html  # linux
```

---

## Route map

| File                          | Target URL              | Active nav state                |
| ----------------------------- | ----------------------- | ------------------------------- |
| home.html                     | `/`                     | (brand-lock is the home link)   |
| outrights.html                | `/outrights`            | pill nav "Winners" active       |
| matches.html                  | `/matches`              | pill nav "Matches" active       |
| about.html                    | `/about`                | burger overflow                 |
| learn.html                    | `/learn`                | burger overflow                 |
| methodology.html              | `/methodology`          | burger overflow                 |
| corrections.html              | `/corrections`          | burger overflow                 |
| privacy.html                  | `/privacy`              | footer legal                    |
| terms.html                    | `/terms`                | footer legal                    |
| affiliate-disclosure.html     | `/affiliate-disclosure` | footer legal                    |
| responsible-use.html          | `/responsible-use`      | footer legal                    |
| cookies.html                  | `/cookies`              | footer legal                    |
| 404.html                      | host's 404 handler      | —                               |

---

## Brand — the load-bearing decisions, do not reinvent

**Palette** (all defined in `colors_and_type.css` as CSS variables):

- `--paper` `#FAF7F0` — warm cream (the page)
- `--ink` `#0E2240` — deep navy (primary type)
- `--flame` `#D9461C` — dusty orange (the single accent)
- `--flame-deep` `#A8341A` — hover/press
- `--flame-tint` `#F7E4DA` — Pick card wash

**Type** — three families, loaded from Google Fonts CDN via `@import`
in `colors_and_type.css`:

- **Inter Tight 700** — wordmark + chrome + UI
- **Source Serif 4** — display headlines, prose, italic taglines
- **JetBrains Mono** — prices, percentages, any column-aligned numerics

**Wordmark spec** (do not substitute):

- "Odds Primer" in Inter Tight 700, letter-spacing `-0.022em` at 22px masthead, `-0.025em` at 38px display
- Bars glyph: viewBox `0 0 38 34`, bars at `x={2,11,20,29}` width 6, heights `{10, 16, 28, 14}`, **flame on the third bar**, baseline rule at `y=34` stroke-width 1
- Canonical lockup carries the tagline beneath: *"The **AI** sports desk for **market edge**"* — Source Serif 4 italic 400, flame (`#A8341A`) on the words "AI" and "market edge"

**The tagline lives in two places**:
- Home masthead, under the wordmark
- Footer of every page

It does not appear on About/Learn/etc. mastheads (intentional — masthead height stays stable across nav). Mobile keeps the tagline visible at all viewport widths.

---

## Terminology — load-bearing

Use these exactly. Mixing them confuses the brand.

| Term                  | Means                                          |
| --------------------- | ---------------------------------------------- |
| **Odds Primer**       | The editorial publication (the site)           |
| **The Desk**          | The AI verdict engine                          |
| **Pick / Pass / Avoid** | The three editorial verdicts                 |
| **Model probability** | The estimate The Desk produces                 |
| **Edge**              | Difference between market and model probability|
| **"View source on [venue] ↗"** | The outbound link pattern. Never "Bet now" / "Trade now" / "Back it" |

---

## Voice — no-go list

These words do not appear in Odds Primer copy under any circumstance:
**bet now, trade now, back it, lock-of-the-day, banker, smash, free money,
guaranteed (as a claim — "not guaranteed" as a disclaimer is fine).**

Editorial register is patient teacher, not tipster. We explain prices and
flag mispricing. We do not instruct readers.

---

## Content that is mocked — replace before launch

Sample data lives hardcoded in the HTML. Replace these when wiring to
real data:

| Where                                  | Mocked content                                |
| -------------------------------------- | --------------------------------------------- |
| `home.html` lead verdict               | France v Mexico, +4pp edge, Polymarket −180   |
| `home.html` article previews           | "3 picks · 1 avoid · +5pp top edge"           |
| `home.html` sticky mobile bar          | "Today: 3 picks · top edge +5pp"              |
| `outrights.html` picks                 | France / Argentina (Pick), Brazil (Avoid)     |
| `outrights.html` field-stands chart    | Brazil 22 / Argentina 18 / France 16 / England 12 / Spain 11 / Field 21 |
| `matches.html` fixture board           | 8 fixtures across Group F / A / B             |
| `home.html` "Featured columns"         | 3 placeholder editorial cards                 |
| Last-updated stamps                    | "Updated 13 May 2026" — bump on first deploy  |

---

## What's TBD on your side

Each of these is intentionally unfinished — fill in during integration:

- **Domain.** All internal links assume single-domain relative paths.
  Confirm `oddsprimer.com` (or whatever) and update OG meta when ready.
- **Cookie banner persistence.** The banner appears on every page load.
  For production, wire `localStorage.setItem('op_cookie_consent', …)`
  on Accept/Reject/Save, and check on page load before rendering.
- **Newsletter form.** Currently presentational only
  (`onsubmit="event.preventDefault();"`). Wire to whatever provider
  (Buttondown / ConvertKit / Beehiiv) when you've picked one.
- **Affiliate referral links.** Currently `href="#"`. Plug in real
  Polymarket / Kalshi referral codes when those programs land.
- **Privacy / Terms / Cookie policy dates.** All show
  "Last updated 13 May 2026" — bump on first deploy and again on any
  substantive edit.
- **Governing law.** Terms intentionally has no jurisdiction line —
  add only after counsel has confirmed.
- **Newsletter copy.** Privacy intentionally has zero newsletter
  references (not live at launch). If/when you add one, the Privacy
  page needs a new section.

---

## Email addresses used

Only these. `hello@` is retired.

- `desk@oddsprimer.com` — general contact
- `corrections@oddsprimer.com` — factual error reports
- `privacy@oddsprimer.com` — privacy / GDPR requests
- `legal@oddsprimer.com` — legal + affiliate questions

---

## What I do not want changed without checking

These are decisions that have been locked deliberately. Touching them
will break consistency with the rest of the brand work.

- The wordmark + tagline lockup
- The Pick / Pass / Avoid label set
- The "View source on [venue] ↗" outbound pattern
- The "We do not take wagers, hold funds, execute trades…" footer
  disclaimer wording (it's load-bearing for regulatory positioning)
- The role-based emails above
- The "no founder names, no registered-entity claim" rule (we are an
  independent editorial website — not a registered company)

If something on this list needs to change, ping me before touching it.

---

## Recommended implementation order

1. **Static deploy** to Vercel/Netlify behind a password (private preview).
2. **Set up `/404` routing** on the host.
3. **Wire the cookie banner** to `localStorage`.
4. **Plug in the newsletter provider** (or hide the form if it's not in
   scope for v0).
5. **Replace mocked content** with real engine output — start with the
   home lead verdict + outrights, then the matches board.
6. **Self-host fonts** if you want to remove the Google Fonts CDN
   dependency. Drop the `.woff2` files into `assets/fonts/` and replace
   the `@import url(...)` line at the top of `colors_and_type.css` with
   `@font-face` declarations.

---

## Questions

Hit me before changing brand decisions, copy on the trust pages
(privacy/terms/etc.), or the wordmark lockup. Everything else — layout
tweaks, mobile polish, performance — your call.
