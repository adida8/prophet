# Session Log — Prophet

---
## [2026-05-18 · Card design v4 — dual-chip Layout A locked, slot-audit xlsx, Faktor round-2 spec sync] — Cowork

**Summary:** Continuation of the v4 launch thread. Three big workstreams landed in one long session. **(1) Card design.** Adi asked to redesign the canonical card so both Polymarket and Kalshi prices appear on every match/outright card, with a clear CTA pushing to the venue. Walked through three layouts (A compact dual-chip, B side-by-side panels, C venue ladder) and four CTA push levels (L1 plain text → L4 action language). Adi locked Layout A + L3 button-styled CTA + cents-primary/American-odds-secondary. Built `cards-v4.html` showcase — six variants (Match Pick / Pass / Avoid; Outright Pick / Avoid; lead-verdict scale-up). Caught the −180 vs 52¢ probability-conversion bug (52% implied = −108, not −180); fixed every chip across the showcase so the numbers actually compute. After Adi flagged "CTAs too soft", dropped the unified "Market" reads slot (each venue chip now carries its own implied probability + per-chip edge), promoted venue CTAs to solid ink buttons reading "Open Polymarket ↗" / "Open Kalshi ↗" with flame arrows. Propagated the new card into `handover-v4/home.html` lead verdict, replacing the old `lv-card` single-venue block. Mobile-tightened buttons (34→36px height) and chip padding (12/12/10) so two stacked chips don't dominate the mobile fold. **(2) Slot audit.** Built `desk-content-slot-audit-v4.xlsx` — 99 slots across home/outrights/matches, sourced into six tags (DESK / DESK-NEW / DESK-DERIVED / COMPOSED / EDITORIAL / STATIC). Sheet 2 is a 15-row "Contract gaps" list — the engineer's TODO of fields The Desk needs to surface, sorted by priority. Critical gap is `market_prices.{polymarket, kalshi}` — the dual-chip card needs both venue prices on every output, not just the "chosen" one. **(3) Faktor round-2 spec sync.** Faktor's review flagged that the v0.2/v0.5 spec edits Adi promised never made it to `docs/desk-handoff-specs @ 18a3d41`. Diagnosed the drift: edits existed in `prophet/` (Cowork's spec workspace), never copied into `market_tips_ai-1`. Patched a Stage 5 / PR 1 acceptance internal inconsistency in the waist spec while in there. Bundled three specs into `outputs/desk-spec-sync-2026-05-18/` with SYNC.md commands + reply draft. Adi pushed `15d4370` to `docs/desk-handoff-specs` — diff confirms waist v0.2 + data-layer v0.5 landed cleanly (137 + 30 lines updated across the two files). Faktor unblocked for PR1 + Phase 1a.

**Decisions (locked 2026-05-18, this session):**

- **Card design is `card-v4` Layout A** — compact dual-chip across all match + outright surfaces. Same skeleton, two metadata deltas between Match and Outright (kickoff vs resolution date; paired teams vs single team). One component family with `.is-pick / .is-pass / .is-avoid / .is-lead` modifiers.
- **No unified "Market" reads slot.** Each venue chip carries its own cents (= implied probability) + American odds. The single "Model 56% — The Desk's estimate, before venue prices" stat sits above the chips. Per-chip edge ("+4pp on Polymarket, +3pp on Kalshi") makes the venue spread legible without writing it in prose.
- **Venue CTA = solid ink button, neutral verb "Open [venue] ↗".** L3 push level — visual weight, not action language. No banned-word rule violation. The "Read the market case →" overflow link remains as the editorial-dossier path (internal traffic, not affiliate).
- **Price format is cents primary + American odds secondary**, internally consistent. 52¢ ↔ −108 (not −180). Every chip on every variant rechecked against the conversion formulas. American odds for negative (favourite) = `−(p / (1−p)) × 100`; positive (underdog) = `+((1−p)/p) × 100`.
- **Mobile button minimums**: standard 36px height / 11px font / 8×10 padding; lead variant 38px / 11.5px / 9×12. Chip internal padding `10px 12px 9px` on mobile. Within WCAG AA tap-target guidance (24×24 minimum), under HIG 44×44, but justified for editorial card density.

**Files shipped:**

- `Odds Primer Design System/mockups/cards-v4.html` — canonical card showcase, 6 variants, ~32KB self-contained. Inline CSS, brand tokens, internally consistent prices.
- `handover-v4/home.html` — lead verdict swapped from old `lv-card` single-venue block to new `card-v4 is-pick is-lead` dual-chip. Cards-v4 CSS injected. American odds bug fixed (52¢ / −108).
- `desk-content-slot-audit-v4.xlsx` — 99-row slot inventory + 15-row Contract gaps + 6-tag legend. Generated via openpyxl with formatted source-tag fills (flame for DESK-NEW, soft green for DESK, pale gold for DESK-DERIVED, etc.).
- `outputs/desk-spec-sync-2026-05-18/SYNC.md` — Faktor round-2 sync bundle with commit commands, reply draft, and the three updated specs.
- `THE_DESK_POSITION_WAIST_SPEC.md` — patched Stage 5 / PR 1 acceptance internal inconsistency (both sections now name `Side / MarketSnapshot / VenuePrice`, no stale `ModelOutput`).

**Project Updates:**

- **`docs/desk-handoff-specs` HEAD is `15d4370`** (was `18a3d41`). Waist v0.2 + data-layer v0.5 + outrights v0.2 all on the branch. Faktor's PR1 + Phase 1a unblocked.
- **Contract gap inventory exists.** 15 fields The Desk needs to surface for the v4 site, in priority order: `market_prices.{venue}` (Critical, blocks all dual-chip cards) → `model_p` / `market_p` surfacing → `today.headline_verdict` + aggregate counts → group_summary → kickoff_local + venue.tz → match.market_url → full `OutrightOutput` contract. Captured in the xlsx.

**Action Items:**

- [ ] **Adi: reply to Faktor** with the confirmation message — branch tip `15d4370`, headers read v0.2/v0.5/v0.2, plus the waist Stage-5 inconsistency fix. Draft is in SYNC.md and was pasted in chat.
- [ ] **Adi: pick a canonical clone of market_tips_ai.** Currently has `~/Code/market_tips_ai` (where the spec pushes went) AND `~/Code/market_tips_ai-1` (where the SYNC.md re-run failed). Two clones of the same repo will cause confusion again. Rename one to `_archive` once the other is confirmed canonical.
- [ ] **Adi: review the slot audit xlsx** before next session — sets the agenda for what The Desk needs to publish to drive the site. The "Contract gaps" sheet is the engineer's TODO.

**Open Threads (carry to next session — Adi flagged he wants to keep working on these):**

