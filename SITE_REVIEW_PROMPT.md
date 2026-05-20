# Odds Primer — pre-launch mobile review prompt

> Paste everything below the line into a fresh Cowork session that has the
> **Claude in Chrome** extension connected.

---

You are doing an **end-to-end, mobile-first pre-launch review of
`https://oddsprimer.com`**. I'm about to start sharing this link publicly for the
first time, and the overwhelming majority of people I share it with will open it
on a phone. So **mobile usability is the lens for this entire review** — desktop
is out of scope unless something is so broken it's worth a one-line note.

**What Odds Primer is:** an educational oddschecker for prediction markets, led by
the FIFA World Cup 2026 as its launch "issue." The product's wedge is the
**verdict** — every match and the tournament-winner market gets a Pick / Pass /
Avoid call with a plain-English explanation. Price comparison is the scaffolding;
the verdict is the heart. The brand is editorial, newspaper-of-record in tone —
"Odds Primer is the masthead; World Cup 2026 is the issue" — not a hype betting
site.

**An email signup has just been added** somewhere on the site (likely the home
page and/or footer). Review it as a first-class part of the launch — and judge it
specifically as a phone experience.

## How to run this

Use the **Claude in Chrome** tools (`navigate`, `get_page_text`, `read_page`,
`resize_window`, `javascript_tool`, `find`) — do NOT raw-fetch the HTML, because
the site is client-rendered React and a raw fetch returns an empty shell.

**Set the viewport to a real phone size before you load anything:**
`resize_window` to **390 × 844** (iPhone 14-class). Do the entire review at this
width. The product rule is mobile-first and non-negotiable, so a layout that only
works on desktop is a defect, not a nuance. Take a screenshot of each page so you
can judge what the visitor actually sees above the fold.

## Pages to visit (all on `https://oddsprimer.com`)

- `/` — home / editorial front page (and the email signup)
- `/about`
- `/learn` + each of the 3 primers linked from it
- `/matches` — match list, then open a couple of individual match pages from it
- `/outrights` (and `/outrights/wc26`) — tournament-winner market
- `/ledger` — paste-a-wallet viewer; check the empty state and, if easy, a
  populated state
- `/backtest` — backtest dashboard (public and linkable)
- a deliberately bad URL (e.g. `/this-page-does-not-exist`) — confirm a real,
  on-brand 404 rather than a blank screen

**Known issue to verify:** there's a route conflict at `/` between the React
editorial app and a separately-generated static site (`/`, `/matches`,
`/outrights`). On mobile, confirm a visitor lands on the intended editorial page
and the two systems aren't double-rendering or leaking each other's layout.

## What to evaluate on each page (mobile lens)

1. **Tap targets & ergonomics** — are buttons, links, the verdict-card CTA, and
   nav items large enough and far enough apart to tap with a thumb (~44px)? Any
   controls crammed against each other or against the screen edge? Is the primary
   action reachable without hunting?

2. **Layout & overflow** — anything cut off, overflowing horizontally, forcing
   sideways scroll, or overlapping at 390px? Text that's too small to read without
   zooming? Verdict cards should hold the locked single-chip design and stack
   cleanly — MODEL / MARKET / edge and venue / price / CTA should remain legible
   when narrow (CTA becomes a full-width 44px button on mobile). Tables (matches,
   ledger, backtest) are the usual offenders — check they reflow or scroll
   gracefully rather than breaking the page.

3. **Above-the-fold / first impression** — on a phone, what's visible before any
   scroll? The home page should **lead with the verdict**, not a generic "we
   compare prices and explain" pitch. Is the value clear in the first screen?

4. **Navigation** — is there a working mobile nav (hamburger or equivalent)? Does
   it open, close, and route correctly? Can you always get back home? Flag links to
   `/dashboard` or other legacy/unlinked pages that shouldn't be public yet.

5. **Email signup (mobile)** — find it. Is the placement obvious and the reason to
   subscribe clear? Does the field bring up the right keyboard / input type for
   email? Does it validate (try empty, malformed, and valid)? Are there clear
   success and error states on a small screen? Does the submit actually succeed —
   or could it silently drop a signup? Is there a lightweight privacy/consent line
   (operating entity is "Adi Dagan t/a Odds Primer," a free service,
   pre-incorporation — honest and minimal, no overclaiming)?

6. **Performance & stability on mobile** — slow first paint, layout shift as
   things load, images that arrive late or oversized, anything janky on scroll.

7. **Brand & content** — body type Source Serif 4, wordmark/chrome Inter Tight
   (700), numerics JetBrains Mono; consistent masthead, nav, and footer across
   pages; editorial tone. Flag typos, placeholder/draft/"TODO" copy, stale dates,
   broken links, and any page that styles like a different product (e.g. the legacy
   dark-theme dashboard bleeding in).

8. **Mobile SEO basics** — confirm a `<meta name="viewport">` is present and
   correct (this is the foundation of mobile rendering), plus a unique `<title>`
   and meta description per page and Open Graph / Twitter tags (since shared links
   will unfurl in messaging apps — check the OG image and title look right). Note
   any `noindex` left on by accident.

## Output

Deliver a single **prioritized punch list**, grouped into three buckets:

- **Blockers** — must fix before sharing (broken/overflowing pages on mobile,
  unusable tap targets, broken signup, missing viewport meta, route conflict
  visibly breaking the home page, off-brand or draft content a new visitor lands
  on).
- **Should-fix** — real issues that won't stop a launch but should be done soon.
- **Nice-to-have** — polish.

For **each** finding give: the **page/URL**, a one-line description of the problem
as seen on a phone, and a **concrete fix** (what to change, and where in the repo
if you can infer it — editorial site `frontend/src/op/`, static site generated by
`site/generate.py`, Ledger `frontend/src/ledger/`). Don't fix anything — just
report. Be specific; skip generic advice. Every line should be actionable.
