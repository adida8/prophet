# Session Log — Prophet

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