- **Propagate `card-v4` to `/matches` and `/outrights`.** The home lead verdict is on the new design; the matches board (8 fixture rows) and outrights page (3 picks + field-stands chart) still use the old single-venue patterns (`.fx` row family on matches, `.opick` on outrights). Sweep is ~45 minutes: build a compact "single-line per chip" variant for the board rows (so 8 stacked dual-chips don't dominate vertical space), keep the full vertical dual-chip for outright picks (only 3 rows, fits).
- **Optional card refinements** (Adi hasn't decided):
  - "BEST" annotation on the chip with the higher edge — currently the flame underline on +4pp vs the rule underline on +3pp implicitly marks the better-for-Pick venue; an explicit "BEST FOR PICK" badge would make it loud. Adi's call.
  - Hide American odds on mobile to compress chips further (`52¢ +4pp · Open ↗` only, no `−108`). Mentioned as a future lever; not decided.
  - Single-line per chip on mobile for the board view specifically (vs the current stacked vertical).
- **Slot audit follow-through.** The xlsx is a reference, not yet acted on. Once Adi reviews, next moves are: (a) hand the Contract gaps sheet to Faktor / The Desk team as the engineering scope, (b) refine specific rows where "DESK-NEW" vs "DESK-DERIVED" is fuzzy, (c) decide whether Featured columns is engine-generated or stays EDITORIAL for v1.
- **Process gap: prophet/ → market_tips_ai-1 sync is manual.** SYNC.md proposed a tiny `~/bin/sync-desk-specs.sh` (3-line copy script). Adi to set up when he has a quiet evening. Until then, every spec edit in Cowork needs a manual `cp` step before the reply to Faktor.
- **Process gap: SYNC.md path bug.** I gave Adi `cp ~/outputs/desk-spec-sync-2026-05-18/...` as the source path. That's the Cowork sandbox path, not a Mac path. The correct source is always `~/Documents/Claude/Projects/prophet/`. Fixed conceptually but if I generate another sync bundle the SYNC.md should use the prophet path, not the outputs path.

**Handoff for next session:**

Card design is locked at `card-v4` Layout A · L3 buttons · per-chip data. The canonical showcase lives at `Odds Primer Design System/mockups/cards-v4.html` (6 variants, internally consistent prices). The home's lead verdict at `handover-v4/home.html` already runs this design. Next move on the card front is to **propagate to `/matches` (8 fixture rows) and `/outrights` (3 picks + field chart)** — design a compact "single-line per chip" variant for the matches board so 8 stacked cards don't kill the mobile fold; keep the full vertical chip for the 3 outright picks. The slot audit at `desk-content-slot-audit-v4.xlsx` is the reference doc for what content fields The Desk needs to feed each card — Sheet 1 is the inventory, Sheet 2 is the engineer's TODO of contract gaps (15 rows, Critical at the top). On the Faktor side, `docs/desk-handoff-specs` is at `15d4370` with waist v0.2 + data-layer v0.5 + outrights v0.2 — nothing more to do until Faktor pings back. No code state to restore; everything is files-on-disk and a clean git tree.

---
## [2026-05-18 · v4 launch build — verdict-teaching merge, ChatGPT mobile-fixes, full trust-page suite, handover to Faktor] — Cowork

**Summary:** Long continuation of the home-v3 thread, ending with a packaged handover for Faktor. Two rounds of ChatGPT review iterated the canonical home: round 1 produced the verdict-teaching merge (Option A standfirst + Option C lead verdict + Option B verdict-key, in that order — show first, teach second), with five copy fixes ("Read the market case" CTA, AI model named in the hero, no action language anywhere, 3-step path explainer below the lead, verdict-key relocated below the lead). Round 2 delivered eight mobile-conversion fixes (shorter hero, lead-verdict CTA as a full-width 44px mobile button, sticky bar "Learn → See reads" + "top edge +5pp", drop "Home" from the pill nav so it's Winners/Matches only, rewrote the "Polymarket is the slower" thesis line, plus tighter hero / lead-verdict / path-explainer padding under 720px, plus Pick/Pass verdict-key tightening). Then stood up a clean `/v4/` directory with all 14 pages: home + outrights + matches + about + methodology + learn + privacy + terms + affiliate-disclosure + responsible-use + cookies + corrections + 404 + colors_and_type.css. Ran a second launch-content pass per a long content spec: The Desk terminology standardised, new sitewide footer disclaimer + affiliate line, hello@ retired in favour of desk@, About copy edits (mispriced wording, independence sentence, role-based emails, body links), Learn restructured (new H1 *"Prediction markets, explained simply"*, "Not sportsbooks" section, risk note under Edge, Polymarket/Kalshi examples without endorsement, expanded "View source"), Methodology gained an "In short" callout + baseline-threshold language + two new disclosure sentences + last-updated-timestamp expectation, Privacy fully restructured into 13 sections with explicit Legal basis / International transfers / Children sections and zero newsletter references, Terms added four new sentences without inventing governing law. Built /404. Softened the home "How we work" copy so even quoted gambling-promo words are gone. Packaged everything into `handover-v4/` + `oddsprimer-v4-handover.zip` (101KB) with a README.md that covers route map, brand spec, terminology, no-go list, mocked-content list, what's TBD on Faktor's side, and the don't-change-without-checking list. Wrote a paste-ready Slack/email for Adi.

**Decisions (locked 2026-05-18, this session):**

- **Canonical home page order is fixed.** Hero → lead verdict → path explainer → verdict-key → article previews → How we work → Featured columns → Newsletter → Footer. Demo first, teach second. Locking this retires Options A/B/C; canonical = A+C+B.
- **AI model is named in the hero standfirst.** *"Our AI model compares Polymarket and Kalshi prices with its own read of each World Cup market. Every market gets one verdict: Pick, Pass, or Avoid. We show the price, the edge, and the reasoning. We don't tip."*
- **CTA copy locked.** Lead verdict says **"Read the market case ↗"**. Sticky mobile bar swaps "Learn → See reads"; both halves point to /matches. Pill nav is Winners + Matches only — Home dropped (brand-lock handles "go home").
- **No action language anywhere.** "Back it" / "sit it out" / "lock-of-the-day" stripped from every verdict-key and legend. The home "How we work" copy that previously *quoted* gambling words to disavow them was softened to *"No hype, no tip-of-the-day, no instructions"* — the anti-tipster point survives without printing the literal banned phrases.
- **Terminology lock.** *Odds Primer* = the publication. *The Desk* = the AI verdict engine. *Pick / Pass / Avoid* = the three editorial verdicts. *Model probability* = the estimate The Desk produces. *Edge* = market vs model gap. **"View source on [venue] ↗"** is the only outbound link pattern — never "bet now / trade now / back it / lock".
- **No founder names, no legal entity claim.** Public-facing operator is "Odds Primer" or "Odds Primer Editorial Desk". Footer copyright is just `© 2026 Odds Primer · An independent editorial website — not a registered company, broker, or sportsbook.`
- **Role-based emails only. `hello@` is retired.** Final set: `desk@` (general), `corrections@`, `privacy@`, `legal@`.
- **Privacy has no newsletter section.** Newsletter is not live for launch. If/when one ships, the Privacy page needs a new section for it.
- **Sitewide footer disclaimer wording is load-bearing.** *"Odds Primer is editorial information only. We are not a sportsbook, broker, exchange, financial adviser, or betting adviser. We do not take wagers, hold funds, execute trades, or provide personalized advice. Prediction-market participation involves risk and may not be available in your location."* Don't paraphrase — the wording is the regulatory-positioning surface. Paired with the affiliate line directly below.

**Files shipped:**

- `frontend/public/v4/` — clean directory, 14 files + stylesheet (~475KB):
  - `home.html` — article-style canonical with locked A+C+B structure
  - `outrights.html`, `matches.html` — content pages
  - `about.html`, `methodology.html`, `learn.html` — editorial/about pages
  - `privacy.html` (13 sections), `terms.html` (9 sections), `affiliate-disclosure.html`, `responsible-use.html`, `cookies.html`, `corrections.html` — full trust-page suite
  - `404.html` — pill links back to Home / Outrights / Matches / Learn / Methodology
  - `colors_and_type.css` — design tokens
- `frontend/public/v2/home-v3.html` — canonical mockup kept for v3 comparison; `home-v3-option-{a,b,c}.html` are historical comparison artifacts after merge.
- `handover-v4/` + `oddsprimer-v4-handover.zip` (101KB) — packaged for Faktor. Includes README.md with route map, fastest-path-to-live, brand spec, terminology, no-go list, mocked-content list, TBD list, don't-change list.
- `handover-v4/assets/{glyph-bars.svg, wordmark.svg, wordmark-tagline.svg}` — freshly generated standalone SVGs matching v4 inline lockup. The design system's `branding/locked/` folder still holds the May 8 Source Serif version (Adi's Claude.ai sync brought it back during the session) — don't import from there.

**Project Updates:**

- **Cookie banner pattern.** Fixed-bottom on every v4 page with Accept / Reject / Manage. No JS framework — vanilla `<details>` + inline `onclick`. Persistence intentionally NOT implemented; production needs `localStorage.setItem('op_cookie_consent', …)`.
- **Outbound CTA disclosure pattern.** `<p class="affiliate-note">Odds Primer may earn a referral fee if you use a partner venue. Verdicts are editorial and independent.</p>` appears below the home lead-verdict CTA, each outright pick row, and each fixture-board group on matches.
- **Mocked content inventory (all hardcoded).** Home lead verdict (France v Mexico, model 56% / market 52% / +4pp / Polymarket −180); home article-preview stats; sticky bar counts; outright picks (France/Argentina Pick, Brazil Avoid); field-stands chart (Brazil 22 / Argentina 18 / France 16 / England 12 / Spain 11 / Field 21); matches board (8 fixtures across F/A/B); "Updated 13 May 2026" stamps everywhere. Replace when wired to real engine output.

**Action Items:**

- [ ] **Adi: send the handover to Faktor.** Three paths offered: zip via email/Slack (101KB), folder via Drive/Dropbox (Drive preview), or private GitHub repo `oddsprimer-launch` for version history. Paste-ready message provided in chat.
- [ ] **Adi: sanity-check `handover-v4/home.html` on Mac before sending.**
- [ ] **Faktor: wire cookie banner to `localStorage`** so it doesn't appear on every page load.
- [ ] **Faktor: pick newsletter provider** (Buttondown recommended for editorial register) or hide the form. Privacy currently has zero newsletter references — adding one means adding a Privacy section.
- [ ] **Faktor: plug real Polymarket/Kalshi referral codes** into `href="#"` outbound links.
- [ ] **Faktor: 404 routing.** Wire `404.html` as host's 404 handler (Vercel / Netlify / Nginx config).
- [ ] **Eventually: self-host fonts.** Currently loaded from Google Fonts CDN via `@import` in `colors_and_type.css`. Self-hosting removes the runtime dependency.
- [ ] **Adi: confirm domain.** All internal links assume single-domain relative paths; `oddsprimer.com` not yet confirmed. OG meta tags need a real canonical.

**Open Threads (carry to next session):**

- **Conflict with the parallel 2026-05-18 Outright Winner mockup work** (sibling session, also today). That session built `Odds Primer Design System/mockups/wc-outright.html` with a tabbed `/desk` home (Outright | Matches), Monte Carlo simulator brief pending, default-flip via `DESK_DEFAULT_VIEW`. My v4 work assumes the article-style home with `/outrights` and `/matches` as separate pages from `/`. **These two designs diverge.** Open question for next session: do we go (a) tabbed `/desk` per the wc-outright mockup, (b) article-style `/` with separate routes per v4, or (c) both — `/` is article-style for the public, `/desk` is a tabbed product view? The wc-outright mockup is mobile-first which v4 also is, so visual continuity is feasible; the IA question is the real call.
- **Claude Code brief at `CLAUDE_CODE_PROMPT_home_about_learn.md` is stale.** Doesn't reflect v4 IA, separate /outrights /matches pages, burger nav, no-founder-names rule, or the wc-outright tabbed `/desk` track. Needs an update pass before any code agent touches it.
- **Production code lives in `/Users/adi/Documents/Claude/Projects/market_tips_ai-1`** per the workflow lock from this morning's sibling session. v4 handover is a spec output — Faktor (or Claude Code) ports it into that repo. Cowork stays in `prophet/` for specs.
- **`branding/locked/wordmark.svg`** still contradicts v4 — Adi's Claude.ai sync brought back the May 8 Source Serif lockup. Doesn't affect v4 (lockup is inlined) but contradicts `handover-v4/assets/`. Resolve before next brand iteration.
- **Market Tips AI dark-terminal alt-brand mockup** at `frontend/public/v2/home-markettipsai.html` — strategic question still open: real alt to evaluate, or pure exploration? "Tips" voice and Odds Primer voice rules are not co-existing brands.
- **The three home-v3-option-{a,b,c}.html mockups** in v2/ still hold pre-canonical phrasing ("Back it", "sit it out"). Frozen historical artifacts. Leave or move to `_archive/`.
- **`Odds Primer Design System/_nested_to_delete/`** still needs Finder drag-to-Trash (sandbox can't rm).

**Handoff for next session:**

If next session is brand/voice work — read the terminology lock above and `feedback_verdict_is_the_product.md`. Don't introduce gambling-promo words even in quoted negations. If next session is implementation — production code is in `market_tips_ai-1`, the v4 handover is the spec input; the stale Claude Code brief needs updating first. If next session is the Outright Winner / Match-tabs reconciliation — the wc-outright design at `Odds Primer Design System/mockups/wc-outright.html` and the v4 home at `frontend/public/v4/home.html` need to be reconciled into one canonical IA. If next session is a Faktor follow-up — handover went out as `oddsprimer-v4-handover.zip` + `handover-v4/README.md`; expect ping-backs on real domain, cookie banner persistence, newsletter provider pick, outright model timing.

---
## [2026-05-18 · Outright winner — design lock + mobile-first mockup] — Cowork

**Summary:** Adi asked to add an Outright Winner view alongside Matches, with Outright as the default until WC 2026 kicks off. I scraped Polymarket's `2026-fifa-world-cup-winner-595` event (43 nations, Spain 15.3% top, $271.4M vol, resolves Jul 20 2026), proposed a tab-based home (Outright | Matches) layered over the existing `/desk` shell, and surfaced three open calls via AskUserQuestion. All three locked on the maximal path. Built a desktop-leaning HTML mockup at `Odds Primer Design System/mockups/wc-outright.html`. Adi pushed back: not mobile-optimized. Rebuilt the file mobile-first — same DOM, three breakpoints (base / 600px / 900px), sticky tabs, horizontal-snap Picks carousel, stacked row-card ladder that swaps to a real `<table>` only at ≥900px.

**Decisions (locked 2026-05-18):**
- **Build the outright simulator before shipping the page.** Engine PR adds a Monte Carlo on top of the existing Elo model — 10,000 tournament rollouts → `outright_p` per team. Without this the Outright tab is a Polymarket mirror with no edge, which contradicts the verdict-is-the-product rule. Chosen over the "stub model, ship tracker" path.
- **Hero treatment = top 3 Picks by `edge_pp`.** Not the top 4 favourites. The page's reason to exist is the model's disagreement with the market, not a restatement of market consensus.
- **Default-flip mechanism = date-based env flag.** `DESK_DEFAULT_VIEW` derived from `WC2026_START_UTC`; server returns "outright" until 2026-06-11 kickoff, "matches" afterward. One env knob, no client date math, no deploy on launch day.
- **One home, two tabs.** URL `/desk` honours the default; `/desk/matches` forces the matches view. No separate top-level routes; the segmented tab strip sits below the masthead.
- **Outright is NOT a `MatchOutput`.** New `OutrightOutput` contract — N-way market, single resolution, one entry per team, lives at `data/output/football/outright/wc26-winner.json`. Needs its own ADR + schema entry before any code.

**Files shipped:**
- `Odds Primer Design System/mockups/wc-outright.html` — mobile-first standalone mockup. Masthead (compact bars+wordmark, UTC time right), edition strip ("31 days to opening match"), sticky tab strip (Outright 43 / Matches 12), event hero ("Who wins the World Cup?" + standfirst that names the 10k Monte Carlo), 3-up Pick slab (Brazil +3.5pp, Argentina +3.2pp, Germany +2.8pp — Germany's edge sits below the 3.0pp Pick floor and the card admits it), 43-row ladder of all PMK teams. Mobile = scroll-snap carousel + stacked row-cards with flame-tint fade on Picks. Desktop = 3-up grid + real table. ~1000 lines, no JS. Real Polymarket implied % numbers; Model % invented to make the disagreement story.

**Engine work this implies (not yet built):**
1. ADR + `OutrightOutput` schema in `desk/publish/contract.py`.
2. `desk/sports/football/outright.py` — bracket Monte Carlo. Open question for its brief: how to handle teams still in CONMEBOL/AFC qualification playoffs as of May 2026 (weight by qual probability vs. freeze field at draw date).
3. Verdict step reuses `desk/verdict/decide.py` thresholds (3.0 / 1.0 / -2.0 pp) unchanged — `model_p − market_p` math works on N-way too. Phase A.4 Avoid caveat applies less here because outright isn't zero-sum across visible sides (Yes/No each, sums <1).
4. Outright explainer reuses `voice.py` rules — templated copy in the same pattern as the match Pick stub.
5. Frontend: `DeskTabs.jsx`, `DeskOutright.jsx`, `OutrightLadder.jsx`. `DeskApp.jsx` reads `?view=` and a server-injected default; same path-routing pattern already in use (no router lib).
6. `DESK_DEFAULT_VIEW` flag in `desk/config.py` + a tiny `/api/desk/config` (or SPA bootstrap payload).

**Action Items:**
- [ ] **Adi: green-light the outright simulator brief** — once approved I'll draft `THE_DESK_OUTRIGHTS_SIM_BRIEF.md` (inputs, qualification handling, sim count, validation against closing-market baseline) before any code goes in. Same shape as `THE_DESK_PR_BACKTEST_BRIEF.md`.
- [ ] **Adi: review the mockup on phone.** Mobile-first rebuild needs validation at 375px before this design is handed off.
- [ ] **Adi: decide on the Avoid column for Outright.** With normalised market % across 43 sides, Avoid almost never fires (the Phase A.4 single-venue problem applies). Keep the column for parity with match page, or drop it.
- [ ] **Adi: decide on the "two Picks + one watch" vs "three Picks" hero treatment.** Mockup stretches the 3.0pp threshold to show three Pick cards; in a real run Germany would be a near-miss, not a Pick.

**Open Threads (carry to next session):**
- This is design-only. No engine work started, no React port started. The mockup is a standalone HTML in the design system folder, not in `frontend/public/v2/`. When the simulator lands, the React port follows the same path-routing pattern used today by `DeskApp.jsx`.
- Outright tab co-exists with the article-style home from 2026-05-13. Open question: does `/desk` become a tabbed view (Outright | Matches), or does the home stay article-style with `/outrights` and `/matches` as separate pages it links to? Today's design lands the tabs under `/desk` specifically, leaving the article-style `/` home untouched. Possible alignment work later.
- Carry-overs from previous sessions still open: verdict-teaching variant A/A+C/A+B+C, Market Tips AI direction, stale Claude Code brief refresh, delete `_nested_to_delete/`, self-host brand fonts.

**Handoff for next session:**
The Outright design is locked. The natural next step is the simulator brief — that gates the `OutrightOutput` contract, which gates everything else. Mockup at `Odds Primer Design System/mockups/wc-outright.html` is the visual reference. New feedback rule in Cowork auto-memory: mobile-first is non-negotiable for all UI work going forward. No code state to restore.

---
## [2026-05-18 · Cowork ↔ Claude Code workflow lock — spec here, code there; market_tips_ai-1 read-only] — Cowork

**Summary:** Short session, no build work. Adi clarified that the working code lives in `/Users/adi/Documents/Claude/Projects/market_tips_ai-1` and asked me to remember never to delete or change anything in that folder. I saved the rule to auto-memory, verified I have full read access to the repo (7,760 files outside `node_modules`/`.git`: Next.js app, `desk/` engine, `lib/`, `components/`, `supabase/migrations/`, `docs/`, `tasks/`, both CLAUDE.md files), and confirmed the intended workflow: spec/think in Cowork against the real repo state, hand off to Claude Code for implementation.

**Decisions (locked 2026-05-18):**
- **`market_tips_ai-1` is read-only from Cowork.** I read it freely to ground specs in real file paths and existing patterns, but I do not edit/move/delete anything there unless Adi explicitly points at a file.
- **Workflow split.** Cowork = specs, briefs, ADRs, sprint plans, research, design work. Claude Code = implementation against those specs (branch, code, run gates, open PR). Spec outputs land in `prophet/` (or wherever fits), not inside `market_tips_ai-1/`.

**Files shipped:**
- Auto-memory: `spaces/.../memory/feedback_market_tips_ai_folder.md` — feedback entry capturing the read-only rule with Why / How to apply. Indexed in `MEMORY.md`.

**Project Updates:**
- None to repo code or docs. The session's only persistent output is the memory entry above; everything else was confirmation of state.

**Action Items:**
- None outstanding from this session.

**Open Threads (carry to next session):**
- Carry-overs from 2026-05-13 still open: pick verdict-teaching option (A / A+C / A+B+C); Market Tips AI direction (thought experiment vs real alt brand); stale Claude Code brief at `CLAUDE_CODE_PROMPT_home_about_learn.md` needs an update pass for article-style IA + /outrights /matches routes + burger nav + no-founder-names rule; delete `Odds Primer Design System/_nested_to_delete/` in Finder; self-host brand fonts; outright-engine scope decision for Faktor build.

**Handoff for next session:**
The workflow is now wired: spec here, code in Claude Code, never touch `market_tips_ai-1` from Cowork. When Adi opens the next session, the natural first move is one of (a) draft a spec for one of the open carry-overs above — most leverage is on the stale Claude Code brief refresh, since that unblocks the React port of the v2 mockups — or (b) pick one of the May-13 decisions still pending (verdict-teaching variant, Market Tips AI brand direction). No code state to restore; the repo is unchanged.

---
## [2026-05-13 · Home-v3 mockup pass — article-style IA, brand sync, verdict-teaching options, alt-brand mockup] — Cowork

**Summary:** Long session, lots of iteration. Started by building the v2-plan homepage (home-v3) from the homepageplanv2 brief — Outright Winners + Today's Board + How we work + Featured columns + Newsletter + Footer + sticky mobile bar. Then About page (anonymous role cards — no founder names) and Learn index + 3 primer articles. Brand-synced the May 12 wordmark update (Source Serif 4 800 → Inter Tight 700 + tagline "The AI sports desk for market edge"); archived the old May 8 lock files; cleaned up a partial Claude.ai → Cowork export that included divergent versions of mockups. Iterated mobile UX (burger → pill nav → both with different scopes). After Faktor call, pivoted home to article-style: removed the full Outright Picks + Today's Board sections from home and replaced with two article preview cards linking to NEW /outrights.html and /matches.html pages; moved About + Learn into a burger menu (top-right of masthead, `<details>` no-JS). Built three verdict-teaching mockup options (A/B/C) with a floating A/B/C switcher so Faktor can compare. Built a Market Tips AI alt-brand mockup (dark terminal × fintech, electric green/AI-purple, "tips" voice, AI confidence scores) as a max-contrast brand comparison.

**Decisions (locked 2026-05-13):**
- **Home IA is article-style.** Two article preview cards (Outright winners + Upcoming matches) replace the full sections on home. Full content lives on /outrights.html and /matches.html. Followed Faktor's call ask.
- **No founder names on the public site.** About's "Who runs this" section uses anonymous role cards — "The engineer" / "The editor". Footer copyright is `© 2026 Odds Primer.` (not "Adi Dagan trading as…"). Memory updated: legal_status memory still says sole-trader is the legal framing, but the public-facing site never names the operator.
- **Canonical lockup on every page masthead.** Earlier iteration had wordmark-only on About/Learn and canonical (with tagline) on home only — caused screen-jump on nav. Lockup is now identical across all 8 pages so masthead height is stable on navigation. Mobile tagline visibility restored (removed the under-520px display:none rule).
- **Tagline stretches from glyph left edge.** The design-system spec has `padding-left: 50px` so tagline aligns under wordmark text only — that proportion only works at 38px display size. At the 22px masthead size, padding-left: 0 lets the tagline span the full lockup width naturally. Document-system spec is unchanged; masthead implementation overrides for the smaller size.
- **Burger holds About + Learn only.** Primary nav (visible inline + pill on mobile) carries Home / Outright winners / Upcoming matches. Burger button sits top-right of masthead, all viewports. `<details>/<summary>` pattern — no JS.
- **Outright picks are mocked, model is v0.1.** The Desk doesn't currently model outright probabilities (per `THE_DESK_SPEC.md` §6). The home/outrights pages show three hardcoded picks (France/Argentina/Brazil) with a footnote dagger explicitly flagging the engine is v0.1, in production for v1.2.
- **Brand v3 wordmark + tagline lock-in confirmed.** Inter Tight 700 wordmark, letter-spacing −0.022em at 22px masthead, −0.025em at 38px display; tagline "The AI sports desk for market edge" in Source Serif 4 italic with flame on "AI" and "market edge". May 8 wordmark (Source Serif 4 800) archived to `branding/exploration/_archive_2026-05-08-wordmark/`.

**Files shipped:**
- `frontend/public/v2/home-v3.html` — rebuilt three times this session, final state = article-style home with two preview cards, canonical lockup, pill+burger nav, sticky mobile bar linking to /matches.
- `frontend/public/v2/about.html` — anonymous role cards, sticky side-rail TOC, five anchored sections.
- `frontend/public/v2/learn.html` — three numbered primer cards index.
- `frontend/public/v2/learn-what-is-a-prediction-market.html` — 3-min primer, pullbox.
- `frontend/public/v2/learn-how-prices-are-set.html` — 5-min primer with American-odds → cents conversion table + worked Brazil-22¢/25¢ example.
- `frontend/public/v2/learn-is-it-legal.html` — 4-min primer with venue × regulator × legal-frame table + "we're not lawyers" notice box.
- `frontend/public/v2/outrights.html` — NEW page. Outright picks (France/Argentina/Brazil) + "Where the field stands" market-consensus bar/cards.
- `frontend/public/v2/matches.html` — NEW page. Fixture board (Groups F/A/B, 8 matches) + verdict-key legend + summary strip.
- `frontend/public/v2/home-v3-option-a.html` — verdict-led standfirst (cheapest).
- `frontend/public/v2/home-v3-option-b.html` — verdict-key strip under hero (medium).
- `frontend/public/v2/home-v3-option-c.html` — lead-verdict block above article cards (substantive). All three carry a floating A/B/C switcher (bottom-right) and have `colors_and_type.css` inlined so each is shareable as a standalone file.
- `frontend/public/v2/home-markettipsai.html` — alt-brand mockup. Dark `#0B0E13` background, Inter-only typography, electric green (`#00E676`) + AI-purple (`#7C5CFF`) accents, "tips" voice, AI confidence scores, hit-rate band, "Trade now on Polymarket ↗" CTAs.
- `CLAUDE_CODE_PROMPT_home_about_learn.md` — brief for porting the v2 mockups into the React app. Hard frontend-only constraints; custom-pathname routing pattern; no new npm deps; `package.json` unchanged; `git diff --stat origin/staging…HEAD` must show only `frontend/` changes. **Stale vs current state** — still describes all-on-home IA, not article-style + separate /outrights /matches pages, and doesn't reflect burger menu or A/B/C verdict-teaching choice.
- `Odds Primer Design System/branding/exploration/_archive_2026-05-08-wordmark/` — archived old wordmark.svg, glyph-bars.svg, bars-locked-v2.html, odds_primer_logo.png + README explaining supersession.

**Project Updates:**
- New auto-memory `feedback_verdict_is_the_product.md` (Cowork space): Pick/Pass/Avoid is the wedge; homepage must lead with it explicitly; "we compare prices and explain" framing is incomplete without naming the verdict.
- Brand sync from Claude.ai → repo: nested duplicate folder reconciliation. Promoted `assets/wordmark-tagline.svg` and `mockups/logo-tagline.html` to top level. Replaced top-level wordmark.svg + 3 mockups with the May-12 versions. Kept top-level `mockups/verdict-explore/notes.md` (it had a 2026-05-05 "View source on" update that the Claude.ai export had reverted to "Open on"). Nested duplicate folder renamed to `_nested_to_delete/` — bash sandbox can't `rm` it (macOS quarantine attrs); Adi to drag-to-Trash in Finder.

**Action Items:**
- [ ] **Adi: pick verdict-teaching option** (A / A+C recommended / A+B+C canonical) from the three option mockups → merge into canonical `home-v3.html`.
- [ ] **Adi: decide Market Tips AI direction.** Dark-mode alt-brand shipped; is it a thought experiment or a real alt to evaluate? If real, also build a light "Robinhood-on-cream" variant for a 3-way comparison. Strategic flag: the "tips" word in MarketTipsAI naming directly contradicts Odds Primer's anti-tipster voice rules — these are not compatible co-existing brands, they're a choice.
- [ ] **Adi: update Claude Code brief** to match current state — article-style home, separate /outrights + /matches React routes, burger nav pattern, no founder names rule. Currently the brief still describes the pre-Faktor-call IA.
- [ ] **Adi: delete `Odds Primer Design System/_nested_to_delete/`** in Finder (sandbox can't rm — macOS quarantine attrs).
- [ ] **Adi: self-host brand fonts** (Inter Tight, Source Serif 4, JetBrains Mono `.woff2`) under `Odds Primer Design System/branding/fonts/` and `@font-face` them from `colors_and_type.css`. The Claude.ai design-system preview shows "Missing brand fonts" warning; the repo has the same gap — falling back to Google Fonts CDN at runtime. Self-hosting would (a) match the Claude.ai preview exactly, (b) remove the third-party runtime dependency.
- [ ] **Adi: optionally inline CSS across all `v2/` mockups** (not just the option-A/B/C/markettipsai files) so any single file is shareable standalone, like Faktor's Option C breakage today. Or commit to always sharing the whole folder.
- [ ] **Adi: respond on whether outright-engine work is in scope** for the Faktor build. Mockup currently shows v0.1-flagged picks. Spec'd in `THE_DESK_OUTRIGHTS_SPEC.md` but parked.

**Open Threads (carry to next session):**
- Verdict-teaching option not yet picked. My recommendation stands: **A+C** — standfirst rewrite that names Pick/Pass/Avoid, plus a lead-verdict block above the article cards demonstrating one in action. A+B+C is canonical magazine teaching but adds visual weight that may compete with the article previews.
- Market Tips AI exists in two states: (a) the May-8 internal MVP deck framing — "DraftKings of soccer prediction markets," CPA-affiliate, screenshot factory; (b) today's dark-terminal mockup — AI-led, confidence scores, hit-rate band. If MarketTipsAI is real, "67% hit rate" and per-pick AI-confidence scores are load-bearing claims that don't yet exist in The Desk's contract — they're feature work.
- Claude Code brief is stale on three dimensions: IA (article-style), routes (/outrights + /matches), nav (burger). Don't hand to Claude Code without an update pass — it would produce something divergent from the current mockups.
- Article preview cards on home currently DON'T teach the verdict. A newcomer sees "3 picks · 1 avoid" without knowing what those words mean. Verdict-teaching option (above) closes this gap.
- Outright engine is v0.1 — `THE_DESK_OUTRIGHTS_SPEC.md` and the v2 plan §3.2 both flag this. Mockups carry a † footnote acknowledging it; production needs the engine work before any "outright pick" rendering is honest.
- Tagline indentation: design-system preview shows `padding-left: 50px` (under wordmark text) at 38px display size; masthead uses `padding-left: 0` at 22px size so the tagline stretches across the full lockup. Both look right at their respective scales but it's an implicit override worth documenting in the design system if the spec page ever ships in a different size.

**Handoff for next session:**
The mockups are at `frontend/public/v2/`. Eight Odds Primer pages share canonical chrome (masthead with bars glyph + Inter Tight wordmark + flame tagline, edition strip, pill+desktop+burger nav, footer): `home-v3.html` (article-style home with two preview cards), `outrights.html` and `matches.html` (the full content pages those cards link to), `about.html` (anonymous), `learn.html` + three primers. Three verdict-teaching variants of the home live at `home-v3-option-{a,b,c}.html` with a built-in switcher — Adi to pick one and merge to canonical. One alt-brand mockup at `home-markettipsai.html` — dark terminal × fintech, max visual contrast to Odds Primer. Claude Code brief at repo root `CLAUDE_CODE_PROMPT_home_about_learn.md` is stale; needs an update pass before the React port. The big strategic question still open: does Odds Primer's editorial verdict register beat Market Tips AI's AI-tipster register for conversion in the Faktor / Adi judgment? The mockups make the contrast visible — answer is a brand decision, not a build one.

---
## [2026-05-07 · B2C legal pages — Privacy + T&Cs (sole-trader framing)] — Cowork

**Summary:** Adi shared a screenshot of his B2C task list (Privacy Policy, T&Cs, 404, Event details, Site sweep) and asked for help completing them. Scoped the work via AskUserQuestion: Privacy + T&Cs first; copy (md) + design-system HTML mockup; generic placeholder jurisdiction. Built v1 with `[LEGAL ENTITY NAME]` brackets. Adi flagged "we don't have a legal entity setup yet" — pivoted to **sole-trader framing**.

**Decisions (locked 2026-05-07):**
- **Operating model for B2C launch:** Adi Dagan trading as "Odds Primer" — sole trader, pre-incorporation. Adi is publisher, operator, and (for GDPR) data controller as a natural person. Personal liability — fine for a free educational beta, blocker for payments / B2B / paid acquisition.
- **Liability cap (free service):** greater of (a) fees paid in last 12 months [£0], (b) `[AMOUNT, e.g. £100]`. Replaces the original "[AMOUNT / 12 months' fees]" boilerplate.
- **Bracketed placeholders that remain genuinely unknown:** `[CITY, COUNTRY]`, `[SERVICE ADDRESS]`, `[JURISDICTION]`, `[VENUE]`, liability `[AMOUNT]`. Everything else now reads with real names.
- **Visual treatment:** mocked up to match `mockups/fixtures-board.html` chrome — top-rule masthead, eyebrow-led title block, two-column body (sticky TOC sidebar + serif prose with mono section numbers), warm-paper placeholder banner with flame top border, footer cross-link to sibling page.

**Files shipped:**
- `Odds Primer Design System/mockups/legal/privacy-policy.md` — 13 sections, sole-trader framing.
- `Odds Primer Design System/mockups/legal/privacy-policy.html` — full design-system mockup (CSS variables only, no hardcoded hex).
- `Odds Primer Design System/mockups/legal/terms-and-conditions.md` — 15 sections.
- `Odds Primer Design System/mockups/legal/terms-and-conditions.html`.

**Project Updates:**
- New auto-memory `project_prophet_legal_status.md` (Cowork space): pre-incorporation, sole-trader for B2C, flagged as a blocker for payments / B2B / paid acq.

**Action Items:**
- [ ] Build 404 page in same design language — Claude (next session, or this one if time).
- [ ] Build Event details page mockup — Claude.
- [ ] Site sweep (whatever that means — clarify with Adi) — TBD.
- [ ] Pick a UK mail-forwarding service for `[SERVICE ADDRESS]` (~£10–25/mo) — Adi.
- [ ] Decide governing law / jurisdiction (likely UK as default) — Adi + counsel.
- [ ] Decide liability cap amount — Adi + counsel.
- [ ] Pencil UK Ltd incorporation for post-WC window (~ post 2026-07) — Adi.

**Open Threads (carry to next session):**
- Tax residence / operating jurisdiction not yet confirmed in any conversation. Defaulted to UK in the rewrite — flag for explicit confirmation.
- WC mockups from 2026-05-06 still awaiting Adi's review (hero / OG cards / match dossier).
- Masthead wordmark weight (700 vs 750 vs 800) still TBC from 2026-05-05 logo lock.
- Three B2C tasks (404, Event details, Site sweep) still pending — Privacy + T&Cs done.

**Handoff for next session:**
Privacy + T&Cs are at `Odds Primer Design System/mockups/legal/`. Open them in either order (they cross-link). Brackets that remain are genuinely unknown — counsel/jurisdiction decisions, not fill-in-the-name. When Adi incorporates, the swap is mechanical: publisher line + meta strip "Status" row + contact block.

---
## [2026-05-06 · WC 2026 edition framing + three cover prototypes] — Cowork

**Summary:** Resolved the WC 2026 edition design problem at the strategic level, then built three working prototypes. After seven rounds of rejected logo modifiers (quiet attachments → louder banners → FIFA-inspired "26") I diagnosed the whole approach as off — we're a publication that *covers* the World Cup, not the event itself. ChatGPT review crystallized the framing: **"Odds Primer is the masthead; World Cup 2026 is the issue."** Cover treatment, not logo treatment. Locked logo stays untouched. Built three cover-system prototypes, then ran a refinement pass to tighten edition labeling, strip third-party venue colors, and enforce flame discipline.

**Decisions (locked 2026-05-06):**
- **WC 2026 edition is an editorial franchise, not a sub-brand or campaign skin.** Logo is not modified. Edition lives in layout hierarchy: recurring strips, rules, datelines, issue labels, match cards, chart-led covers.
- **Edition labeling rule:** "World Cup 2026" in navy, weight 700, slightly stronger tracking. Surrounding edition copy in graphite/ink-soft. Warm-paper strip background acceptable. Never make the whole edition label flame.
- **Venue dot rule:** all venue dots are neutral. Solid navy = prediction market (Kalshi, Polymarket); outlined navy = sportsbook (DraftKings, FanDuel, BetMGM, Caesars). No third-party brand colors anywhere.
- **Best-price copy semantics tightened:** "Cheapest" → "Lowest listed"; "Best after fees" → "Best net price". Always paired with explainer "Net price includes fees and venue spread where known."
- **Editorial byline:** "Odds Primer Editorial" (not "Faktor Editorial").
- **Flame discipline:** one dominant flame moment per module (best-price underline OR key spread OR small editorial marker). Body-text `em.flame` is gone — body emphasis uses `em.tnum` (mono numerics) instead.
- **Hard anti-patterns** (locked in `branding/wc-edition-brief.md`): no trophy, no "26" digit overlays, no host-country flag palette, no soccer-ball/pitch/badge/crest decoration, no tournament confetti, no "WC Edition" baked into the logo, no secondary mark, no green for "best," no sportsbook-ticker live states.

**Top 3 surfaces (ranked by impact):**
1. Homepage / WC hub hero — broadsheet front page. Locked logo + warm-paper edition strip + chart-table hybrid hero ("The same World Cup question has six different prices") + 6-venue comparison + footnote stats.
2. 1200×630 OG / social cards — magazine cover, three example cards (outright spread / opening match / dark launch announcement). One headline, one tabular-number fact, no FIFA imagery.
3. In-article match dossier module — embedded in longform article, vertical edition rail "WC 2026 · MARKET BRIEF", 6-row venue table with flame-underlined best price, compact variant for sidebars.

**Files shipped:**
- Strategic doc: `Odds Primer Design System/branding/wc-edition-brief.md` (locked framing + treatment specs + magazine references + anti-patterns).
- ChatGPT prompt + logo PNG (for cross-LLM review): `branding/chatgpt-wc-edition-prompt.md`, `branding/odds_primer_logo.png` (rendered hi-res, Source Serif 4 ExtraBold via fontTools woff2→ttf conversion).
- Three working prototypes: `mockups/wc-hub-hero.html`, `mockups/wc-og-card.html`, `mockups/wc-match-dossier.html` — all post-revision-pass complete.

**References to pattern-match:** NYT Magazine World Cup Issue (Bichler/Aguila), The Atlantic 2019 redesign, France Football redesign (République Studio), The Athletic special editorial packages.

**Action Items:**
- [ ] Review the three updated mockups and react — Adi.
- [ ] Decide masthead wordmark weight 700 vs 750 vs 800 (carried over from 2026-05-05 logo lock).
- [ ] Outlined-paths variant of `wordmark.svg` for native rasterizers (carried over).
- [ ] Once Adi signs off on the visual language, port the match-dossier into a `MarketDossier.jsx` (or `MatchDossier.jsx`) component in `ui_kits/web/`.
- [ ] Propagate the design-system rules locked today (edition labeling, venue dots, "Lowest listed/Best net price" copy, flame discipline) into `README.md` and `SKILL.md` so future agents inherit them.

**Open Threads (carry to next session):**
- Faktor's Track B (B2B MM) still parked. No movement today.
- Recommendation engine: Faktor blockers from 2026-05-03 still open (Wikipedia Elo, Polymarket slug map, injury sourcing decision).
- Etsy / EdgeGridStudio: had first Kalshi Sports Tracker buyer this morning; Adi planning a check-in DM. (Outside Prophet scope but flagged in session.)

**Handoff for next session:**
The three WC mockups are ready for Adi's read. Open them in this order: hero → OG cards → match dossier. The match dossier is the one closest to becoming a real component — port it into `ui_kits/web/` once the visual lands.

---
## [2026-05-05 evening · logo locked v2 + design system propagation] — Cowork

**Summary:** Locked the Odds Primer logo end-to-end. Explored 4 brand directions (bars, typographic, footnote dagger, quiet monogram) → chose bars → six bar iterations → first ChatGPT review picked A2 (caret) + A5 (meaningful heights) cross-breed → built synthesis → Adi rejected the caret ("not sure I like the arrow on top of the orange bar") → tested 5 caret-alternatives → Adi picked **bare** → second ChatGPT review flagged the wordmark as too SaaS, the masthead live dot as too sportsbook, and "Open on" as too transaction-adjacent → Adi accepted variant D (Source Serif 4 800, 8% smaller wordmark, glyph-led) with three production tweaks (11px gap, no live dot, "View source on" copy). Then propagated everything through the design system in one pass.

**Decisions (logo locked v2 · 2026-05-05):**
- **Glyph:** four bare bars on a navy baseline rule, heights map to real probabilities 22 · 38 · **65** · 30 (third bar in flame). No caret, no overscore, no underline. ViewBox `0 0 56 50`. Favicon falls back to a stocky trio at 16px (viewBox `0 0 48 44`, heights 18/34/24).
- **Wordmark:** Source Serif 4 800, letter-spacing −0.012em, OpenType `ss01` on. Glyph-led: 11px gap from glyph to wordmark; wordmark 8% smaller than v1.
- **Masthead:** glyph 42px tall, wordmark 18px, no flame "live" dot. Live state is plain mono "FRA v ARG · live."
- **Venue handoff phrase changed system-wide:** "Open on [venue] ↗" → "View source on [venue] ↗" (citation, not destination).

**Files shipped:**
- Assets: `assets/glyph-bars.svg`, `assets/wordmark.svg` (locked geometry; wordmark.svg uses inline `<text>` with Source Serif 4 — works in browsers, needs outlined-paths variant for native rasterizers).
- Code: `ui_kits/web/Wordmark.jsx` (heights, serif font, weight 800, glyphSize prop for masthead override), `ui_kits/web/Masthead.jsx` (flame dot removed, `<Wordmark size={18} glyphSize={42} />`).
- Docs: `README.md`, `SKILL.md`, `ui_kits/web/README.md` — wordmark spec + venue phrase + logo moved out of "open items."
- Previews: `preview/glyph-bars.html`, `preview/wordmark.html`, `preview/buttons.html`.
- Mockups: `mockups/fixtures-board.html`, `mockups/verdict-explore/{index,01-stamp}.html`, `mockups/verdict-explore/notes.md`.
- Spec page: `branding/bars-locked-v2.html` (production reference; supersedes `bars-locked.html`). Full exploration trail kept in `branding/`.

**Action Items:**
- [ ] Pick masthead wordmark weight (700 vs 750 vs 800) — currently 800 in code. Adi · §02 of `bars-locked-v2.html`.
- [ ] Outlined-paths wordmark.svg for native rasterizers (social cards, email) — needs a design tool. Adi or designer.

**Open Threads:**
- WC 2026 edition addition to the logo — Adi asked next, will start the conversation in the next session.
- Standalone branding/* exploration files kept as historical record; `_DELETE_ME_duplicate_byte_identical_to_parent/` folder still untouched (separate cleanup task).

---
## [2026-05-03 evening · recommendation engine design + 72-match prototype] — Cowork

**Summary:** Designed and prototyped the AI recommendation engine for Prophet/Odds Primer. The brief: AI-based smart-trade recommendations as the next product layer. Surfaced and resolved the tension with the existing "educational, anti-gambling-promo" positioning — Adi clarified the AI *is* the educational layer (the model produces a probability and a teaching blurb; comparison to market is done in the display, not the model). Built the design doc, vetted 12 sports-data sources, ran an end-to-end test on Mexico v South Africa, then expanded to all 72 group-stage matches. Locked the late-binding rule (weather + injuries only enter the model inside T-5 days). Output is a four-tab workbook for Faktor with Schema, Matches, Blurbs, and Open questions tabs.

**Decisions:**
- **Engine architecture LOCKED (5 layers):** ingest → feature store → model → LLM explainer → display. Markets feed display only, never the model. Educational story is honest because we never look at market prices to generate the model output.
- **Model approach v1:** Elo prior + home advantage (+75 if true host country) + altitude bonus (computed from venue elevation). Dixon-Coles deferred to v2 once tournament data arrives. Deliberately simple in v1 — engineering work is in the data, not the math.
- **Data sources greenlit:** football-data.org (free, WC permanent, 10 req/min), API-Football ($19/mo, richer H2H + injuries), StatsBomb Open Data (free historical xG for training set), World Football Elo via **Wikipedia data module** (NOT eloratings.net — JS-rendered, blocker), OpenWeatherMap (1000 calls/day free). Markets via Kalshi Events API + Polymarket Gamma API.
- **Sources rejected:** Understat (top-5 European leagues only — not international), SofaScore/FotMob (aggressive bot protection), ESPN hidden APIs (no SLA), Pinnacle/sharp odds (deliberately excluded — would taint editorial story).
- **Late-binding rule LOCKED:** weather + injuries only enter the engine inside the final ~5 days. Pre-window the model runs on stable inputs only (Elo, FIFA rank, form, home/altitude). Reason: 38-day weather forecasts are noise; injuries 30+ days out rarely survive to match day. Saved to auto-memory as `feedback_late_binding_features.md`.
- **Fixture source resolved:** the games we care about are the ones priced as markets — fixture list comes from Kalshi/Polymarket, FIFA site is the metadata authority (venue, kickoff, group). API-Football *not* needed for fixtures.
- **Bespoke vs template blurbs deferred:** decide after Faktor wires the Haiku-explainer step. v1 plan is template-everywhere via Haiku; bespoke pickup only on highest-traffic matches.

**Action Items (Faktor blockers):**
- [ ] Confirm Wikipedia data module as Elo source — Faktor + Adi
- [ ] Build Polymarket fixture-slug map (gamma slug lookup returned empty in test) — Faktor
- [ ] Decide injury data sourcing: manual ops (5 min/day) vs scrape vs SportMonks paid (EUR 69-129/mo) — Adi
- [ ] Wire up Haiku-explainer step, test on opening weekend, compare to bespoke — Faktor
- [ ] Confidence-band thresholds — Adi
- [ ] Refresh Elo numbers closer to kickoff (data module currently 19-Jan-2026 — 3.5 months stale) — Faktor

**Project Updates:**
- Recommendation engine added as new product layer. Strengthens "AI is the educational layer" positioning, doesn't reverse the educational-oddschecker scope.
- WC 2026 group-stage fixture list (72 matches) and team ratings (48 teams) gathered and locked.

**Artifacts created (all in `/Users/adi/Documents/Claude/Projects/prophet/`):**
- `RECOMMENDATION_ENGINE_DESIGN.md` — 1-page design doc with the late-binding rule baked in
- `sports_data_sources_vetting.xlsx` — 2-tab vetting (greenlit / optional / avoid), 12 sources
- `test_mexico_v_south_africa.md` — end-to-end engine dry run on the WC opener
- `faktor_engine_workbook.xlsx` — 4-match spec workbook (Schema + Matches + Blurbs + Open questions)
- `faktor_engine_workbook_full.xlsx` — full 72-match expansion, T-38 fundamentals run, 10 bespoke blurbs + 62 templated, 12 open questions for Faktor

**Key model results (worth carrying forward):**
- **Mexico v South Africa** at Azteca: model 74/18/8, market 62/24/16. The 12-point gap is the market's collective injury haircut on Mexico (Malagón Achilles, Romo, Chávez ACL, Huerta, Huescas, Giménez doubt). Editorial story is *in the gap*, not in chasing edge.
- **USA v Paraguay** at SoFi: Paraguay's Elo (1833) is actually higher than the USA's (1747). Even with +75 home advantage, model lands 35/28/37 — slight Paraguay edge. Most surprising opening-weekend result.
- **Spain v Saudi Arabia** at Atlanta: 83/14/3 — biggest favourite call in the opening matchday.
- Six teams confirmed via late playoffs (Czech Republic, Bosnia, Turkey, Sweden, Iraq, DR Congo) — ratings still settling. Flagged as "low confidence" in the workbook.

**Operational findings to flag for Faktor:**
- eloratings.net is JS-rendered → use Wikipedia's `Module:SportsRankings/data/World_Football_Elo_Ratings` (plain wikitext, version-controlled)
- Polymarket Gamma API direct slug lookup unreliable — pre-build the slug map at tournament start
- Injury data is the hardest input — no good free API; manual ops or paid SportMonks WC plan are the realistic paths

**Open Threads (carry to next session):**
- **NEXT TASK — engine-to-site delivery mechanism (flagged by Adi end of session, 2026-05-07 evening).** How does the engine output reach Faktor's platform? Real options: (a) **pull model** — we host JSON/API at a URL Faktor's site fetches on a cron, (b) **push model** — engine POSTs to Faktor's API on each refresh, (c) **shared database** — engine and site both read/write to the same Postgres/Supabase, (d) **static injection** — Adi manually pastes the workbook output into the CMS each matchday. Decision affects: where the engine runs, who owns the infra, refresh cadence, fail-quiet behaviour, and how late-binding refreshes (T-5 weather/injuries, T-1h confirmed XI) propagate. Discuss with Adi before any more building. Adi's framing: "I need to be able to produce the output of this engine so he can pull it — or that I inject it."
- Bespoke vs template blurb depth decision pending Haiku-explainer test
- Sportsbook anchor as silent sanity check (Pinnacle implied prob) — engineer-only debug feature, not user-facing
- Comparison-view UI when model and market agree (Mexico-SA test showed agreement is itself a teaching moment)
- Knockout rounds not modelled (TBD teams)
- Track B (B2B MM) untouched today — 30-day market test still ending ~2026-05-22

**Output schema for site injection (locked late 2026-05-03):** the engine produces three rendered text fields per match — `match_title` (formatted as "Home v Away · {hook}"), `short_summary` (1-2 sentences, no probabilities — those render via separate UI components), `full_blurb` (60-90 words, includes probability and drivers). These are the public-facing text fields injected into the site. Schema tab and Blurbs tab in `faktor_engine_workbook_full.xlsx` updated to reflect this. Bespoke entries for matches 1-10 (e.g. "Sixteen years on", "The Elo shock", "2022 ghosts"), template generators for 11-72.

**Handoff for next session:**
Adi reviewing the full 72-match workbook overnight. Faktor will get the design doc + workbook + open questions tab. First Faktor decisions are blockers (1-3 above): Elo source, slug map, injury sourcing. Once those land, build Haiku explainer step and compare output to the 10 bespoke blurbs to decide whether the engine ships unattended or needs human pickup for the WC.

---
## [2026-05-02 evening · branding research] — Cowork

**Summary:** Brand-direction session. Adi handed over a structured brief for a 20-site competitive landscape (EU-weighted, four buckets) to decide which palette direction to ship for the WC landing page. Built the research end-to-end — Playwright Chromium screenshots at 1280×800, palette extraction (PIL median-cut + saturation-weighted dedup, then visual curation against cookie-modal noise), register/type/mode/audience scoring, cluster-map placement on publication↔product / muted↔bold axes — and produced a four-page `landscape.pdf` with verdict and receipts. Recommended Direction B "Floodlight" (ink-black + warm parchment + sodium-amber dark-mode editorial, the only genuinely empty quadrant in the field). Adi pushed back: liked Coaches' Voice's clean-white + saturated-orange + modern-sans register. Refined to a Direction D "Tactical." Adi then locked: keep the orange, add dark blue, asked for a Claude Design prompt to try mockups. Authored the prompt with palette `#FFFFFF` paper / `#0E2240` ink-navy / `#FF5A1F` flame-orange / `#3A3F47` graphite / `#F0ECE2` warm rule, modern sans throughout, reticle motif retained.

**Decisions:**
- **Palette direction LOCKED:** white paper + dark navy ink + flame-orange accent. Modern sans throughout (no broadsheet serif). Reticle/scope motif retained as system glyph.
- **Specific hex picks (provisional, to be battle-tested in mockups):** paper `#FFFFFF`, ink-navy `#0E2240`, flame-orange `#FF5A1F`, graphite `#3A3F47`, warm rule `#F0ECE2`. Navy may swap to `#112038` (deeper) or `#14264A` (bluer) if `#0E2240` reads too "broadcast TV" on a real masthead.
- **REJECTED palette directions** (proposed in landscape.pdf): A "Broadsheet" (cream + ink + oxblood — too close to The Athletic / Set Pieces); B "Floodlight" (dark mode + sodium amber — Adi's preference is clean-white-with-bold-orange, not dark-mode-editorial, despite the dark-mode quadrant being genuinely uncrowded in the sample); C "Pitch" (cream + moss + signal-orange — extension of original Scout palette).
- **Coaches' Voice is the closest peer reference** in the sampled field — Adi explicitly "likes" it. Cluster-map quadrant we now occupy: publication, slightly-bold. Currently only Coaches' Voice sits there, pitched at coaches not fans — viable claim for Prophet.
- **Mockup exploration delegated to Claude Design.** Authored a self-contained prompt (saved as `branding/claude_design_prompt.md`) requesting four compositions: homepage hero, single scout report page, logo lockups, identity sheet.
- **Two substitutions in the 20-site sample:** Smarkets geo-blocked (404 from sandbox; brand has rebranded to "Smarkets Predictions") → replaced with Betfair Exchange. Tifo Football's domain (tifofootball.com) has been taken over by an unrelated Thai gambling promo (UFABET) → replaced with Mundial Magazine. Both swaps preserve bucket counts.

**Action Items:**
- [x] Run 20-site competitive landscape research with screenshots, palette extraction, scoring — Claude
- [x] Produce `landscape.pdf` — 4 pages: grid · cluster map · verdict · receipts — Claude
- [x] Author Claude Design prompt with locked palette — Claude
- [ ] **Try mockups in Claude Design** with the `claude_design_prompt.md` prompt — Adi
- [ ] Once mockups land, decide: ship as "The Scout" or use Read the Game with the Tactical palette — Adi + Faktor
- [ ] Battle-test `#0E2240` on a real masthead — swap to `#112038` or `#14264A` if it reads broadcast-TV — Adi (after seeing first mock)
- [ ] **Lock the brand name** before Monday for the WC landing page (still carries from prior sessions)
- [ ] Per-screen detailed design prompts (5 screens) — Claude (offered prior session, not yet built)

**Artifacts created this session (all in `/Users/adi/Documents/Claude/Projects/prophet/branding/research/` unless noted):**
- `landscape.pdf` — 4 pages: 20-site landscape grid, 2-axis cluster map (publication↔product / muted↔bold) with the empty dark-mode-editorial zone marked, three palette directions with brand-wearing mocks (Broadsheet / Floodlight / Pitch) + recommendation, full receipts table with method note.
- `data.json` — structured 20-site dataset (palette hex, register score 1–4, type pairing, default mode, audience signal, vibe summary, x/y cluster coordinates) for stress-testing the verdict.
- `screenshots/` — 22 PNGs (20 active + 2 substituted-out: smarkets 404, tifofootball domain-squat).
- `landscape.html` + `landscape_filled.html` + `_build_html.py` + `_makepdf.py` + `_capture*.py` + `_palette*.py` — research pipeline. Re-runnable.
- `branding/claude_design_prompt.md` — the locked-palette prompt for Claude Design (saved separately so it's findable next session).

**Key research findings (worth carrying forward):**
- **Crowded zones in football branding:** top-right (bold + product) is gambling promos + loud sports portals; bottom-right (muted + product) is utility/scoreboard SaaS (Pinnacle, OddsPortal, FotMob, Polymarket); bottom-left (muted + publication) is the B&W editorial corner (The Athletic, Mundial, Set Pieces).
- **White space:** dark-mode editorial is genuinely unowned — every football publication defaults to white paper, every dark-mode site in the field is gambling. Mid-left (publication, slightly bold) has only The Blizzard (cream + hot pink) and Scouted FC (deep red on white). Warm/muted with a non-default accent is uncontested.
- **Coaches' Voice cluster position:** ~(-0.4, +0.2) — publication-leaning but bolder than Athletic/Mundial because of the orange CTA system. Adi liked it because it combines clean modern editorial with a single saturated orange, which the rest of the field doesn't pair together.
- **What the locked palette gives up vs Floodlight:** the dark-mode-editorial empty quadrant. What it gains: a register that splits "premium publication" and "tactical tool" — closer to Prophet's actual wedge ("we tell you what to make of the data") than pure broadsheet authority.

**Open Threads (carry to next session):**
- **Brand name still not locked** — Read the Game / The Scout / Prophet / MarketTipsAI all in play. Carries from prior sessions. Mockups should test all three names.
- **Cut A vs Cut B unresolved** — drives most of the dev work. Carries.
- **Reversal of "no sports" rule unreconciled** — carries.
- **Track B (B2B MM)** untouched today — 30-day market test ends ~2026-05-22.
- **Per-screen detailed design prompts (5 screens)** — offered prior session, not yet built. Worth doing once Adi has chosen between Claude Design output and going to a designer.

**Handoff for next session:**
Adi will return after running the prompt through Claude Design. Expected feedback shape: (1) which navy reads best on the masthead (`#0E2240` baseline; alternates `#112038` deeper / `#14264A` bluer); (2) whether the modern-sans direction is right or whether something with a touch more editorial weight is needed for the wordmark; (3) whether to commit to "The Scout" or test "Read the Game" / "Prophet." Once those land, next deliverables: per-screen design prompts (5 screens — homepage, market detail, learn, movers, about), wordmark refinement, and the landing-page build. Brand has to be locked by Monday for WC landing page; the Claude Design pass is the gate.

---
## [2026-05-02 PM] — Cowork (affiliate-program scan)

**Summary:** Monetization research session. Scanned affiliate / referral / partner programs across prediction markets (Kalshi, Polymarket, PredictIt, Manifold, Limitless, Myriad, SX Bet, Drift BET, Augur) and brokerages with event-contract products (Robinhood Event Contracts, IBKR ForecastEx). Initial output was a long markdown doc — Adi pushed back ("too long, you should know it by now"), confirmed preference for xlsx on all comparison work going forward. Rebuilt as `AFFILIATE_PROGRAMS.xlsx` with Priority / Platform / Program / Commission / Attribution / Payout / Geo / Eligibility / Action columns + a Risks tab. Adi then pushed back on the unit economics ("payouts look small but Kalshi/Poly must have something working") — this surfaced the most important strategic insight of the session: public affiliate rates are deliberate filters, not the actual offer. Real money is in BD-negotiated KOL/Partner deals, 5-20x richer than self-serve. Closed with iGaming-vs-pred-market structural comparison anchored in Adi's Playtech background.

**Key strategic insights (the keepers):**
- **Public rates ≠ real rates.** Polymarket's open referral (30% lifetime, 180-day window, $10k volume gate) and Kalshi's $25 refer-a-friend are filters/retention tools. Real growth budget flows through Polymarket Partner Program (Dub.co, invite-only, custom rev-share + CPA stacks, sometimes equity-style for top creators) and Kalshi's bespoke Ambassador grants. Reported 6-7 figure deals existed before Kalshi's Feb 2026 X-badge purge.
- **Pred-market affiliate ≠ iGaming affiliate.** Operator's take is 0-2% (trading fee on matched orders) vs iGaming house edge of 5-15%. So 30% of pred-market fees ≈ 30% of nothing per dollar of activity. Per dollar of GGR/fees the ratios are similar, but per dollar of customer deposit the affiliate earns 5-10x less than in iGaming. No NGR concept (no negative carryover), no Income Access / MyAffiliates / Affilka equivalent, no AskGamblers-tier directory, no iGB-style conferences. Infra is being built right now (Dub for Polymarket, Impact for Robinhood).
- **Risk profile is the real differentiator.** iGaming affiliate book is durable per-jurisdiction. Pred-market book can be wiped overnight by a single CFTC ruling or state injunction (Kalshi NV sports block is the live example). Diversify across 3-4 operators minimum.
- **Arbitrage window NOW.** Pred-market operators don't yet have validated LTV models, so custom BD deals are easier to negotiate today than they will be in 18 months. Lock in terms before market matures.
- **Comparison/oddschecker positioning is the BD lever.** Pitch Prophet not as a generic affiliate but as intent-led traffic — "users who already want to bet on X convert 5-10x generic." Same door Substack newsletters and crypto KOLs walk through.
- **Affiliate is instrumentation, not the business.** Track B (B2B data feed) is the real revenue model. Affiliate funds the consumer side and proves user intent; B2B is the recurring P&L.

**Recommended affiliate stack for WC MVP (priority-ranked):**
- **P0 — Polymarket** (Partner Program via partners.dub.co/polymarket; open referral as fallback): the only program with SaaS-grade terms. USDC daily, on-chain attribution.
- **P0 — Kalshi** (BD/Ambassador direct, NOT the $25 refer-a-friend): regulatory winner, custom deals only path to value.
- **P1 — SX Bet** (sx.bet/earn): 35% lifetime fee rev-share, sports-native, on-chain attribution, international coverage.
- **P1 — Myriad** (Share to Earn): 1% USDC buy volume + points, monthly USDC payouts above $500, low-friction secondary.
- **P2 — Robinhood** (Impact.com): defer; awkward fit (sells brokerage, not contract); conflicts with Kalshi attribution.
- **Defer — IBKR ForecastEx, Limitless.** **Skip — PredictIt, Manifold, Drift BET, Augur.**

**Decisions:**
- **Output preference locked:** xlsx is the default for any comparison/research deliverable. No long markdown reports. Saved to auto-memory as `feedback_concise_outputs.md`.
- **Affiliate stack approach:** BD-negotiated custom deals over self-serve. Public refer-a-friend programs set up as fallbacks only.
- **Engineering implication (not yet implemented):** centralize affiliate links in a single config file (e.g. `affiliates.config.{js,py}`) keyed by platform + geo, so swaps and policy changes are one-edit. Affiliate-policy fluidity (Kalshi X-badge purge Feb 2026) makes this load-bearing.
- **Geo-aware link-out is now part of beta scope.** Polymarket blocks 8 US states + 33+ countries; Kalshi US-only with NV sports block; SX Bet/Myriad permissive internationally. The legal-platform-per-region routing isn't optional once affiliate links are live.

**Action Items:**
- [ ] Apply to Polymarket Partner Program (partners.dub.co/polymarket) — Adi or Faktor, this week
- [ ] Email Kalshi BD direct, pitch as comparison/data partner — Adi or Faktor, this week (don't bother with the $25 program)
- [ ] Sign up SX Bet at sx.bet/earn — Adi, this week
- [ ] Sign up Myriad Share-to-Earn (per-market button) — Adi, this week
- [ ] Add disclosure footer + per-platform geo gating to MVP design spec — Adi/Faktor + design tool
- [ ] Build `affiliates.config` single-source-of-truth file when first affiliate link goes live — Claude on request
- [ ] Decide whether to lean on Faktor's network for warm intros to Kalshi/Polymarket BD — open question
- [ ] Defer Robinhood/IBKR evaluation to post-WC MVP

**Artifacts created this session (all in `/Users/adi/Documents/Claude/Projects/prophet/`):**
- `AFFILIATE_PROGRAMS.xlsx` — canonical reference. Sheet 1: priority-ranked comparison (11 platforms, 9 columns). Sheet 2: cross-cutting risks & decisions. Color-coded by priority (P0 green, P1 blue, P2 yellow, Defer grey, Skip red).
- `AFFILIATE_PROGRAMS.md` — long-form version (still in folder, lower-priority reference; can be deleted).

**Auto-memory updates:**
- New: `feedback_concise_outputs.md` — never long markdown reports, default to xlsx for comparisons, tight tables in chat.

**Open Threads (carry to next session):**
- **Affiliate BD outreach is the immediate next action** — Polymarket Partner application + Kalshi BD email. Faktor's network might shorten the path.
- **Track B/affiliate alignment unresolved.** B2B data feed (Track B) and consumer affiliate stack (Track A) need a coherent product story. Affiliate proves intent; B2B monetizes it. How they share infrastructure isn't yet specified.
- **Carry-over from morning session (still open):** brand name lock, Cut A vs Cut B on cross-platform claim, mobile-first/light-default/accent color confirmation, per-screen design prompts, 15-20 curated WC market educational blurbs, Kalshi↔Polymarket WC market-ID mapping table (if Cut A).
- **Carry-over older:** Track A/B reconciliation (since 2026-04-22), Track B 30-day market test ends ~2026-05-22, "no sports" rule reversal not formally reconciled, retire stale `feedback_drive_workspace.md` rule.

**Handoff:**
Next session likely the branding session (still owed from morning). After branding, the affiliate BD outreach moves from "decide" to "execute." When affiliate links are about to go live, the geo-aware link-out logic + `affiliates.config` file become the engineering blocker — flag those as scope add to the WC MVP build.

---
## [2026-05-02] — Cowork

**Summary:** Strategic-mode session. Adi declared a major pivot — Prophet/PredictionEdge becomes an "educational oddschecker for prediction markets" co-developed with Faktor (good friend, 25y in gaming, "very aligned on vision"). MVP is a curated 2026 FIFA World Cup edition. Beta target ~2026-05-09 (7 days). This reverses the 2026-04-23 "no sports" decision-support positioning. Audited the live Railway deploy, identified the central pre-launch gap, agreed on five screens to design, and produced three handoff artifacts (launch task brief, design brief, standing design context). Next session: brand identity work (name lock, wordmark, color, type).

**Decisions:**
- **New positioning:** "Educational oddschecker for prediction markets." MVP = curated 2026 World Cup edition. Reverses the prior "decision-support workspace for serious traders" framing AND the "no sports" rule from 2026-04-23.
- **Co-founder:** Faktor confirmed as co-developer / partner. Should appear on About page with bio + photo.
- **Beta target:** ~2026-05-09 (7 days from this session).
- **Domain candidate:** markettipsai.com (owned, may switch). PredictionEdge is OUT (yourpredictionedge.com is an active competitor — confirmed in 2026-04-23 session).
- **Five screens for the MVP:** (1) Homepage / World Cup hub, (2) Market detail with comparison view, (3) Learn page, (4) Movers / live tracker, (5) About + trust.
- **Design approach:** go straight to high-fidelity, NOT wireframes (no time for two passes; layout is mostly content-dictated; the visual treatment IS the differentiator).
- **No formal design system upfront.** Anchor on a small "design direction" (light/dark default, one accent color, typeface vibe) and let the system emerge from the first screen (Market Detail, the highest-stakes one).
- **Mobile-first.** Match-time traffic = phones.
- **Out of scope for beta:** accounts, login, payments, multi-sport, notifications, watchlists, historical charts, complex onboarding, Track B B2B work.

**Pre-launch blockers identified (audit of live https://web-production-9e0f9.up.railway.app):**
- `/api/compare` returns every market with `source: "single"` and only Polymarket data. The "Compare odds across Kalshi, Polymarket, DraftKings and more" claim is structurally unbacked. **Cut A:** add Kalshi ingestion + a hand-built ID mapping table for the curated WC markets. **Cut B:** drop "cross-platform" from copy, position as "smart Polymarket lens" for beta. NOT YET DECIDED.
- World Cup markets exist in the data but are buried under volume-sorted Bitcoin / Iran politics / NBA Finals — needs a curated WC surface.
- Educational blurbs absent from the API. The differentiator hasn't been built.
- Trading-bot-era endpoints leak the Prophet origin (`/api/positions`, `/api/orders`, `/api/kill`, `/api/balance/live`) — should be hidden before showing outsiders.
- Three brand names coexist on the live deploy: "Prophet" in OpenAPI title, "PredictionEdge" in page title and UTM source, "MarketTipsAI" as the domain. Brand collision is visible to anyone who inspects.

**Action Items:**
- [x] Save 2-sentence MVP scope to memory + Notion-ready brief — Claude (BETA_LAUNCH_BRIEF.md)
- [x] Long-form design brief — Claude (DESIGN_BRIEF.md)
- [x] Standing design context for AI design tool project knowledge — Claude (DESIGN_CONTEXT.md)
- [x] Update auto-memory `project_prophet.md` with new MVP scope + reversal flag — Claude
- [ ] **Lock the three blocking decisions in next 24h** — Adi + Faktor:
  - [ ] Brand name + domain
  - [ ] Cut A or Cut B on cross-platform claim
  - [ ] (Implicit: confirm mobile-first, light mode default, accent color)
- [ ] Per-screen detailed prompts (5 of them) for the design tool — Claude (offered, not yet built)
- [ ] Write the 15–20 curated WC market educational blurbs — Adi/Faktor or Claude
- [ ] Hand-built Kalshi ↔ Polymarket market-ID mapping table for WC markets (only if Cut A) — Adi or Claude

**Artifacts created this session (all in `/Users/adi/Documents/Claude/Projects/prophet/`):**
- `BETA_LAUNCH_BRIEF.md` — Notion-ready MVP scope + checklist of every task to launch beta, broken by branding / design / product / dev / legal / analytics / launch.
- `DESIGN_BRIEF.md` — long-form design brief (audience, brand direction, 5-screen specs, references, anti-patterns, deliverables).
- `DESIGN_CONTEXT.md` — short standing context to upload as project knowledge into an AI design tool. Microcopy do/don't examples, recurring components, page chrome, anti-patterns, reference vibes.

**Open Threads (carry to next session):**
- **Branding session is the next step.** Brand names in play: MarketTipsAI (domain owned), PredictionEdge (out — taken), Prophet (the original). The branding session should produce: name lock, wordmark, accent color, typography pair, logo lockup. Standing context already in `DESIGN_CONTEXT.md`.
- **Cut A vs Cut B unresolved.** Drives most of the dev work. Without resolution, the design has to assume cross-platform comparison works AND degrade gracefully when it doesn't.
- **Reversal of "no sports" rule unreconciled.** April 2026 strategy excluded sports for regulatory + competitive (OddsJam) reasons. May 2026 World Cup MVP reverses that without explicit reasoning logged. Open question: are sports back permanently or just as a launch-event wedge?
- **Track B (B2B MM) untouched today.** 30-day market test still ends ~2026-05-22. Track A/B reconciliation still unresolved (carried since 2026-04-22).
- **Legacy memory inconsistency:** auto-memory previously noted Google Drive folder for project files; Adi confirmed today the Drive folder no longer exists. Local `/Users/adi/Documents/Claude/Projects/prophet/` is the only relevant folder. Auto-memory `project_prophet.md` updated this session; check `reference_artifacts.md` and `feedback_drive_workspace.md` next session if any stale references remain.

**Handoff for branding session:**
The branding session should start by reading `DESIGN_CONTEXT.md` (it has the voice rules, microcopy examples, and reference vibes already locked). The three live brand candidates: MarketTipsAI (domain owned), PredictionEdge (RETIRED — competitor name collision), or fresh option. Faktor is co-founder so consider including him in any "founder voice" framing. Recommended first deliverables: (1) shortlist of 3–5 names with reasoning, (2) wordmark exploration for top 2, (3) one accent color recommendation that avoids Kalshi green and Polymarket purple, (4) typography pair (one for UI/body, one for numbers). Note: high-fidelity straight, no wireframes.

---
## [2026-05-01] — Cowork

**Summary:** Maintenance session. Two structural changes: (1) Adi consolidated everything Prophet-related into `/Users/adi/Documents/Claude/Projects/prophet/` as the single master folder for code + Cowork artifacts, reversing the prior code-in-Claude-Code / planning-in-Drive split. (2) Adi declared Prophet a private project — memory files moved out of Google Drive into local `./memory/` and must never be synced back.

**Decisions:**
- Single master folder: `/Users/adi/Documents/Claude/Projects/prophet/` holds code + Cowork stuff. Canonical Prophet workspace.
- **Prophet is private. Memory stays local.** `SESSION_LOG_Prophet.md` and `PROJECT_Prophet.md` now live at `[project]/memory/` only — NOT in `~/Google Drive/My Drive/Claude/memory/`. Cross-laptop sync intentionally dropped.
- Snapshot skill gained a generic "project-private override" rule: if a project folder has a `memory/` subfolder, that's its canonical memory location. No project names in Drive.

**Action Items:**
- [x] Move `SESSION_LOG_Prophet.md` + `PROJECT_Prophet.md` to local `[project]/memory/`, delete from Drive — Claude
- [x] Scrub Prophet pointers from Drive `MEMORY.md` index — Claude
- [x] Add private-memory anchor block to local `CLAUDE.md` — Claude
- [x] Update Drive `session-snapshot-SKILL.md` with generic local-override rule — Claude
- [x] Update auto-memory `reference_artifacts.md` to reflect new master folder — Claude

**Open Threads:**
- Track A/B reconciliation still unresolved (carried from 2026-04-23 + 2026-04-22 sessions).
- Track B 30-day market test ends ~2026-05-22 — call should be made before then.
- Older `feedback_drive_workspace.md` rule (Cowork auto-memory) about always writing to Drive `/prophet/` is now obsolete and contradicts the new privacy decision; retire in next session.
- Drive `user_google_drive.md` index entry says "default save location is Drive" — still true for non-Prophet work, but worth a re-read pass on Adi's other rules to make sure none silently push Prophet to Drive.

---
## [2026-04-23] — Cowork

**Summary:** Track A (consumer decision-support) stress-tested with web research + ChatGPT cross-review. Original OddsChecker-for-PMs aggregator scope scored 44/100 (NO-GO). Pivoted to decision-support workspace productizing the Prophet paper-trading + risk-management stack; pivoted scope ceiling was 62–70, revised down to **55–62** after deeper read on OddsJam's PM surfaces. SPRINT.md trimmed ~25% (paper portfolio cut, Telegram demoted to stretch, 10–12 matched pairs target). Private-beta target 2026-04-26 still holds. Track B untouched.

**Decisions (Track A):**
- Retire "PredictionEdge" brand — yourpredictionedge.com is an active $9.99/mo direct competitor. Revisit "Prophet" before public launch.
- Kill affiliate-first monetization. Resequenced: paid subscription Months 1–3, affiliate as garnish Months 4–6, SEO + data licensing Months 6–12.
- Sports markets OUT of beta mapping — regulatory overhang + OddsJam owns sports-tooling.
- Sprint trimmed: cut paper portfolio / P&L sparkline / seed scripts; Telegram → Day 5 stretch only; dropped "force ≥3 buy signals" acceptance criterion (honest holds are correct).
- Realistic pivoted ceiling is 55–62, not 90 — don't scope to a ceiling that can't be delivered.

**Action Items:**
- [x] REVISED_SCOPE.md (Drive /prophet/) — Claude
- [x] SPRINT.md trimmed v2 (Drive /prophet/) — Claude
- [x] CLAUDE_CODE_TASKS.md — per-task Claude Code prompts (already in Drive /prophet/, reviewed)
- [x] PROJECT.md updated with OddsJam re-read + perpetual-futures note — Claude (this session)
- [ ] Gemini third-review of REVISED_SCOPE.md + SPRINT.md — Adi
- [ ] Day 1 T1.5 Prophet strategy smoke test (biggest sprint risk) — Adi + Claude Code
- [ ] Track A/B reconciliation decision — Adi (carried forward from last session, still unresolved)

**Project Updates:**
- Track A: scope finalized; sprint trimmed; beta 2026-04-26 on track; ceiling 55–62.
- Track B: untouched this session; 30-day test in flight ending ~2026-05-22.

**New Context (competitor landscape, verified April 2026):**
- Volumes: Kalshi $12.35–13.07B/mo, Polymarket $10.57B/mo (March 2026). Combined ~$23B/mo; Bernstein $1T/2030 at ~80% CAGR.
- Direct Track-A competitors: Your Prediction Edge ($9.99, product + name collision), Oddpool ($30/$100/Enterprise), FORS (Solana), Prediction Market Tools, FinFeedAPI, PolyRouter.
- **OddsJam (Gambling.com Group) is more serious than prior reads assumed.** Dedicated /prediction/traders and /prediction/insiders surfaces, algorithmic trader recommendations + optimal bet sizing + Kalshi/Polymarket deep links, standalone Kelly + EV calculators, Platinum push notifications, PM-to-betting-odds converter. Pricing: Plus $39 / Gold $199.99 / Global $399.99.
- **Perpetual futures launching on both venues.** Polymarket early-access with 10x leverage on gold, stocks (NVDA, COIN), BTC; Kalshi following. Phase 2 scope question: support perps or stay binary-only. Existing Prophet strategies are binary YES/NO — perps need different risk management.
- Affiliate reality softer than onepager: Polymarket 30% revshare × 180d gated behind $10K traded volume; Kalshi $25 trading credits (not cash). No public CPA verification at the $60–300/depositor claim.
- AI Overviews crushed betting-affiliate SEO: 96% of sites hit; CTR 15%→8%.
- Regulatory: Third Circuit 2-1 for Kalshi (April 6 2026). Polymarket ToS restricts US persons via UI + API.

**Open Threads:**
- **Track reconciliation still unresolved.** Track A beta 2026-04-26 and Track B 30-day test (~2026-05-22) run in parallel. Adi hasn't decided: run both, delay A for B, or kill one. Flagged in last session's log too; still needs a call.
- **T1.5 is make-or-break.** If Prophet strategies can't ingest matched-market snapshots cleanly on Monday night, wedge doesn't ship this week — revert to comparison-only or cut the sprint.
- **Distribution unsolved.** Cold-start paid SaaS + AIO-degraded SEO + no existing audience + expensive regulated-category ads. Private beta doesn't validate this; post-beta it becomes the gating question.
- **Six strategic questions** live in PROJECT.md. Q6 added post-OddsJam: "Is there a wedge structurally out of reach for OddsJam?" Current best answer: backtested strategy-driven signals on **non-sports** PM categories. If that doesn't hold up in beta feedback, margin for error is very small.

**Process note (filesystem):** This session I repeatedly wrote planning docs to `/Users/adi/Documents/Claude/Projects/prophet/` instead of Google Drive despite the rule in MEMORY.md + the past fix logged in PROJECT_Prophet.md. Corrected after Adi pushed back; Drive folder now mounted (`~/Library/CloudStorage/GoogleDrive-…/My Drive/Claude/prophet/`). Reinforced rule in Cowork auto-memory (`feedback_drive_workspace.md`). If this repeats in a future session, escalate — it's now been flagged twice.

---
## [2026-04-22 / 2026-04-23] — Cowork

**Summary:** Strategic evaluation of an ALTERNATIVE direction for Prophet — running the paper-trading bot's underlying tech as a B2B market-making infrastructure business sold to trading firms and small PM venues. This is a PARALLEL TRACK (Track B). The consumer decision-support workspace pivot from 2026-04-20 (Track A, private beta launching 2026-04-26) is unaffected by this session and was not discussed. Two external analyst reports (ChatGPT + Gemini) returned independent GO-WITH-CHANGES verdicts on the Track B B2B thesis. Built four artifacts to support a 30-day market-validation test for Track B.

**IMPORTANT — Two-track reality:**
- Track A (consumer decision-support workspace, $29/mo, private beta 2026-04-26): UNCHANGED by this session.
- Track B (B2B MM infrastructure, this session's focus): NEW evaluation.
- Adi has not yet decided whether Track B replaces, complements, or is parked alongside Track A. The 30-day test should be the input for that call.

**Decisions:**
- **Tier A only.** Sell licensed software (customer runs it on their infra, with their capital). Both analysts independently flagged Tier B (managed service) as the thesis killer — capital intensity ($500K-$2M per customer per Gemini), CTA/IB/CPO registration risk, and in-house verticalization by buyers.
- **Two ICPs, one product.** Trading firms (alpha capture) and small/mid PM venues (seed liquidity). Same software, different value prop. Decide which sells better in 30 days.
- **Wedge: correlated-event handling.** Both analysts agreed pricing math is commodity; the moat is news-driven volatility handling, adverse-selection defense, and venue connectivity at scale. Operator-console mockup leads with this.
- **Pricing: $10K-$30K/mo.** Annual contracts. 30-day free pilot on Demo, 60-day paid pilot on live. No managed-service tier (keeps regulatory exposure on customer side).
- **Brand "Prophet" is a placeholder.** Reads consumer-y for B2B; needs a real name before going to market.
- **30-day test before any further build.** Six concrete deliverables, ~70 founder-hours, pass/fail bar at day 30.

**Action Items:**
- [x] Build operator console mockup — Claude → `prophet/mockups/operator-console.html`
- [x] Build Tier-A revenue & capacity model (xlsx, 1,155 formulas, zero errors) — Claude → `prophet/models/tier-a-revenue-model.xlsx`
- [x] Build mom-explainer presentation (9 slides, plain language) — Claude → `prophet/presentations/explainer-for-mom.pptx`
- [x] Build positioning one-pager (validated docx, US Letter) — Claude → `prophet/sales/positioning-onepager.docx`
- [ ] Record 3-min demo video of Kalshi DEMO bot — Adi (~8 hrs)
- [ ] Build target list of 30 named contacts (15 quant shops, 10 venues, 5 sportsbook leads) — Adi (~8 hrs)
- [ ] Send 30 personalized cold emails — Adi (~12 hrs)
- [ ] Conduct 5+ discovery calls with structured notes — Adi (~20 hrs)
- [ ] Write end-of-30-days decision memo (GO / PIVOT / KILL) — Adi (~4 hrs)
- [ ] Decide on real brand name (placeholder "Prophet" doesn't fit B2B) — Adi
- [ ] Decide on pricing range narrowness ($10-30K vs $5-50K vs $15-25K) — Adi
- [ ] Decide whether to keep or strike Cboe/Fanatics roadmap claim in onepager — Adi

**Project Updates:**
- **Prophet (paper-trading bot):** Now reframed as the *demo asset* underpinning a B2B sales motion, not a standalone investor-facing artifact. The bot's Python code, Kelly-sized risk manager, and Kalshi+Polymarket connectivity are the moat-credibility piece for the new B2B pitch.
- **New parallel track:** Tier-A MM infrastructure thesis evaluation. 30-day market test in flight (deliverables above).

**Model Findings (xlsx):**
- BASE case (TAM=25 logos, ACV=$15K, close=13.5%): peaks ~3 customers, $44K MRR @ M12 — MISSES $50K target by $6K, then declines as small-TAM pipeline exhausts and churn eats the base.
- BEAR (TAM=10): non-viable, $1.4K MRR.
- BULL (TAM=50, ACV=$35K): $458K MRR but capacity utilization 112% — implies quitting day jobs, violates side-project constraint.
- TAM ceiling is the binding constraint, not close rate. Realistic equilibrium: 5-6 customers, $75-90K MRR.

**New Context:**
- ChatGPT + Gemini analyst reports both delivered GO-WITH-CHANGES verdicts. Strong convergence: kill Tier B, lead with correlated-event wedge, sell to mid-tier not top sportsbooks, 9-18 month window before Sportradar/OddsJam-class incumbents commoditize.
- Disagreement: ChatGPT estimates 8-15 realistic Tier-A buyers (venues only); Gemini estimates 30-40 (incl. niche venues). ChatGPT more grounded — quant shops are the variable that pushes TAM to ~25.
- April 6 2026: Third Circuit ruled CFTC has exclusive jurisdiction over sports event contracts. Helps the category.
- FanDuel Predicts launched Dec 2025 (5 states, CME partnership); DraftKings Predictions launched Dec 2025 (38 states, CME + Crypto.com). Top sportsbooks vertically integrating PM exposure in-house.
- Kalshi has SIG as institutional MM partner since 2024; Robinhood + Susquehanna acquired their own exchange/clearing for PMs. Venue-MM relationships are tightening — top tier is closed.
- Polymarket paying $5M+/month in liquidity incentives (April 2026) — confirms the venue-side pain point.

**Open Threads:**
- **TRACK RECONCILIATION URGENT.** Track A private beta is 2026-04-26 (4 days away). Track B 30-day test would land ~2026-05-22. Adi needs to decide: (a) launch Track A as planned and run Track B 30-day test in parallel, (b) delay Track A to focus on Track B validation first, or (c) kill one. This session did not address this — the next session should.
- Bridge to Cowork auto-memory: written to a new memory file `project_prophet_b2b_mm_evaluation.md` to keep the prior decision-support pivot memory intact. Both tracks now coexist in memory.
- After 30-day Track B test ends (~late May 2026): if GO, scope a 6-month Tier-A build; if KILL, fully shelve the B2B thesis and revert focus to Track A.
- Adi has not yet run any actual prospect conversations for Track B — the entire current Track B state is desk research + artifact prep.
---
