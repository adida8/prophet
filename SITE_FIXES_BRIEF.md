# Odds Primer — pre-launch mobile fixes (Claude Code brief)

Goal: get `oddsprimer.com` ready to share publicly. It was reviewed at 390×844 (mobile)
and the full prioritized list lives in `SITE_REVIEW_PUNCHLIST.xlsx` (this repo) — open it
for the per-item detail; this brief is the execution plan.

Follow this repo's `CLAUDE.md` for workflow: **work on `staging`**, commit, push, eyeball the
staging URL, then merge `staging` → `init/project-setup` to ship. Don't push half-finished work
to prod. Run the existing quality gates before each commit.

## Read this first — the root cause

Most blockers come from ONE problem: `oddsprimer.com` is serving **two sites at the same time** —
the React editorial app (`frontend/src/op/`) and the legacy static "PredictionEdge" site
(`site/generate.py`). They collide at `/`, `/about`, `/matches`, `/outrights`. The `CLAUDE.md`
already flags this route conflict as unresolved.

**Do step 1 before anything else, then re-test on a phone — several items below will disappear.**

## Verify before you act (two items are unconfirmed)

These came from a text-only review and need a 30-second on-device check first; don't fix blind:
- Legacy `/events/:slug` URLs (e.g. Colombia v Portugal) reportedly 404 — confirm, then redirect to `/m/...`.
- `/learn` — confirm whether it's one long anchored page vs the three separate primers we expect.

## Fix order

1. **Resolve the two-site route conflict (B-1).** Decide which system owns which routes — retire the
   static site, or scope it to non-conflicting paths and let the React app own the rest. Reconcile,
   then re-test `/`, `/about`, `/matches`, `/outrights`, a bad URL, and `/ledger` on mobile. Re-check
   the rest of this list against what's left.

2. **React-app mobile CSS blockers (`frontend/src/op/`):**
   - **B-2** — verdict cards (`.lv-card`) overflow right; no right padding; page scrolls sideways.
     Add `overflow:hidden; width:100%; box-sizing:border-box` to the card + children; restore `padding-right:16px`.
   - **B-3** — hamburger menu opens ~57px off the LEFT edge (anchored `right:0` to a tiny `<details>`).
     Use `position:fixed; right:0; top:0; width:min(280px,100vw); max-width:100vw`, or re-anchor to the header.

3. **Email signup (B-7).** Today it exists only in the old static `/index.html`, buried, and is broken
   (`action=/index.html`, `method=GET`, email input has no `name`). Build it into the React home page
   (and footer): `type=email name=email inputMode=email autocomplete=email required`, wire to a real
   backend (Beehiiv/ConvertKit etc.), add success + error states and a one-line privacy/operator note.

4. **Verdict-led home (B-9).** Move the headline verdict directly under the masthead/issue line; put the
   verdict key *below* the first card. (The home page must lead with Pick/Pass/Avoid, not the intro.)

5. **`/backtest` overflow (B-8).** Replace fixed-px grid (`grid-template-columns:342px`) with
   `repeat(2,1fr)` → `1fr` on mobile; wrap the table in `overflow-x:auto`; container `width:100%; padding:0 16px`.

6. **Remaining blockers:** `/about` no-trailing-slash 404 (B-4), 404 fallback serving the old index with a
   200 (B-5), `/ledger` old "PredictionEdge" branding + overflow (B-6). Most of these are downstream of
   step 1 — confirm after reconciling routes.

## Then the should-fixes (see xlsx for the full set)

Highest-value cluster:
- **Tap targets** — bring "Read the case →" (31px), "See all" links, hamburger button (36px),
  pill-nav (38px), footer links (18px) up to ≥44px hit areas.
- **Social tags (S-3)** — no OG/Twitter tags anywhere; shared links unfurl blank. Add per-page
  `og:*` + `twitter:card` + a 1200×630 image, prioritising home + per-match pages (sharing picks is the
  main growth mechanic).
- **Static-site parity** — collapse the 350px sidebar on mobile, match the editorial brand (navy
  `#0E2240`, not violet), clean `.html` URLs, fix the stale "13 May 2026" date, fix the cookie banner
  (`position:fixed`), fix the `/method.html` PICK|PASS|AVOID tab overflow. Many of these evaporate if the
  static site is retired in step 1.
- **Voice/content** — "back it" → "the line appears underpriced"; add the "Adi Dagan t/a Odds Primer"
  operator line to Privacy/Terms/signup; explain the outright "+6.5pp but doesn't clear the +3pp gate" line.

Brand reference for all of the above: body **Source Serif 4**, wordmark/chrome **Inter Tight 700**,
numerics **JetBrains Mono**, masthead navy `#0E2240`. Keep the editorial tone — not a tipster site.

## Scope

This is all website/design work (React editorial app + static generator). Do **not** touch the engine,
the output contract, or anything under `desk/` — that's out of scope for these fixes.
