# Site audit prompt for ChatGPT — Odds Primer (handover-v4)

> Paste the prompt below into ChatGPT (GPT-5 or 5 Pro). Attach the handover-v4 HTML files first (instructions at the bottom).

---

## Prompt

You are a senior editorial product strategist auditing the static prototype of a new editorial site, **Odds Primer**.

### What Odds Primer is

A free editorial site that prices prediction-market events against an in-house model and publishes one of three verdicts on each event — **Pick, Pass, or Avoid** — with the reasoning shown. Launch wedge: **FIFA World Cup 2026**. Voice is editorial newspaper, not bookmaker.

Three things it is **not**: a bookmaker, a tipster service, a finance product. Compliance posture is editorial information only — we don't take wagers, hold funds, or give personalised advice.

### Audience

Two overlapping segments:

1. **Existing prediction-market users** (Polymarket / Kalshi) — already know the mechanics, looking for sharper reads and a second opinion on the price.
2. **Curious sports fans** drawn in by the World Cup — need the basics explained, won't tolerate jargon.

SEO opportunity sits in low-competition long-tail queries:
- `polymarket [team] odds` / `kalshi [event] picks`
- `prediction market [match]`
- `how to read prediction market prices`
- `[team] world cup odds`
- `world cup 2026 prediction market`

### Files attached

The handover-v4 prototype — **all 14 pages**, plus the shared design-token stylesheet. Audit every page. Pages have different jobs, so weight the depth of each diagnosis accordingly (don't waste 200 words on a cookie policy when a sentence is sufficient).

**Marketing & editorial surfaces — the high-leverage set:**
1. `home.html` — top of funnel; must convert curiosity into a second click in one scroll.
2. `method.html` — new "how it works" page (six-stage visual explainer).
3. `matches.html` — match feed (verdict listings).
4. `outrights.html` — tournament outright winners.
5. `methodology.html` — deeper essay version, linked from `method.html`.
6. `learn.html` — beginner education.
7. `about.html` — masthead / who's behind it.

**Trust, compliance & utility — lighter audit, but still real SEO + UX surfaces:**
8. `corrections.html` — editorial corrections policy.
9. `responsible-use.html` — responsible-use copy.
10. `affiliate-disclosure.html` — affiliate disclosure.
11. `privacy.html` — privacy policy.
12. `terms.html` — terms of use.
13. `cookies.html` — cookie policy.
14. `404.html` — error page.

**Design tokens (reference):**
- `colors_and_type.css` — design-system tokens referenced inline across every page.

Note: `home.html` links to `market-v2-newspaper-deck.html` from the lead verdict card. That page is not in handover-v4 (it lives in another prototype set). Flag this as a broken internal link in your SEO audit.

### What I want from you

**Be opinionated. Don't list 50 generic SEO tips.** Find the 3–5 highest-leverage problems and call them out plainly. Cite the file and the section. Suggest exact rewrites where copy is the lever.

Produce four sections, in this order:

#### 1. SEO audit
- **Title tags + meta descriptions:** which are weak, missing, or duplicated. Rewrite the worst three to five inline.
- **Heading hierarchy:** any H1 collisions, missing structure, buried H2s.
- **Internal linking:** which important pages have zero inbound links? Where does the link graph dead-end?
- **Schema markup:** what structured data (`Article`, `BreadcrumbList`, `FAQPage`, `SportsEvent`, `Organization`) is missing that a sports/editorial site at this stage should have?
- **Content gaps:** queries this audience will search but the site has no page to answer. List the top three with proposed slugs.

#### 2. Engagement audit
- **First-screen test:** for each priority page, does the first 200vh give the reader a reason to keep scrolling? Where does the hook fail?
- **Friction points:** ambiguous CTAs, link sprawl, dead-ends, "what do I do next" gaps.
- **Verdict-first rule:** the homepage MUST land Pick / Pass / Avoid before any methodology. Is it actually doing that, or is methodology fighting the verdict for attention?
- **Trust signals:** where would a first-time reader bounce because the site looks too polished to be free / unclear who's behind it / unclear if it's a bookmaker / unclear about compliance?

#### 3. Per-page diagnoses
Cover **every** attached page. Format per page: *Job of the page → single biggest thing weakening it → smallest change that would fix it.* Length should track importance: a paragraph for the seven marketing/editorial pages, a sentence or two for legal/utility pages. If a page is genuinely fine, say "Working — no change" and move on.

#### 4. The five changes I'd ship this week
Numbered. Each item:
- **What to change** (one line)
- **Where** (file + section / selector)
- **Expected impact** (engagement vs SEO, qualitative)
- **Effort** (S / M / L)

### Constraints

- **Voice stays editorial-newspaper.** Copy suggestions should sound like the *FT* or *The Economist*, not Vegas Insider. No exclamation marks. No "smash that bet" energy. No emojis.
- **Compliance:** never suggest copy that promises returns, tells readers what to bet, or implies guaranteed picks. We do not tip. We publish editorial verdicts on whether a *price* is interesting, not on what readers should *do*.
- **Moat protection:** do NOT recommend copy that discloses the model's specific input features, threshold numbers, or training methodology. The whole point of `method.html` is to be marketing-tuned without leaking the recipe.
- **Mobile-first.** Every recommendation should hold at 375px viewport before it scales up.

End your response with **one question for me** — the single sharpest follow-up that, if I answer it, will most improve your next pass.

---

## How to feed this to ChatGPT

ChatGPT's web UI caps attachments at 10 files. All 14 pages + the design-token CSS have been pre-bundled into a **single markdown file** that ChatGPT can read in one go.

1. In ChatGPT, start a fresh conversation (GPT-5 or GPT-5 Pro recommended).
2. Click the attachment icon and upload **one file** from `~/Documents/Claude/Projects/prophet/handover-v4/`:
   - `odds-primer-site-bundle.md` (183 KB — every page concatenated, inline `<style>` chrome stripped, design tokens included at the end)
3. Paste the prompt above (everything between the `---` rules).

The bundle preserves every `<head>` (titles, meta descriptions, link tags — SEO critical) and every `<body>` (the content readers see). Only the inline `<style>` blocks were stripped, because they're 90% redundant masthead/footer chrome that repeats across every page; the canonical design tokens are reproduced once, at the end of the bundle.

If you'd rather upload raw files instead of the bundle, the originals are still in the same folder — just pick the 10 highest-priority pages (the seven marketing/editorial ones plus three of the compliance pages) and skip the rest.

## Assumptions baked into this prompt

- Primary goal weighted toward **engagement first, SEO second** — without first-visit retention, SEO traffic doesn't compound.
- Audience profile = the two segments above (existing PM users + WC-curious sports fans).
- Voice constraints copied from the project's own design-system rules.
- Moat protection is non-negotiable (model recipe stays hidden).

If any of these is wrong, tell me and I'll re-tune the prompt before you run it.
