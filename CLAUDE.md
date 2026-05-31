# Prophet · Ledger · The Desk · Odds Primer site

This repo carries four discrete surfaces. They share a Python + React
stack but are independent — each can run, deploy, and ship without the
others.

| Product | What it is | Lives at | Status |
|---|---|---|---|
| **Prophet** | Paper-trading bot for prediction markets, plus the platform's market data engine and React dashboard | `prophet/` (or repo root for legacy code), `frontend/` | shipping; deployed to Railway |
| **Ledger** | Connected portfolio tracker for Polymarket (Kalshi in Phase 1). Paste-a-wallet viewer at `/ledger`. | `ledger/`, `frontend/src/ledger/` | Phase 0 shipped; live on Railway |
| **The Desk** | Verdict engine that evaluates every priced football match + the WC 2026 outright winner market | `desk/` | PRs 1–4 + backtest + 4.5 sanity + explainer stub + **optimization-spec Phase A** + **outright engine (parallel pipeline, live on Polymarket)** + **WC26-only ingest filter** + **per-team outright ladder UI** + **team-id collision fix + seed-Elo audit** + **news-signals PRs A–F all live in production** (12 trusted-core RSS → Haiku → `copy.editorial_citations` + bounded Elo nudges) + **PR 5 Haiku blurb-writer** (gated on `DESK_BLURB_HAIKU=1`, falls back to stub on any failure) + **distribute wire to Market Tips AI** (sqlite outbox + HMAC-signed push + bearer-gated GET safety net, gated on `DESK_DISTRIBUTE_PUSH=1` / `DESK_API_BEARER_TOKEN`) + **Phase B.1 form residual coupled unit (Shadow)** + **Phase 1b live Elo (per-match + outrights, free)** + **Phase B.3 injury penalty (Shadow, audit-gated)** + **PR 6 `desk schedule` CLI** + **forward-validation measurement loop** (`desk fv-report` / `desk fv-ingest-outcomes`) + **ops dashboard External providers panel** + **team-news blurb subsystem Slices A+B+C shipped to staging 2026-05-30** (api-football injuries + RSS hard signals fuse into a per-team `TeamNews` payload; api-football `/fixtures/lineups` fetcher; Haiku prompt mandate with materiality matrix + "Neymar opens for Brazil" starter highlights; T-90m polling loop; `DESK_LINEUP_FETCH=1` + `DESK_LINEUP_LOOP_ENABLED=1` + `DESK_FORCE_TICK_ON_BOOT=1` flags). **Pending operator actions:** eyeball staging blurbs once Haiku catches up; merge `staging` → `init/project-setup` to promote to prod + **dedicated squad-paragraph subsystem Q1–Q5 shipped to staging 2026-05-30** (card-accumulation data path + `CardStatus` on `TeamNews` + Haiku `SQUAD PARAGRAPH` mandate + outright per-team `squad_note` + `desk fetch-cards` CLI + daily-tick wiring). `DESK_INJURY_FETCH=1` + `DESK_LINEUP_FETCH=1` + `DESK_LINEUP_LOOP_ENABLED=1` + `DESK_CARD_FETCH=1` + `DESK_BLURB_HAIKU=1` all flipped live on staging + prod (2026-05-30 evening). **Operator action still pending:** confirm WC26 yellow-card reset rule (wipe-after-QF) against the actual 2026 FIFA tournament regulations — `DESK_CARD_FETCH=1` is already live, so post-QF at-risk flags will be wrong if the 2026 regs diverge from 2022's. |
| **Odds Primer site (React)** | Editorial front-of-house: home (`/`), about (`/about`), learn (`/learn` + 3 primers). Reuses the design system; hardcoded sample data — live wiring is a later workstream. Legacy Prophet trading dashboard moved to `/dashboard` (unlinked). | `frontend/src/op/` | shipped to staging 2026-05-13 (PR #27). **Route conflict at `/` with `site/generate.py`'s static site (`/`, `/matches`, `/outrights`) needs reconciling before prod promote. |
| **Activity signals** | Anonymous views + four-way reaction chips on every match card. Top "activity strip" (N users · Most picked · Community leaning) + chip row (🐂 Bullish · 💸 Overpriced · 🪤 Trap line · 💎 Value). Vanilla-JS island injected by `site/generate.py`; backend is FastAPI + Railway Postgres (the only Postgres-backed domain in this repo — everything else is sqlite). | `activity/`, `activity_refresh_loop.py`, `migrations/`, `site/public/js/activity.js`, `tests/activity/` | **staging: live + working end-to-end (2026-05-27).** Prod: code merged in `2753d6c` but prod Postgres + `DATABASE_URL` reference not yet wired; widget renders, every POST 500s silently until that's done. Lifespan is hardened (asyncpg 5s connect timeout + try/except) so a missing DB no longer bricks the rest of the site. |

Build specs live alongside the code:

- `THE_DESK_SPEC.md` — six-PR build plan for The Desk
- `THE_DESK_PR_BACKTEST_BRIEF.md` — backtest harness brief (shipped)
- `THE_DESK_PR_4_5_BRIEF.md` — sanity layer brief (shipped)
- `THE_DESK_TRUSTABILITY_BRIEF.md` — first trustability roadmap (superseded by the optimization spec)
- `THE_DESK_OPTIMIZATION_SPEC.md` — v1.1 + v1.2 optimization spec; **Phase A landed**, B–F outstanding
- `THE_DESK_OUTRIGHTS_SPEC.md` — outright winner build spec; v0.2 supersedes earlier drafts. Note: v0.2 wants outrights folded through the position-list waist, but **the parallel-pipeline implementation in `desk/outrights/` shipped first** — it predates the waist refactor and runs live on Polymarket today.
- `THE_DESK_DATA_LAYER_SPEC.md` — data layer spec; Phase 1b (live Elo from eloratings.net / clubelo.com) is the credibility-load-bearing piece the match-Pick page needs before its Picks become real signals
- `THE_DESK_NEWS_SIGNALS_SPEC.md` — news & editorial signals spec (v0.1 draft). PRs A–F **all shipped** as of 2026-05-21 — sport-agnostic source registry + resolver, RSS fetcher + cache, Haiku extractor, editorial track → `copy.editorial_citations`, GDELT aggregator path, hard-track Elo adjustments. Live on Railway behind `DESK_SIGNALS_FETCH=1` + `DESK_SIGNALS_EXTRACT=1` (needs `ANTHROPIC_API_KEY`).
- `THE_DESK_SQUAD_PARAGRAPH_SPEC.md` — dedicated squad-paragraph spec (v0.1, 2026-05-30). **All five PRs Q1–Q5 shipped to staging.** Q1: card-accumulation data path (`desk/data/api_football/cards.py` + `card_accumulation` cache table + `CARD_RULES` per-competition registry + sanity gates). Q2: `CardStatus` dataclass + `cards: tuple[CardStatus, ...]` field on `TeamNews`; builder reconciles at-risk against already-suspended players (substring fallback covers "Bellingham" vs "Jude Bellingham"). Q3: Haiku system prompt's `SQUAD PARAGRAPH` section mandates ONE dedicated paragraph covering opening XI + out + at-risk; word-count ceiling bumps 220 → 240 when squad content present; `post_check` extended with at-risk-as-fact guard + "at risk"/"one booking"/"one yellow"/"yellow accumulation" added to the materiality=none availability-keyword set. Q4: deterministic per-team `squad_note` string on every outright ladder row (`Out: Saliba (injury). One booking from a ban: Tchouaméni.`), no Haiku call — additive-only field, no ADR (outright JSON has no Pydantic contract and no documented external subscribers). Q5: `desk fetch-cards` CLI + daily-tick wiring at `desk_refresh_loop.py`. Gated on `DESK_CARD_FETCH=1` (data path) + `DESK_CARD_AT_RISK=1` (surfacing, default on) + `DESK_TEAM_NEWS_BLURB_REQUIRED=1` (strict post-checks). `DESK_CARD_FETCH=1` flipped live on both envs 2026-05-30 evening. **Operator action still pending:** confirm the WC26 yellow-card reset rule (wipe-after-QF) against the actual 2026 FIFA tournament regulations — currently running on the 2022 rule assumption; post-QF at-risk flags will be wrong if 2026 diverges. **Post-ship spec change 2026-05-31:** the squad paragraph now ALWAYS fires (was: silent when no data). The no-data case writes one positive sentence (`"both squads come through clean"` / `"no flagged absences either way"`) instead of being absent — reader was expecting to see something on every match page; api-football's sparse pre-tournament injury data meant 71 of 72 matches were silent. Post-check guard relaxed to reject only negative claims (`"X is injured"`, `"ruled out"`, `"one yellow from a ban"`), not generic positive vocabulary.
- `THE_DESK_TEAM_NEWS_BLURB_SPEC.md` — team-news blurb spec (v0.2, 2026-05-30). **Slices A + B + C all shipped to staging.** Slice A: `TeamNews` payload (`PlayerAbsence` + `LineupStatus` + materiality matrix) fuses api-football injuries cache + RSS hard signals into one per-team object threaded onto Haiku's `Inputs`; system prompt gains a `TEAM NEWS POLICY` section with materiality-driven mandate; `post_check` adds three guards (must-name-player on materiality=high, no availability filler on both-sides-none, confirmed-lineup must name a starter or formation). Slice B: api-football `/fixtures/lineups` fetcher (`desk fetch-lineups [--window-hours 24]`) with `LineupRow` + `FixtureResolution` cache tables, `APIFootballRuntime.lineup_for_match_iso3`, starter-name highlights in the Haiku prompt ("Neymar opens for Brazil; Vinicius starts on the left"). Slice C: T-90m polling loop at `desk_lineups_refresh_loop.py` (15-min cadence, 2h kickoff window, re-publishes on landing). Gated on `DESK_LINEUP_FETCH=1` (daily tick) + `DESK_LINEUP_LOOP_ENABLED=1` (T-90m loop) + `DESK_TEAM_NEWS_BLURB_REQUIRED=1` (strict post-check). `DESK_FORCE_TICK_ON_BOOT=1` overrides `control.json` so a redeploy guarantees a refresh tick.
- `THE_DESK_SOCIAL_SPEC.md` — social automation spec (v0.1, 2026-05-28). **Phase 1 (PRs S1–S6) shipped 2026-05-28** — sqlite draft queue at `desk/desk/social/`, stub renderer (4 solid-colour 1080×1350 PNGs), selector (daily highest-conviction Pick + weekly roundup), IG + X caption templates with voice-rule + social banned-phrase enforcement + outlet-attribution lockstep, FastAPI router at `/api/desk/social/*` (re-uses `/desk/ops` Basic-auth gate), React approval view at `/desk/ops/social`, bundle download (PNGs + caption .txt files + meta.json) + Mark-as-posted hand-off, daily hook in `desk_refresh_loop.py` + new `social_weekly_cron.py` for the Sunday roundup. Gated on `DESK_SOCIAL_ENABLED=1` + the existing `DESK_OPS_USER` / `DESK_OPS_PASS`. **Phase 2** (S7 IG Graph API + S8 X v2 auto-post) outstanding — waits on Meta verification + X Basic subscription. Real slide renderer (replacing `StubRenderer`) is a separate workstream tracked by `THE_DESK_SOCIAL_RENDERER_SPEC.md`.
- `ACTIVITY_SIGNALS_SPEC.md` — v1.0.1, locked. Anonymous views + four-way reactions on every match card. Schema in Railway Postgres (`migrations/20260527_activity_signals.sql`), FastAPI router at `/api/activity/*`, three background jobs in `activity_refresh_loop.py` (aggregator 60s / seeder 8 min / prune daily), vanilla-JS island at `site/public/js/activity.js`. Live on staging; prod awaits Postgres provisioning + `DATABASE_URL` wiring.
- `desk/VOICE.md` — **canonical editorial voice for all Desk-generated copy** (V1: dry wit with a spine; 120–180-word blurbs, every blurb has a point + is sourced, never invent a citation). PR 5's Haiku blurb-writer prompt MUST point here. Hard "never" rules are enforced in `desk/desk/explainer/voice.py`; brand-level prose lives in `Odds Primer Design System/README.md`.
- `STATUS.md` — overnight-run briefing (refreshed when an autonomous run lands work; check it in the morning)
- `ledger-phase-0-brief.md` — Phase 0 brief for Ledger
- `Odds Primer Design System/` — voice, palette, type, components. Canonical brand assets live at the **top level**: `assets/wordmark.svg`, `assets/wordmark-tagline.svg`, `assets/glyph-bars.svg`, with the lockup spec in `preview/wordmark.html`. Wordmark is **Inter Tight 700** (not Source Serif 4); bars glyph uses `viewBox 0 0 38 34`. The earlier `branding/locked/` folder is **archived** — don't read or import from it.

## Brand Persona (marketing workstream — non-code)

`Brand Persona/` holds the spec for an **original AI virtual influencer** built as a brand-ambassador for the betting/prediction-market audience. Started 2026-05-31. Brand play, stylish & striking, **no adult content**. Core positioning: *competence is the attractive trait* — looks are packaging, credibility is the product.

- **Original character only** — never a clone of a real person (likeness/right-of-publicity + impersonation risk). A real IG reference was explicitly rejected as a base.
- `character-bible-v1.md` — persona spec, name candidates, open questions.
- `video-workflow-v1.md` — daily script-to-Reel pipeline: Midjourney + LoRA (lock face) → image-to-video bridge → HeyGen custom avatar → ElevenLabs voice → CapCut polish. Build once, ~20 min/day after. Custom avatar only (never stock); one voice forever; caption everything; label as AI in bio.
- **Open:** face-of-Odds-Primer vs standalone account, platform, name, verdict-deliverer vs lifestyle, and premium-vs-curvy body direction all unsettled.

## Deploy

Two deploy branches, both watched by Railway:

- **`staging`** — pre-prod copy of the site. Work lands here first. the operator clicks around the staging URL to confirm things look right before promoting. (Staging URL: TODO — fill in.)
- **`init/project-setup`** — production. Live URL: `https://oddsprimer.com` (Railway-deployed; the older `web-production-9e0f9.up.railway.app` host still resolves to the same service). Only receives merges *from* `staging` once changes look good.

Default workflow: commit on `staging` → push → eyeball the staging URL → when happy, merge `staging` → `init/project-setup` to ship. Feature branches are optional; the operator typically works directly on `staging` since it's a solo build.

Build pipeline (same on both branches): `railpack.json` runs `npm install` + `vite build` for the frontend, then `python main.py --dashboard --port $PORT` as the start command.

---

## Prophet — paper-trading bot + market data platform

Autonomous paper-trader for the **Kalshi Demo** API plus a market data scheduler that pulls Kalshi + Polymarket and matches them for arb / movers. Records simulated trades to CSV; **never** calls the Kalshi order API.

### Quick start

```bash
cp .env.example .env          # fill KALSHI_API_KEY + KALSHI_PRIVATE_KEY_PATH
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..

python main.py                # data platform + dashboard on :8000
python main.py --paper-trade  # also run the paper-trading loop
```

For frontend dev with hot-reload: `cd frontend && npm run dev` (port 5173) while the backend runs on 8000.

### Layout

```
main.py                  # Entry point — orchestrates scheduler + server (+ ledger refresh)
config.py                # Env vars, constants, ticker watch-list
server.py                # FastAPI server (REST + WS broadcast + SPA fallback)
scheduler.py             # Polymarket + Kalshi fetch loop (30s default)
risk_manager.py          # Kelly Criterion position sizing (2% hard cap)
core/                    # Auth (RSA-PSS), HTTP/WS client, CSV logger
strategies/              # Strategy ABC + simple_arb
frontend/                # Vite + React dashboard (recharts, lucide-react)
data/portfolio.csv       # Simulated trade log
data/prophet.db          # Market data snapshot store
```

### Key design decisions

- **No real trades.** Simulated only.
- **Demo environment only.** All URLs point to `demo-api.kalshi.co`.
- **Half-Kelly** with a hard 2% cap per trade.
- **WebSocket reconnect** — Kalshi stream auto-reconnects on 5s backoff.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `KALSHI_API_KEY` | — | Kalshi API key |
| `KALSHI_PRIVATE_KEY_PATH` | `./kalshi_private_key.pem` | RSA private key path |
| `STARTING_BALANCE` | `10000` | Simulated starting capital |
| `MAX_BET_PCT` | `0.02` | Max 2% of balance per trade |
| `TRADING_FEE_PCT` | `0.008` | 0.8% fee per trade |

---

## Ledger — Polymarket portfolio viewer (Phase 0)

Sister product under the Odds Primer masthead. Paste a `0x…` wallet at `/ledger` → see open + closed positions and a cumulative P&L chart, all server-side persisted in `data/ledger.db`. Free, no auth.

### Layout

```
ledger/
├── README.md            # architecture + Phase 1 path
├── db.py                # aiosqlite — wallets / snapshots / positions
├── polymarket.py        # async client for data-api.polymarket.com
├── service.py           # refresh + view-model build + history
├── router.py            # /api/ledger/* mounted by server.py
└── refresh_loop.py      # 15-min background refresh

frontend/src/ledger/     # path-routed at /ledger and /ledger/{addr}
├── LedgerApp.jsx
├── Masthead.jsx         # locked Odds Primer wordmark + edition strip
└── ...                  # uses op-tokens.css (verbatim copy of design system)
```

### API

| Method | Path | Returns |
|---|---|---|
| `POST` | `/api/ledger/wallet/refresh` | View model after a forced refresh |
| `GET`  | `/api/ledger/wallet/{address}` | View model (cached < 5min) |
| `GET`  | `/api/ledger/wallet/{address}/history` | Snapshot time-series |

See `ledger/README.md` for the full data flow + the path to add Kalshi in Phase 1.

---

## The Desk — verdict engine

Engine that evaluates **every priced football match** (not just WC 2026). For each match it produces a `verdict.json` (Pick / Pass / Avoid) + three rendered editorial strings (title / summary / blurb). The website (built by Faktor — the operator's partner on this) is the only consumer; it reads only the CDN-fronted JSON contract.

Six-step pipeline, each independently replaceable:
**Ingest → Features → Model → Verdict → Explainer → Publish.**

### PR ladder (per `THE_DESK_SPEC.md` §4 + briefs)

- ✅ PR 1 — output contract + static-file publisher
- ✅ PR 2 — fixture ingest + match identity (Polymarket gamma → 78 priced fixtures)
- ✅ PR 3 — football model v1 (Elo + host + home + altitude)
- ✅ PR 4 — verdict step + thresholds (end-to-end pipeline)
- ✅ Backtest harness — `desk backtest --tournament wc-2022` + summary dashboard
- ✅ PR 4.5 — sanity layer (liquidity filter + stub-Elo gate + Avoid edge_pp fix)
- ✅ Explainer stub — templated `copy.{title,summary,blurb}` with voice-rule enforcement
- ✅ Phase A (per `THE_DESK_OPTIMIZATION_SPEC.md`) — bootstrap CI, multi-window persistence, Avoid review
- ✅ Outright winner engine — parallel `desk/outrights/` pipeline (MC sim, 10k baseline + 100×1k bootstrap), live on Polymarket WC 2026 winner market, publishes `desk/data/output/outrights/fb-wc26-winner.json` + per-team ladder. Predates the waist refactor in `THE_DESK_OUTRIGHTS_SPEC.md` v0.2.
- ✅ WC26-only live ingest filter — `DESK_COMPETITIONS=wc26` (default) gates Polymarket ingest to the World Cup. Override with `DESK_COMPETITIONS=wc26,epl,ucl` or `*` for all.
- ✅ Team-id collision fix — Polymarket reuses slug code `kor` for both Korea Republic and Curaçao ("Kòrsou"). Ingest now prefers title-name → ISO3 lookup (see `iso3_for_name` in `desk/sports/football/teams.py`), falls back to slug code only when title is unknown.
- ✅ Seed-Elo audit — `desk/sports/football/data/elo_seed.py` audited against eloratings.net mid-2026. Frozen until live ingest lands.
- ✅ News-signals PRs A–F (per `THE_DESK_NEWS_SIGNALS_SPEC.md`) — 21-source global registry (13 RSS active + 8 trust-only / `feed_type=none` reserved for licensed APIs), `desk fetch-signals` populates `desk/data/signals.db`, `desk extract-signals` runs Haiku with prompt caching + tool-use schema (cost ~$0.003/article, content-hash dedupe makes steady-state nearly free), `copy.editorial_citations` filled by `build_citations` with team binding to the participating sides + ≥2-org consensus detector for plural attribution, hard-track injury/suspension Signals from `can_feed_model` sources nudge each team's Elo within the 5-day late-binding window (bounded -8 injury / -6 suspension, capped -30 total per team). Wired into `desk_refresh_loop.py` so the daily tick fetches + extracts + republishes JSON.
- ✅ PR 5 — explainer Haiku replacement. `desk/desk/explainer/haiku.py` is the blurb-writer (`claude-haiku-4-5`, forced tool-use, system prompt loads `desk/VOICE.md` verbatim + cache_control ephemeral so a single run amortises across 70+ matches). `desk/desk/explainer/__init__.py` dispatches: when `DESK_BLURB_HAIKU=1` + `ANTHROPIC_API_KEY` set, Haiku writes title/summary/blurb; stub still produces `drivers` + the merged Copy is voice-checked one more time. Falls back to the templated stub on any failure (no key, network/timeout, voice-rule violation, blurb outside [80, 220] words, attribution to an outlet not in `editorial_citations`).
- ⬜ PR 6 — scheduler + CLI + serve
- 🟢 Phase B.1 — form residual. **Coupled unit shipped end-to-end in Shadow** (per `THE_DESK_OPTIMIZATION_SPEC.md` §4.B.1 + data-layer spec §5). `FootballFeatures` carries optional `team_*_form_delta` (+ `team_*_rank_residual` field reserved but unused — see [ADR 0002](desk/docs/adr/0002-defer-rank-residual.md)); `_adjusted_elos` applies `FORM_WEIGHT * form_delta` when `DESK_FORM_RANK_RESIDUAL=1`; per-team `Driver` fires once a contribution clears ±15 Elo. Data side (`desk/desk/data/api_football/`): WC26 national-team registry → `/teams?search=` resolves canonical ISO3 ↔ numeric `team_id`; `/fixtures?team=X&last=10` populates a sqlite cache; `compute_form_delta` produces a weighted-PPG-vs-baseline scalar per team that `features_builder.build_features(fx, form_source=runtime)` threads onto each WC26 fixture. Refreshed nightly via `desk fetch-rank-form` (gated on `DESK_RANK_FORM_FETCH=1`). **Discipline gates all in:** Citation provenance on every `FormDelta` row (source endpoint + fetched_at + transform name); sanity gates (`sanity.py`) reject fixtures with wrong-window date / wrong-team entity / negative goals + reject form_delta outside ±2.0; pre-publish coverage report (`coverage.py`) WARNs when WC26 team-resolution <95% or per-competition fixture coverage <98%; `desk rate-budget` CLI prints worst-case daily-call estimate vs the Pro cap (currently 140 / 7,500 = 98.1% headroom). **Forward-validation logger wired into `run_once`**: per fixture with form_delta, `FootballSport.decide_and_explain` dual-computes "published" + "shadow with-residual" via `compute(features, force_residual=True)` and writes to `forward_validation.db` so Brier comparison is mechanical once outcomes resolve. `DESK_FORM_RANK_RESIDUAL` stays `0` in prod until the ≥100-fixture sample clears spec §1.4 (no Brier regression vs Phase A's 0.5806, sane directional behaviour). WC-2022 backtest byte-identical with flag off (Brier 0.5806 / 0.5794, 30 pick / 34 pass / 0 avoid).
- 🟢 **Phase B.1 measurement loop** — `desk fv-ingest-outcomes` pulls resolved match results from api-football `/fixtures?team=X&date=Y` (waits 30h post-kickoff for settle), `desk fv-report` prints Brier + §1.4 gate verdict + reliability bins. Wired into the daily refresh tick when `DESK_RANK_FORM_FETCH=1`. When the ≥100-fixture sample shows no regression + sane direction, `DESK_FORM_RANK_RESIDUAL=1` graduates B.1 Shadow → Live.
- 🟢 **Phase 1b live Elo** — `desk/desk/data/elo/` ships eloratings.net (World.tsv, parser-hardened with row-count + in-range floors; keeps last-good cached values on parser mismatch) + api.clubelo.com (per-club CSV, top-5 league + WC26 mapping). `EloRuntime` reads cache-then-seed; `features_builder.build_features(fx, elo_source=runtime)` threads it onto every fixture. **Also feeds the outright winner sim** via `desk/desk/outrights/live_elo.py` — per-team `live − outright_seed` deltas are merged alongside the existing hard-signal nudges, only firing when `source_id="eloratings"` (so cache-absent stays byte-identical). Live data wins; seed values still flow as the floor (preserves WC-2022 backtest byte-identical for both per-match and outright surfaces). `desk fetch-elo` CLI; gated on `DESK_ELO_FETCH=1`. **No vendor key required** — both providers free.
- 🟢 **Phase B.3 injuries** — `desk/desk/data/api_football/injuries.py` + `injuries_refresh.py`. Per-team injury fetch → bounded Elo penalty (per-player importance × INJURY_BASE_PENALTY 60 Elo, capped at 150 Elo/team; only `Missing Fixture` + `Suspended` types count, `Questionable` excluded). **Pre-flip audit** via `desk b3-audit` (probes 8 sides, checks 60% coverage / 90% position-presence / 90% type-presence floors per spec §5). Hook: `_adjusted_elos` subtracts the penalty when `DESK_INJURY_PENALTY=1`; per-team `Driver` fires above ±15 Elo. Dual-prediction shadow path captures both B.1 form-on AND B.3 penalty-on in a single `compute()` call via `force_residual` + `force_injury_penalty` overrides. `desk fetch-injuries` CLI; gated on `DESK_INJURY_FETCH=1`. ~70 calls/tick (Pro cap headroom unchanged at ~98%).
- 🟢 **PR 6 scheduler** — `desk schedule` CLI wraps `desk_refresh_loop.py` so the loop is invokable through the unified `desk` surface. `--once` runs a single tick + exits (cron-friendly); without it, the loop runs forever, honouring the Ops dashboard's `control.json` schedule. The underlying loop file is unchanged — the wrapper is the cleanup, not a rewrite.
- 🟢 **Team-news blurb subsystem Slices A + B + C** (per `THE_DESK_TEAM_NEWS_BLURB_SPEC.md` v0.2) — shipped to `staging` 2026-05-30, prod promotion pending operator merge. **Slice A:** `desk/desk/sports/football/team_news.py` builds a per-team `TeamNews` payload (`PlayerAbsence` + `LineupStatus` + materiality matrix) by fusing the api-football injuries cache with RSS hard signals, deduped by NFD-normalised player name with surname fallback. `Inputs` carries `team_a_news` / `team_b_news`. Haiku system prompt has a `TEAM NEWS POLICY` section that mandates blurb behaviour by materiality (high → must name an absent player, none → must not mention availability). `post_check` ships three new guards (named-player, availability-keyword-on-none, confirmed-lineup hook) — soft by default, hard via `DESK_TEAM_NEWS_BLURB_REQUIRED=1`. **Slice B:** `desk/desk/data/api_football/lineups.py` + `lineups_refresh.py` implement the `/fixtures/lineups` fetcher with cache-backed fixture-id resolution. New cache tables `lineups` + `fixture_resolution`. `desk fetch-lineups [--window-hours 24]` CLI. `APIFootballRuntime.lineup_for_match_iso3` is the hot-path read. api-football lineup wins over RSS `confirmed_lineup` signals when both present (structured 11-name list + formation). Haiku prompt extended with explicit "name 1–2 notable starters by surname" instructions + concrete example shape ("Neymar opens for Brazil; Vinicius starts on the left"). `_format_team_news` renders the starting XI verbatim. **Slice C:** `desk_lineups_refresh_loop.py` at project root (registered alongside the other loops in `main.py`). 15-min cadence, scans for fixtures in next 2h, calls `desk fetch-lineups --window-hours 2`, on any successful fetch runs `desk run --once` + `site/generate.py` so new starters reach the published surface before kickoff. ~16 calls/hr on a typical WC26 day. Gated on `DESK_LINEUP_LOOP_ENABLED=1` + `API_FOOTBALL_KEY`. `DESK_FORCE_TICK_ON_BOOT=1` overrides `control.json` so a redeploy guarantees a refresh tick. Daily refresh tick also runs `desk fetch-lineups --window-hours 24` when `DESK_LINEUP_FETCH=1`.
- ⬜ Phase B.2 (weather) per optimization spec
- ⬜ Phase C–F per optimization spec

### Trustability progress (Phase A of `THE_DESK_OPTIMIZATION_SPEC.md`)

Phase A landed in four sub-phases (A.1 bootstrap CI, A.2 band tuning,
A.3 multi-window persistence, A.4 Avoid review). Each shipped tests
green and a regenerated dashboard. Detail in `STATUS.md`.

| Pick rate | Original | After PR 4.5 | After A.1 (±20) | After A.2 (±50) |
|---|---|---|---|---|
| WC 2022 backtest | 95% | 95% | 77% | **47%** |

Down from 95% to 47%; not yet inside the 5–20% target. Calibration
tied with the closing market (Brier 0.581 vs 0.579), so the dashboard
**does not** read "Trustable" green yet — both Pick rate and Brier
need Phase B's late-binding features. The selection-discipline ladder
(bootstrap CI → tune → persistence → Avoid review) is now in place;
Phase B is the next-largest lever.

Phase A.3 multi-window persistence is wired but a no-op on WC 2022
because the backtest uses one closing-market snapshot for every
window. It activates with Phase D's walk-forward harness + per-window
market data, or in live mode once PR 6 ships the per-match
persistence cache.

Phase A.4 documented that the Avoid rule is structurally impossible
on single-venue normalized closing odds (per-side edges sum to 0).
Threshold relaxed -2.0 → -1.5pp per spec; v1.2 ADR candidate to
redefine Avoid as max-side edge ≤ avoid_pp or a market-distortion
metric so it can fire on single-venue data.

Every published `MatchOutput` carries voice-checked editorial prose
in `copy.{title, summary, blurb}`. Sample Pick output on a live WC
2026 fixture:

> The model rates Bosnia and Herzegovina at 34%; the market prices that
> side at 22%. The +11.1pp gap is the basis for the Pick.

### Backtest

```bash
cd desk && PYTHONPATH=. python3 -m desk backtest --tournament wc-2022
```

Replays the engine across a frozen historical sample, writes:

- `desk_backtest.xlsx` — Snapshots + Match Universe rebuilt from real
  inputs. Brier and verdict-resolution formulas auto-recompute when
  Excel opens the file.
- `desk_backtest_dashboard.html` — KPI strip, **coloured headline summary**
  (calibration / selection / bottom-line cards, green/amber/red), reliability
  bins, match table — all regenerated each run.

Both are exposed by the FastAPI server in production:

- **Dashboard:** https://web-production-9e0f9.up.railway.app/backtest
- **Workbook:** https://web-production-9e0f9.up.railway.app/backtest.xlsx

Server routes are registered before the SPA fallback so they take
precedence over the React app's catch-all.

Critical invariant: `desk/backtest/replay.py` never imports from
`desk/sports/football/ingest/` — guarantees no run leaks today's data
into a 2022 fixture. Asserted by a test that scans the source for
forbidden import prefixes.

To refresh what Railway serves: re-run the backtest locally, commit
the regenerated `desk_backtest_*.{xlsx,html}` files, push to
`staging` first, eyeball, then merge into `init/project-setup`.
Railway redeploys on every push to either branch.

### Quick start

```bash
cd desk
python -m pip install -e ".[dev]"
pytest                                      # 172 tests, all green

python -m desk sports                       # list registered sports
python -m desk run --once                   # live pipeline → data/output/football/*.json
python -m desk match fb-wc26-fra-mex-20260612
python -m desk outrights                    # MC-sim WC26 winner market → data/output/outrights/
python -m desk backtest --tournament wc-2022 # historical replay → workbook + dashboard

# News-signals subsystem (gated on env vars on Railway; freely runnable locally)
python -m desk signals validate              # load + report the source seed (fails loud on bad rows)
python -m desk fetch-signals                 # 13 RSS feeds → desk/data/signals.db (~30s, free)
python -m desk fetch-signals --include-long-tail  # also pull GDELT (paid: external API)
python -m desk extract-signals               # Haiku reads cached items → Signals (needs ANTHROPIC_API_KEY)
python -m desk extract-signals --limit 25    # cap items per source per run (cost guard)

# External data layer (Phase 2+ — needs API_FOOTBALL_KEY / OPENWEATHERMAP_API_KEY)
python -m desk verify-data-sources            # smoke-test both keys + report api-football tier (guardrail 4)
python -m desk fetch-rank-form                # refresh form_delta for every WC26 team (1 /teams + 1 /fixtures per team)
python -m desk fetch-rank-form --iso3 fra --iso3 bra  # smoke-test on a subset
python -m desk rate-budget                    # api-football daily-call budget vs Pro cap (closes spec §4.1)
python -m desk fv-ingest-outcomes             # pull resolved match outcomes into forward_validation.db
python -m desk fv-report                      # forward-validation calibration report (§1.4 gate check)
python -m desk fetch-elo                      # Phase 1b — live Elo (eloratings + clubelo); free, no key
python -m desk b3-audit                       # Phase B.3 source audit (BEFORE flipping DESK_INJURY_FETCH)
python -m desk fetch-injuries                 # Phase B.3 — per-team injuries + bounded Elo penalty
python -m desk fetch-lineups --window-hours 2 # Team-news Slice B — confirmed XI for fixtures in next 2h
python -m desk fetch-lineups --window-hours 24 # daily tick variant — catches kickoffs >18h away
python -m desk fetch-cards                     # Squad-paragraph Q5 — per-team card accumulation (WC26)
python -m desk fetch-cards --iso3 fra --iso3 bra  # smoke-test on a subset
python -m desk schedule --once                # PR 6 — single refresh-loop tick (cron-friendly)
python -m desk fetch-odds                      # Non-US pivot — pull Pinnacle / Betfair / WilliamHill / SkyBet (EPL h2h)
python -m desk fetch-odds --sport-key soccer_epl --regions uk,eu  # default form

# Social automation (Phase 1; needs DESK_SOCIAL_ENABLED=1 to actually draft)
python -m desk social draft-daily             # pick today's best Pick → render → caption → queue
python -m desk social draft-weekly            # build Sunday roundup → render → caption → queue
```

### Layout

```
desk/
├── pyproject.toml
├── desk/
│   ├── config.py                     # env + thresholds + paths
│   ├── sport.py                      # Sport ABC + FixtureRef
│   ├── ingest/                       # SOURCE-AGNOSTIC ingest
│   │   ├── base.py                   # Source ABC + auto-registry (used by v2 admin)
│   │   ├── polymarket.py             # gamma client (live)
│   │   ├── polymarket_prices.py      # gamma → MarketSnapshot
│   │   └── kalshi*.py                # stubs; v1.1 wires live
│   ├── verdict/
│   │   ├── thresholds.py             # 3.0 / 1.0 / -2.0 pp; .env override
│   │   ├── compare.py                # MarketSnapshot.best_for(side)
│   │   ├── liquidity.py              # extreme-price guard (PR 4.5)
│   │   └── decide.py                 # Pick / Pass / Avoid + lower-bound gate (A.3)
│   ├── explainer/
│   │   ├── voice.py                  # banned phrases / no exclamation / no emoji
│   │   ├── stub.py                   # templated fallback copy + press chorus
│   │   ├── haiku.py                  # PR 5 — Haiku blurb-writer (forced tool-use; gated on DESK_BLURB_HAIKU=1). Includes the TEAM NEWS POLICY section + starter-highlight prompt + post_check team-news guards.
│   │   └── __init__.py               # dispatcher: Haiku → stub fallback on any failure
│   ├── publish/
│   │   ├── contract.py               # Pydantic v2 — single source of truth
│   │   ├── writer.py                 # atomic per-match + index.json
│   │   └── etag.py                   # SHA-256 of canonical JSON
│   ├── sports/
│   │   ├── __init__.py               # SPORT_REGISTRY (football only in v1)
│   │   └── football/
│   │       ├── sport.py              # FootballSport(Sport)
│   │       ├── fixtures.py           # Polymarket → FixtureRef
│   │       ├── priced.py             # (FixtureRef, MarketSnapshot) pairs
│   │       ├── features_builder.py   # FixtureRef → FootballFeatures
│   │       ├── model.py              # Elo + host + home + altitude
│   │       ├── teams.py              # team-id system + competition map
│   │       ├── data/                 # Elo seed, WC26 venues, club grounds
│   │       ├── ingest/               # Elo intl/club readers (v1: seed)
│   │       ├── metadata/             # FIFA + club adapters
│   │       ├── signals_glue.py       # FixtureRef → registry tag set (country/league/club)
│   │       ├── hard_signals.py       # Signal → bounded Elo adjustment (PR F)
│   │       └── team_news.py          # TeamNews payload (PlayerAbsence + LineupStatus + materiality) fused from api-football injuries + RSS hard signals
│   ├── signals/                      # NEWS-SIGNALS subsystem (sport-agnostic)
│   │   ├── models.py                  # Source / SourceItem / Signal Pydantic v2
│   │   ├── registry.py                # CSV seed loader (fail-loud per row)
│   │   ├── resolve.py                 # fixture tag set → sources_for()
│   │   ├── canonical.py               # tracker-stripping URL normaliser
│   │   ├── parse.py                   # stdlib RSS 2.0 + Atom parser
│   │   ├── aggregator.py              # GDELT 2.0 DOC API client
│   │   ├── fetch.py                   # http GET → cache (polite 10-min gate)
│   │   ├── cache.py                   # SQLite cache (items + extractions)
│   │   ├── extract.py                 # Extractor protocol + AnthropicExtractor (Haiku, prompt-cached)
│   │   ├── editorial.py               # build_citations + find_consensus
│   │   ├── hard_track.py              # hard_signals_for() — track gate + recency
│   │   ├── runtime.py                 # SignalsRuntime: opens cache, yields citations/hard signals per fixture
│   │   └── data/sources_seed.csv      # the 21-row global seed (verified 2026-05-21)
│   ├── data/                          # EXTERNAL data layer (Phase 2+ providers)
│   │   ├── api_football/              # api-football.com v3 — RANK + FORM (B.1) and INJURIES + LINEUP (B.3)
│   │   │   ├── client.py              # async httpx wrapper, auth header, error buckets
│   │   │   ├── status.py              # /status probe → plan tier + daily quota
│   │   │   ├── cache.py               # sqlite — team_resolution + fixture_results + form_deltas (with Citation)
│   │   │   ├── wc26_registry.py       # canonical ISO3 → /teams?search= display name
│   │   │   ├── teams.py               # resolve_team_id — bootstrap canonical ↔ api-football team_id
│   │   │   ├── fixtures.py            # fetch_recent_fixtures — last-N normalised per team
│   │   │   ├── form.py                # compute_form_delta — weighted PPG vs LONG_RUN_BASELINE_PPG
│   │   │   ├── sanity.py              # plausibility gates per data-layer spec §3.7
│   │   │   ├── coverage.py            # pre-publish coverage report per spec §3.3
│   │   │   ├── rate_budget.py         # worst-case daily-call vs Pro cap (§4.1)
│   │   │   ├── refresh.py             # refresh_all — orchestrator the CLI + loop call into
│   │   │   ├── injuries.py            # Phase B.3 /injuries client + source audit
│   │   │   ├── injuries_refresh.py    # walk WC26 registry → cache injury rows + Elo penalty
│   │   │   ├── injury_penalty.py      # bounded position-weighted Elo penalty
│   │   │   ├── lineups.py             # Slice B — /fixtures/lineups client + fixture-id resolver
│   │   │   ├── lineups_refresh.py     # window-scoped batch refresh + kickoff filter
│   │   │   └── runtime.py             # APIFootballRuntime — read-only hot path over cache
│   │   └── openweathermap/            # OpenWeatherMap One Call 3.0 — WEATHER (B.2; deferred)
│   │       ├── client.py              # async httpx wrapper, appid query auth
│   │       └── status.py              # cheapest-call probe → key works + sample temp
│   ├── verdict/
│   │   ├── ...
│   │   └── forward_validation.py      # Phase B Shadow-mode prediction logger (sqlite)
│   ├── distribute/                   # OUTBOUND wire to external consumers (MTA)
│   │   ├── config.py                 # env reader; fail-loud on push=1 without URL/secret
│   │   ├── signing.py                # HMAC-SHA256 over "{ts}.{body}"
│   │   ├── outbox.py                 # SQLite durable queue (collapse by match_id)
│   │   ├── client.py                 # httpx async client → Ok|Retryable|Permanent
│   │   ├── worker.py                 # drain_once: token-bucketed dispatch + backoff
│   │   ├── enqueue.py                # canonical_body + enqueue_match (runner-facing)
│   │   └── withdrawn.py              # detect_and_emit: prior_index − current → withdrawn payloads
│   ├── outrights/                    # PARALLEL pipeline for tournament-winner markets
│   │   ├── ingest_polymarket.py      # gamma client for WC winner event
│   │   ├── wc26_data.py              # bracket structure + Elo seed
│   │   ├── model.py                  # MC sim — 10k baseline + 100×1k bootstrap
│   │   ├── decide.py                 # YES/NO position ladder + lower-bound gate
│   │   ├── explainer.py              # outright copy templates
│   │   ├── publish.py                # per-team ladder + JSON writer
│   │   └── run.py                    # end-to-end orchestrator
│   ├── backtest/                     # READ-ONLY side workflow
│   │   ├── tournaments.py            # WC 2022 + future tournaments
│   │   ├── historical/               # Elo / markets / results loaders
│   │   ├── replay.py                 # SnapshotRow + replay_match (no live ingest!)
│   │   ├── writers/                  # xlsx + dashboard regenerators
│   │   └── runner.py                 # run_backtest() orchestrator
│   ├── runner.py                     # run_once() — full live pipeline
│   ├── cli.py                        # `desk run / sports / match / outrights / backtest / distribute-drain / fetch-signals / extract-signals / signals validate`
│   └── contract.schema.json          # generated; in-sync test enforces
├── CONTRACT_CHANGELOG.md             # public contract changelog — additive-only by default, breaking changes require ADR
├── docs/adr/                         # ADRs (0001 = withdrawn verdict state)
├── tests/                            # 553 green
└── data/
    ├── output/football/              # live per-match JSON + index.json (WC26-only by default)
    ├── output/outrights/              # live per-outright JSON + index.json
    ├── signals.db                    # news-signals cache (gitignored locally; on Railway the path is overridden via DESK_SIGNALS_DB_PATH to a mounted volume so the cache survives deploys)
    └── backtest/                     # frozen Elo snapshots + manual CSVs
```

### Sport boundary (non-negotiable)

Anything sport-specific lives under `desk/sports/{sport}/`. Anything sport-agnostic (`verdict/`, `publish/`, `runner.py`, `scheduler.py`, `cli.py`) **never** imports from a sport package — only through the `Sport` Protocol. Adding tennis later = a new package, not a refactor.

### Match-id format

`{sport_short}-{competition}-{team_a}-{team_b}-{yyyymmdd}` — e.g.

- `fb-wc26-fra-mex-20260612` (national: ISO3 lowercase)
- `fb-epl-mun-liv-20260815` (clubs: `{league}-{short}`)
- `fb-ucl-bay-psg-20260506`

Team-id resolution prefers the Polymarket *title* (display name → ISO3 via `iso3_for_name` in `desk/sports/football/teams.py`) over the *slug* code, because Polymarket reuses some slug codes — e.g. `kor` means both Korea Republic and Curaçao (Papiamento "Kòrsou"). When extending to a new competition, add the missing teams to `_NAME_TO_ISO3` in that file.

### Outright winner contract

Separate from per-match. Engine: `desk/outrights/` (parallel pipeline — MC sim of the tournament, 10k baseline + 100×1k bootstrap). Output: one JSON per outright at `desk/data/output/outrights/{outright_id}.json` + a sibling `index.json` manifest. Today's only outright is `fb-wc26-winner`. Each row in the JSON's `ladder[]` carries a single team with both sides:

```json
{
  "team": "Argentina",
  "model_p": 0.148,
  "model_p_lower": 0.090,
  "model_p_upper": 0.220,
  "yes_market_p": 0.084,
  "no_market_p":  0.916,
  "yes_edge_pp": 6.48,
  "no_edge_pp":  -6.48,
  "yes_lower_edge_pp": 0.65,
  "no_lower_edge_pp":  -7.15,
  "verdict": "pass",
  "pick_side": null
}
```

A per-team verdict is `"pick"` only when the better side's `lower_edge_pp` clears the Pick threshold (default +3.0pp); otherwise `"pass"`. Avoid is structurally impossible on this market shape — see `desk/outrights/decide.py`.

### Server routes (read-only)

The Prophet server mounts the desk output at `/api/desk/*` (see `desk_api.py`) and renders the static site at `/`, `/matches`, `/m/{id}`, `/outrights`, `/o/{id}` (rendered by `site/generate.py` from `desk/data/output/`). Match pages carry a `<section class="sources">` block under the blurb (added 2026-05-21 in `4bd50cf`) — one row per `editorial_citations[]` entry: outlet name as an external link, published date, verbatim quote in italic blockquote. Mirrors the `drivers` block styling.

| Path | Returns |
|---|---|
| `/api/desk/matches?competition=wc26` | Match list with verdicts |
| `/api/desk/match/{match_id}` | Full MatchOutput JSON |
| `/api/desk/outrights` | Outright index |
| `/api/desk/outright/{outright_id}` | Full outright JSON (model + ladder + verdict) |
| `/outrights/wc26` | Stable shortlink to `/o/fb-wc26-winner` |
| `/backtest` / `/backtest.xlsx` | Backtest dashboard + workbook |

### Verdict thresholds (locked, env-overridable)

| State | Rule |
|---|---|
| Pick | `model_p − best_market_p ≥ 3.0pp` for some side |
| Pass | every side: `\|model_p − best_market_p\| < 1.0pp` |
| Avoid | every side: `model_p − best_market_p ≤ −2.0pp` |

Override via `DESK_PICK_PP` / `DESK_PASS_PP` / `DESK_AVOID_PP` in `.env`.

### Other Desk env vars

| Variable | Default | Purpose |
|---|---|---|
| `DESK_COMPETITIONS` | `wc26` | Comma-separated allowlist of competition codes that pass the live football ingest. Set to `*` to disable filtering. |
| `DESK_OUTPUT_DIR` | `desk/data/output` | Where the publisher writes per-match + per-outright JSON |
| `DESK_OPS_USER` | unset | Username for the internal ops dashboard at `/desk/ops`. Both this and `DESK_OPS_PASS` must be set or the page + `/api/desk/ops/*` 404 (disabled-by-default — Railway-only surface). Layout: Run history (last 5) at top; clicking a row loads Sources read + News signals for that run below. Frontend fetches `/runs?limit=5` first, then the selected run by id — no `/latest` dependency. |
| `DESK_OPS_PASS` | unset | Password for the ops dashboard. Set both on Railway to enable; leave unset locally to keep the surface invisible. |
| `DESK_OPS_RETENTION` | `200` | How many `RunReport` JSONs the recorder keeps before pruning the oldest. |
| `DESK_OPS_DIR` | unset → `{DESK_OUTPUT_DIR}/ops` | Where the ops dashboard's persisted state lives: `RunReport` history (`runs/*.json` + `index.json`), refresh-loop control state (`control.json`), per-Haiku-call cost ledger (`costs.jsonl`), and per-tick totals (`tick-totals.jsonl`). On Railway, point this at a mounted volume (e.g. `/data/ops`) so everything survives deploys — without it, every redeploy wipes the dashboard back to "no runs recorded yet" *and* drops control settings back to defaults. Honoured by writer (`desk/desk/runner.py`), reader (`desk_ops_api.py`), refresh loop (`desk_refresh_loop.py`), and cost ledger (`desk/desk/ops/cost.py`). |
| `DESK_OPS_EDGE_DELTA_PP` | `1.0` | Minimum |edge_pp| delta between consecutive runs that fires an `edge` change in the diff engine. |
| `ANTHROPIC_API_KEY` | unset | Required for `desk extract-signals` (Haiku). Without it, extraction exits non-zero — the rest of the pipeline still runs and the cache still fills via fetch, just no Signals are produced. |
| `DESK_AUTORUN` | `1` | Emergency kill switch for the background refresh loop. Set to `0` to disable the loop entirely on a given Railway service (skips the boot tick too). Day-to-day enable/disable + scheduled hours are controlled via the Ops dashboard's **Desk admin** page at `/desk/ops/admin` — that writes `{ops_root}/control.json` (`{ enabled, hours: [int 0..23] }`), which the loop polls on every scheduling decision. Leave this env var at default unless you need to pause without dashboard access. |
| `DESK_INITIAL_DELAY_SEC` | `60` | Delay before the first post-boot tick. Keep > 0 so the server can finish standing up before subprocesses spawn. |
| `DESK_FORCE_TICK_ON_BOOT` | `0` | Set to `1` to force a refresh tick on server boot regardless of `control.json`'s `enabled` / `hours` state. Useful for guaranteeing a fresh tick lands immediately after a deploy. Logged loud in the loop so the operator can confirm it fired. |
| `DESK_LINEUP_FETCH` | `0` | Set to `1` to run `desk fetch-lineups --window-hours 24` in the daily refresh tick. Pulls api-football `/fixtures/lineups` for any priced fixture kicking off within the next 24h + writes to the api-football cache. Needs `API_FOOTBALL_KEY`. Off by default. |
| `DESK_LINEUP_LOOP_ENABLED` | `0` | Master switch for the T-90m lineup polling loop (`desk_lineups_refresh_loop.py`). When `1`, the loop ticks every `DESK_LINEUP_LOOP_TICK_SEC` (default 900s / 15 min) and fetches lineups for fixtures kicking off in the next `DESK_LINEUP_LOOP_WINDOW_HOURS` (default 2h). On any successful fetch the loop also runs `desk run --once` + `site/generate.py` so the new starters land in the published JSON + static HTML before kickoff. ~16 calls/hr on a typical WC26 day — well under Pro tier's 7,500/day. |
| `DESK_LINEUP_LOOP_TICK_SEC` | `900` | Lineup-loop cadence (15 min). |
| `DESK_LINEUP_LOOP_WINDOW_HOURS` | `2` | How far ahead the lineup loop scans for kickoffs. |
| `DESK_LINEUP_LOOP_INITIAL_DELAY_SEC` | `120` | Delay before the lineup loop's first post-boot tick. |
| `DESK_LINEUP_LOOP_PUBLISH` | `1` | When `1`, the loop runs `desk run --once` + `site/generate.py` after every successful lineup fetch so blurbs reach the published surface immediately. Set to `0` to fetch-only (useful for debugging). |
| `DESK_TEAM_NEWS_BLURB_REQUIRED` | `0` | When `1`, the Haiku blurb writer's team-news + squad-paragraph guards become hard fails — a `materiality=high` blurb that doesn't name an absent player falls back to the stub, ditto for confirmed-lineup blurbs that don't mention a starter or formation, and (Q3) an at-risk player named within 6 words of "suspended"/"banned"/"missing"/"ruled out"/"out of" triggers a hard fail. Default `0` ships the guards as warnings only. |
| `DESK_CARD_FETCH` | `0` | Squad-paragraph Q1/Q5. Set to `1` to run `desk fetch-cards` in the daily refresh tick — pulls api-football `/players?team=&season=&league=` per WC26 team (one call/team, ~48/tick) and derives `at_risk = (yellows == threshold-1)` from `CARD_RULES[fx.competition_code]`. Needs `API_FOOTBALL_KEY`. **Flipped to `1` on staging + prod 2026-05-30 evening, before the WC26 yellow-card reset rule was verified against the 2026 FIFA regs.** Outstanding operator action: confirm the wipe-after-QF assumption (carried over from 2022) is still the live rule; post-QF at-risk flags will be wrong otherwise. |
| `DESK_CARD_AT_RISK` | `1` | Squad-paragraph Q2. When `1`, at-risk-card `CardStatus` rows are threaded into the per-team `TeamNews` payload so the Haiku writer can mention them in the squad paragraph. Set `0` to ship bans-only (suppress at-risk surfacing) while the at-risk derivation is being eyeballed. Cards data still fetches when `DESK_CARD_FETCH=1` — this flag only controls what reaches the prompt. |
| `DESK_SIGNALS_FETCH` | `0` | Set to `1` to enable the RSS fetch step on every refresh tick in `desk_refresh_loop.py`. Off by default so a fresh deploy doesn't hit external services until the operator opts in. |
| `DESK_SIGNALS_EXTRACT` | `0` | Set to `1` to enable the Haiku extraction step on every refresh tick. Needs `ANTHROPIC_API_KEY` to actually run; logs a warning + skips if the key isn't present. |
| `DESK_SIGNALS_EXTRACT_LIMIT` | unset | Optional per-source-per-tick cap on extraction. E.g. `25` keeps steady-state Anthropic cost predictable while the source set is being tuned. |
| `DESK_SIGNALS_DB_PATH` | unset → `desk/data/signals.db` | Override the signals cache path. **Set this on Railway** to a mounted volume (e.g. `/data/signals.db`) so the news-signals cache survives deploys — without it, every redeploy wipes `signals.db` and the first post-deploy tick publishes matches with no citations. Honoured by both writers (`desk fetch-signals`, `desk extract-signals`) and reader (`SignalsRuntime.for_sport` in `desk/desk/runner.py`). |
| `DESK_HARD_SIGNAL_INJURY_ELO` | `8.0` | Magnitude of the Elo penalty applied for a single confirmed injury signal (from a `can_feed_model` source, inside the late-binding window). |
| `DESK_HARD_SIGNAL_SUSPENSION_ELO` | `6.0` | Same, for confirmed suspensions / bans. |
| `DESK_HARD_SIGNAL_MAX_ELO` | `30.0` | Hard per-team cap on total hard-signal Elo penalty. Multiple injuries cumulate but never below this floor. |
| `DESK_HARD_SIGNAL_WINDOW_DAYS` | `5` | Late-binding window. A hard signal only adjusts Elo when the fixture's kickoff is within this many days. Outside the window, the path is a no-op. |
| `DESK_BLURB_HAIKU` | `0` | Set to `1` to route the explainer's title/summary/blurb through `desk/desk/explainer/haiku.py` (Haiku 4.5, system prompt sourced from `desk/VOICE.md`). Needs `ANTHROPIC_API_KEY`. Off by default — without it, the templated stub still ships. |
| `DESK_BLURB_HAIKU_MODEL` | `claude-haiku-4-5` | Override the Haiku model id. Useful for pinning a specific haiku build. |
| `DESK_FORM_RANK_RESIDUAL` | `0` | Set to `1` to activate the Phase B.1 form / FIFA-rank residual on the Elo prior (per `THE_DESK_OPTIMIZATION_SPEC.md` §4.B.1). Off by default — the hook lives in Shadow until data-layer Phase 2 populates `FootballFeatures.team_*_form_delta` + `team_*_rank_residual` with real values via API-Football. With the flag off (or with all residual fields None), `_adjusted_elos` is byte-identical to pre-B.1; the regression gate is the WC-2022 backtest. |
| `API_FOOTBALL_KEY` | unset | api-football.com v3 key (direct `api-sports.io` endpoint, header `x-apisports-key`). Phase 2 spine: RANK + FORM (B.1) and INJURIES + LINEUP (B.3). Spec's $19/mo "Pro" tier = 7,500 req/day; smoke-test the live account with `python -m desk verify-data-sources`. |
| `OPENWEATHERMAP_API_KEY` | unset | OpenWeatherMap One Call 3.0 key for Phase 3 weather (B.2). Free tier ≈ 1,000 calls/day; overage capped at ≈ $1/mo per `THE_DESK_DATA_LAYER_SPEC.md` §4.1. Same smoke-test command verifies it. |
| `DESK_RANK_FORM_FETCH` | `0` | Set to `1` in `desk_refresh_loop.py` to run `desk fetch-rank-form` once per tick. Needs `API_FOOTBALL_KEY` (logs a warning + skips if unset). Cost: ~70 calls/tick (1 per WC26 team), well under the 7,500/day Pro cap. Off by default — a fresh deploy doesn't burn api-football quota until you opt in. |
| `DESK_API_FOOTBALL_DB_PATH` | unset → `desk/data/api_football.db` | Override the api-football cache path. **Set this on Railway** to a mounted volume (e.g. `/data/api_football.db`) so cached team_ids + fixture history + form_delta values survive deploys. Without it, every redeploy wipes the cache and the first post-deploy tick burns ~70 calls re-resolving everything. |
| `DESK_FORWARD_VALIDATION_DB_PATH` | unset → `desk/data/forward_validation.db` | Override the forward-validation logger's sqlite path. Should sit on the same mounted volume as `DESK_API_FOOTBALL_DB_PATH` so the accumulated Shadow-mode prediction sample persists across deploys — without it the ≥100-fixture forward-validation threshold resets every time. |
| `DESK_ELO_FETCH` | `0` | Set to `1` to run `desk fetch-elo` per scheduled tick. Free providers (eloratings.net + api.clubelo.com); no vendor key required. Off by default so a fresh deploy doesn't fetch until the operator opts in. |
| `DESK_ELO_DB_PATH` | unset → `desk/data/elo.db` | Override the live-Elo cache path. Set this on Railway to a mounted volume so cached values survive deploys. |
| `ODDS_API_KEY` | unset | The Odds API (`the-odds-api.com`) key — non-US sportsbook + exchange adapter (Pinnacle, Betfair Exchange UK/EU, William Hill, Sky Bet). Reads `regions=uk,eu`, market `h2h`. Cost: 1 credit per region per call (so the default fetch costs 2 credits per sport key per tick). Smoke-test with `python -m desk verify-data-sources`. |
| `DESK_ODDS_FETCH` | `0` | Set to `1` to run `desk fetch-odds` once per scheduled tick. Needs `ODDS_API_KEY` (logs a warning + skips if unset). Pulls h2h prices for the sport keys in `DESK_ODDS_SPORT_KEYS` (default: `soccer_fifa_world_cup`) into `desk/data/oddsapi.db`. **Independent from `DESK_CROSS_VENUE_EDGE`** — the operator can prime the cache without flipping the verdict surface. Off by default. |
| `DESK_ODDS_SPORT_KEYS` | unset → `soccer_fifa_world_cup` | Comma-separated Odds API sport_keys to fetch each tick. Default = WC26 only (matches the default `DESK_COMPETITIONS=wc26` site filter). Add EPL with `soccer_fifa_world_cup,soccer_epl`. Cost: 2 credits per sport_key per tick on `regions=uk,eu`. |
| `DESK_CROSS_VENUE_EDGE` | `0` | Master flag for the non-US pivot (per ADR 0004 + `THE_DESK_NONUS_SPORTSBOOK_SCOPING.md`). When `0` (default + WC-2022 backtest path), the verdict's `edge_pp` is computed against `best_for(side).implied_p` exactly as before and the publisher emits `market_prices=[]` / `consensus_fair=null` — payloads byte-identical to pre-pivot. When `1`, the verdict ranks by **true price** (`e` = implied + fee + spread + commission per venue type) and the publisher emits the per-side, per-venue `market_prices` block + the sharp-weighted `consensus_fair`. |
| `DESK_ODDS_API_DB_PATH` | unset → `desk/data/oddsapi.db` | Override the odds-API cache path. **Set this on Railway** to a mounted volume (e.g. `/data/oddsapi.db`) so cached events + per-venue price rows survive deploys. Without it, every redeploy wipes the cache and the first post-deploy tick burns 2+ credits re-fetching. |
| `DESK_DEVIG_METHOD` | `multiplicative` | Pluggable de-vig method seam. Only `multiplicative` is implemented in v1 (asks for `shin` / `power` raise `NotImplementedError` — silent fallback would defeat the point of asking). |
| `DESK_REGION` | `non-us` | Tags the audience bucket on every published `MatchOutput` (`us` or `non-us`). Lets the front-end serve the right venue set without re-deriving from the URL list. |
| `DESK_INJURY_FETCH` | `0` | Set to `1` to run `desk fetch-injuries` per scheduled tick. **Only flip this after `desk b3-audit` clears** — otherwise we burn ~70 api-football calls/tick on data we'll have to throw away. |
| `DESK_INJURY_PENALTY` | `0` | Set to `1` to apply the Phase B.3 bounded per-team injury Elo penalty to published verdicts. Stays off until a `desk fv-report` shows the with-residual+with-penalty Brier doesn't regress against the published path. Data side fills the feature regardless; the flag only controls what reaches the verdict. |
| `DESK_DISTRIBUTE_PUSH` | `0` | Set to `1` to enable the push wire to Market Tips AI (see `desk/desk/distribute/`). Runner enqueues every `write_match` + every withdrawn payload; `desk_distribute_loop.py` drains every 30s via `python -m desk distribute-drain`. Off by default — a fresh deploy does not push until the operator opts in. |
| `DESK_DISTRIBUTE_INCLUDE_CROSS_VENUE` | `0` | When `0` (default), strips the ADR 0004 fields (`market_prices`, `consensus_fair`, `region`) from the **wire body only** — disk writes still carry the full payload. This exists because MTA's strict validator (`extra="forbid"`) rejected unknown fields as `400 Invalid request` when v1.3 of the contract first hit prod on 2026-05-31. Flip to `1` once MTA confirms its schema is updated and ready to accept the new optional fields. |
| `DESK_DISTRIBUTE_WEBHOOK_URL` | unset | MTA webhook URL — prod `https://markettipsai.com/api/webhooks/desk/publish`. Required when `DESK_DISTRIBUTE_PUSH=1`; `load_config()` fails loud at boot if either this or the secret is missing. |
| `DESK_DISTRIBUTE_WEBHOOK_SECRET` | unset | HMAC-SHA256 shared key for the push wire. Coordinated with MTA via encrypted channel (no commits, no logs). |
| `DESK_DISTRIBUTE_DB_PATH` | unset → `desk/data/distribute.db` | Outbox sqlite path. **Set this on Railway** to a mounted volume (e.g. `/data/distribute.db`) so in-flight rows survive deploys — without it, a redeploy mid-retry loses the row and MTA never sees the payload. |
| `DESK_DISTRIBUTE_RATE_PER_MIN` | `50` | Token-bucket cap on outbound POSTs per sweep. Sits comfortably under MTA's 60-req/min/source-IP ceiling. |
| `DESK_DISTRIBUTE_MAX_IN_FLIGHT` | `8` | Per-sweep concurrency cap. |
| `DESK_DISTRIBUTE_MAX_BYTES` | `60000` | Pre-send body-size guard. Contract bounds put worst-case JSON at ~32KB; the guard exists to fail loudly on contract drift before a 413 round-trip. |
| `DESK_DISTRIBUTE_TICK_SEC` | `30` | Drain-loop cadence (project-root async task). |
| `DESK_API_BEARER_TOKEN` | unset | Token for the bearer-gated external GET at `/api/desk/external/match/{match_id}` (single-match safety-net read for MTA). Shape `dtk_<32-byte URL-safe>`. **Without it the route 404s** — server.py omits the mount entirely so unconfigured deploys don't acknowledge the surface. |
| `DESK_SOCIAL_ENABLED` | `0` | Master switch for social automation. Set to `1` to enable the selector + scheduler hooks (`desk_refresh_loop.py` fires `desk social draft-daily` per tick; `social_weekly_cron.py` fires `desk social draft-weekly` on the configured schedule). Approval API mounts regardless — when `0` it just sees an empty queue. |
| `DESK_SOCIAL_DB_PATH` | unset → `desk/data/social.db` | Override the social-queue sqlite path. **Set on Railway** to a mounted volume so the draft queue + edit history survives deploys. |
| `DESK_SOCIAL_ASSETS_DIR` | unset → `desk/data/social_assets` | Override the carousel PNG output dir. **Set on Railway** to a mounted volume so rendered slides survive deploys; without it, an approved draft's bundle would 500 on redeploy. |
| `DESK_SOCIAL_MIN_EDGE_PP` | `2.0` | Selector skip threshold. Picks below this `edge_pp` don't get drafted. |
| `DESK_SOCIAL_WEEKLY_DAY` | `sunday` | Weekday for the roundup cron (case-insensitive). |
| `DESK_SOCIAL_WEEKLY_AT` | `09:00` | UTC time-of-day for the roundup cron (HH:MM). |
| `DESK_SOCIAL_PUBLISH_MODE` | `manual` | `manual` (Phase 1; operator posts by hand + uses Mark-as-posted) or `api` (Phase 2; auto-posts via IG Graph + X v2). `api` mode requires all six `IG_*` / `X_*` creds to be set together — `load_config()` fails loud at boot otherwise. |
| `IG_ACCESS_TOKEN` / `IG_BUSINESS_ACCOUNT_ID` | unset | Phase 2 only — Meta Graph API long-lived access token + the `@oddsprimer` IG Business account id. Required when `DESK_SOCIAL_PUBLISH_MODE=api`. |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_SECRET` | unset | Phase 2 only — X API v2 OAuth 1.0a credentials. Required when `DESK_SOCIAL_PUBLISH_MODE=api`. |

### Output contract (what the website consumes)

Schema lives in `desk/contract.schema.json`. Sample:

```json
{
  "match_id": "fb-wc26-fra-mex-20260612",
  "sport": "football",
  "competition": { "code": "wc26", "label": "FIFA World Cup 2026", "stage": "group_d" },
  "kickoff_utc": "2026-06-12T19:00:00Z",
  "team_a": "France",
  "team_b": "Mexico",
  "venue": { "city": "Guadalajara", "stadium": "Estadio Akron", "country": "MX" },
  "market_outcomes": ["a", "draw", "b"],
  "verdict": {
    "state": "pick",
    "side": "France",
    "market_venue": "polymarket",
    "price": "-180",
    "edge_pp": 4.2
  },
  "copy": {
    "title": "...", "summary": "...", "blurb": "...",
    "citations": [...],
    "editorial_citations": [
      {
        "outlet":         "The Guardian (football)",
        "url":            "https://www.theguardian.com/football/...",
        "quote":          "He will be an important player in this World Cup.",
        "quote_original": null,
        "quote_lang":     null,
        "published_at":   "2026-05-19T15:00:00Z"
      }
    ]
  },
  "updated_at": "2026-06-12T17:00:00Z"
}
```

Internals (`p_a/p_draw/p_b`, drivers, raw market prices, raw `Signal` objects, the registry itself) **stay inside The Desk**. Adding a contract field requires an ADR.

`copy.editorial_citations` was added news-signals PR D — additive (legacy `copy.citations` URL list preserved). Each entry carries the outlet's display name, deep link, verbatim English quote, plus the source-language original + ISO-639-1 lang for translated quotes.

---

## Activity signals — anonymous views + reactions

Anonymous reader engagement on every match card. Built 2026-05-27. The widget renders:

- **Top activity strip** (only when there's data): "N users viewed this market today" · "Most picked: \<side\>" · "Community leaning: PICK/PASS/AVOID".
- **Reaction chips:** 🐂 Bullish · 💸 Overpriced · 🪤 Trap line · 💎 Value. Cookie-tracked per anon, one vote per match per anon, mutable for 24h then locked.
- **Italic hint:** "Anonymous · one click · no account".

Lives inside the `.lv-card` CSS grid with `grid-column: 1 / -1` and `pointer-events: auto` (overriding the card's overlay-link cascade). Chip clicks call `stopPropagation` so voting on a listing card doesn't navigate to `/m/{id}`.

### Layout

```
activity/
├── __init__.py
├── db.py                      # asyncpg pool (timeout=5s — see "asyncpg lifespan" below)
├── anon.py                    # op_anon cookie + daily-salted IP hash
├── router.py                  # POST /view, POST /vote, GET /{match_id}
└── jobs.py                    # aggregator, seeder, prune
activity_refresh_loop.py       # project-root async loop, sibling to desk_refresh_loop.py
migrations/
├── README.md
└── 20260527_activity_signals.sql
site/public/js/activity.js     # vanilla-JS island (CSS inline, scoped under .lv-card)
tests/activity/
├── test_api.py                # 16 router tests with a faked asyncpg pool
└── test_jobs_helpers.py       # 16 stage/popularity/distribution unit tests
```

### Why Postgres (the only Postgres-backed domain)

Ledger / signals / distribute / prophet all use sqlite. Activity broke that pattern because every match-page load fires `POST /view` from many concurrent readers — sqlite's single-writer model would push lock errors under launch traffic. Railway Postgres add-on handles concurrent writes natively; the connection is **DATABASE_URL** (private network), never `DATABASE_PUBLIC_URL` (egress fees).

### asyncpg lifespan — must stay defensive

`activity/db.py:open_pool()` passes `timeout=5.0` to `asyncpg.create_pool(...)`. **Do not remove this.** asyncpg's default `timeout` is `None` (wait forever). Without the explicit timeout, a misconfigured `DATABASE_URL` hangs FastAPI's lifespan startup indefinitely — uvicorn never accepts connections, every route on the site goes dark, and Railway serves edge 404s. This actually took prod down on 2026-05-27 before the timeout was added. Both `server.py` lifespan and `activity_refresh_loop.py` wrap `open_pool()` in `try/except` so a pool failure only takes activity routes offline, not the whole app.

### Background jobs

| Job | Cadence | Body |
|---|---|---|
| `aggregate_match_activity` | 60s | One SQL UPSERT — recomputes `match_aggregates` from `match_views` + `match_reactions` for every match with any rows. |
| `seed_match_activity` | 8 min | Inserts popularity-weighted seed rows toward stage targets (Tier 1–4 × popularity × time-of-day × verdict-state distribution). Auto-decays per match when real views ≥ 60 AND real votes ≥ 25. Capped at 450 views/day · 70 votes lifetime. |
| `prune_old_views` | daily | `DELETE FROM match_views WHERE viewed_at < now() - 7 days`. Aggregate counts preserved. |

### Frontend race-condition fix worth remembering

The aggregator runs every 60s, so a `GET /api/activity/{id}` issued within that window after a vote returns stale `by_reaction` counts even though `your_vote` is correct (it's read live from `match_reactions`, not the aggregate). Two guards in `activity.js`:
1. After a successful vote, optimistic local bump of `by_reaction[next] += 1` (and decrement of the old vote on a flip).
2. `reconcile(data)` runs at the end of every refresh — if `data.your_vote` is set but `data.by_reaction[your_vote]` is 0, force it to 1.
3. **No immediate `refresh()` after a vote** — it would race the optimistic state. Wait for the next 90s interval poll.

### Design decisions

| Decision | Source |
|---|---|
| Top-level `activity/` package, not under `desk/` | Cross-cutting concern, mirrors `ledger/` |
| Vanilla-JS island in `site/generate.py`, not React | The `/m/{id}` surface is static HTML, not the React app |
| Lazy 24h vote lock — no daily sweep job | The 409 on next vote enforces it; sparse `locked_at` is harmless |
| Same 4 reaction values in DB across all designs | UI relabels per design + verdict state; no schema churn during A/B |
| `DATABASE_URL` referenced into the Prophet app (not typed) | Private network, zero egress, single source of truth |

### Env vars

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | unset | Required. Reference (not type) from the Postgres service into the Prophet app. App lifespan opens the asyncpg pool on boot if this is set. |
| `ACTIVITY_DB_POOL_MAX` | `10` | asyncpg pool max connections. Hobby-tier Postgres has a low ceiling — keep tiny. |
| `ACTIVITY_SEED_ENABLED` | `1` | Set to `0` to disable the seeder loop entirely (used on staging during UX testing so the operator's own clicks are the only data). |
| `ACTIVITY_AGGREGATE_SEC` | `60` | Aggregator job cadence. |
| `ACTIVITY_SEED_SEC` | `480` | Seeder job cadence (8 min). |
| `ACTIVITY_PRUNE_SEC` | `86400` | Prune job cadence (daily). |
| `ACTIVITY_INITIAL_DELAY_SEC` | `30` | Delay before the first post-boot tick of any activity job. |
| `ACTIVITY_IP_SALT` | unset → process-local random | Per-deployment secret prepended to the IP hash. Without it the salt resets on every restart (acceptable — hash is only used for same-day rate-limit buckets). |

### CTA click tracking

A fourth POST endpoint — `/api/activity/cta` — logs every market CTA click to a `cta_clicks` table (`migrations/20260529_cta_clicks.sql`). The site stamps every `<a>` that links to Polymarket or Kalshi with `data-match-id` + `data-cta-venue="polymarket|kalshi"` (see `_cta_pill` and the `render_match_page` cta-row in `site/generate.py`). A capture-phase delegated listener in `site/public/js/activity.js` calls `navigator.sendBeacon('/api/activity/cta', ...)` on click (falls back to `fetch` with `keepalive` when sendBeacon is absent) — capture is required because the listing-card overlay link navigates in the bubble phase. Rows fire-and-forget; the daily report is the consumer. The `seeded` column mirrors the other activity tables so the report's `WHERE seeded = false` filter is consistent across all four.

### Spec + design history

`ACTIVITY_SIGNALS_SPEC.md` v1.0.1 is the locked spec. The user iterated through several designs in one afternoon: Editorial / Literal A/B → Literal only → Market Pulse v2 (incorporating the review doc) → back to v1 Literal. The shipped widget is v1 Literal with emoji chips. Untracked working-tree files left as design history: `activity_signals_mockup.html` (v1), `activity-signals-mockup-v2.html` (Market Pulse), `activity-signals-review.md` (critique arguing against the whole feature in favour of market-movement + "Track this Pick").

---

## Daily report

One-page HTML + PDF brief emailed once a day to `aaron@oddsprimer.com,adi.dagan@gmail.com`. Built from the activity tables (views / votes / CTA clicks for yesterday's UTC day, plus prior-day deltas), enriched with desk match labels + the latest `RunReport` + per-tick Anthropic cost.

### Layout

```
daily_report.py             # one-shot orchestrator + CLI (--once / --force / --dry-run / --date)
daily_report_loop.py        # hourly tick; fires run_once when utc_hour == DAILY_REPORT_HOUR
templates/daily_report.html # Jinja2 template; A4 @page; OP design tokens (Inter Tight + Source Serif 4 + JetBrains Mono)
tests/daily_report/         # config validation, window math, query helpers (faked asyncpg conn),
                            # enrichment readers, status_line, render smoke, idempotency, email assembly
```

### Behaviour

- Window = previous UTC day. Each KPI shows a ▲/▼/flat delta vs the day before.
- Every Postgres query filters `seeded = false` so the seeder traffic never appears in the report.
- The CTA query path is wrapped in `try/except`: a pre-migration deploy still produces a report (zero CTA counts) rather than 500.
- Idempotency: state file at `{ops_root}/daily_report/last_sent.json`. `--force` bypasses.
- Render: Jinja2 → HTML; WeasyPrint → PDF. Cairo / Pango / HarfBuzz now ship via `railpack.json`'s `deploy.aptPackages` so PDF actually renders in production. The fallback path stays in place: if WeasyPrint import *or* dlopen *or* render fails, the email goes HTML-only with a warning logged. (The dlopen failure throws `OSError` from inside Python — the import `try/except` catches both `ImportError` and `OSError`. Don't narrow it back to just `ImportError`.)
- Site-wide visitor metric — `q_site_visitors` counts `DISTINCT anon_id` across all `match_views` rows. `activity.js` fires a per-page-load `POST /view` with a sentinel match_id (`site:home`, `site:matches`, `site:outrights`, `site:learn`, `site:about`) so the count covers non-match surfaces too. Match-specific queries (`q_views`, `q_unique_anons`, `q_top_matches`) filter `match_id LIKE 'fb-%'` to exclude the sentinels.
- Email: smtplib + STARTTLS to Gmail SMTP. Gmail App Password lives in `SMTP_PASS` on Railway, never an account password.
- The loop runs hourly; the send fires at the top of `DAILY_REPORT_HOUR` UTC (default 8). A duplicate tick inside the same hour is a no-op (already-sent).

### Env vars

| Variable | Default | Purpose |
|---|---|---|
| `DAILY_REPORT_ENABLED` | `0` | Master switch. Set to `1` to enable the loop + arm fail-loud config validation. With `0`, missing SMTP/recipient env is allowed; `daily_report.py` exits cleanly with `reason="disabled"`. |
| `DAILY_REPORT_HOUR` | `8` | UTC hour at which the loop fires the daily send. |
| `DAILY_REPORT_TO` | unset | Comma-separated recipient list. Production target: `aaron@oddsprimer.com,adi.dagan@gmail.com`. |
| `DAILY_REPORT_FROM` | falls back to `SMTP_USER` | "From" header. Gmail will rewrite to the authenticated account regardless. |
| `DAILY_REPORT_ENV` | `staging` | Label rendered top-right of the report ("Daily report · Wed, 28 May 2026 · staging"). |
| `DAILY_REPORT_TICK_SEC` | `3600` | Loop tick cadence; rarely changed. |
| `DAILY_REPORT_INITIAL_DELAY_SEC` | `60` | First-tick delay so the server stands up before the loop arms. |
| `SMTP_HOST` | unset | SMTP server. Gmail: `smtp.gmail.com`. Required when `DAILY_REPORT_ENABLED=1`. |
| `SMTP_PORT` | `587` | SMTP port; STARTTLS enabled by default. |
| `SMTP_USER` | unset | SMTP auth user. For Gmail: `adi.dagan@gmail.com`. |
| `SMTP_PASS` | unset | SMTP auth password — Gmail **App Password** (16 chars), never the account password. |

### Ops dashboard surfacing

`GET /api/desk/ops/daily-report` (Basic-auth-gated alongside the other `/api/desk/ops/*` routes) reads `{ops_root}/daily_report/last_sent.json` and returns `{last_sent_date, sent_at}`. The Ops dashboard at `/desk/ops` renders this as a one-line "Daily report" section above External providers so the operator can see at a glance what date the most recent send covered and how long ago it went out. State file lives at the same path the sender writes to — no duplication.

### Spec history

The original build brief (`DAILY_REPORT_BUILD_SPEC.md`) and sample-PDF design lived outside the repo at the time of build (2026-05-29). The shipped layout follows the brief's structure: masthead → status banner → PART I Audience (KPI cards inc. **Unique visitors** site-wide, **Match views**, **Match readers**, Votes cast, CTA clicks → new-vs-returning row → busiest-hour row → CTA-by-venue list → top-5 matches → sentiment bars → zero-click picks → audience funnel) → 7-day uniques SVG chart (added 2026-05-29 in commit `016685e`; embedded inline so WeasyPrint renders it natively in the PDF) → PART II Desk health (last tick, verdict mix, tick cost, editorial changes, pipeline funnel).

---

## Tech stack

**Backend** Python 3.11+, httpx, websockets, cryptography, pandas, FastAPI, uvicorn, Pydantic v2, aiosqlite, asyncpg (activity signals only — Railway Postgres add-on), APScheduler (PR 6+), Anthropic SDK (Haiku for news-signals extraction + future PR 5 blurb generation — listed in root `requirements.txt` so the Railway image installs it; `desk/pyproject.toml` is **not** pip-installed in production, the package runs as a subprocess via PYTHONPATH), Jinja2 + WeasyPrint (daily report template + PDF rendering — Cairo/Pango/HarfBuzz now installed via `railpack.json`'s `deploy.aptPackages` so PDF renders in production; the HTML-only fallback path remains for any future env where the dlopen fails).

**Frontend** React 19, Vite, Recharts, Lucide React. The editorial site (`frontend/src/op/`), Ledger (`frontend/src/ledger/`), and Desk page (`frontend/src/desk/`) all use the Odds Primer Design System (`Odds Primer Design System/`) — Source Serif 4 (body), Inter Tight (wordmark + chrome), JetBrains Mono (numerics). All three share the locked tokens at `frontend/src/ledger/op-tokens.css`. The legacy Prophet trading dashboard at `/dashboard` still uses its older dark-theme tokens.

---

## Conventions

- **Work on `staging` by default.** Commit, push, check the staging URL. Feature branches are optional and only worth the overhead when two unrelated things are in flight at once.
- **`init/project-setup` is production.** Only receives merges from `staging` once changes have been eyeballed. Never push half-finished work straight to it.
- **Never commit `data/*.db`.** Already in `.gitignore` (covers root `data/*.db` AND `desk/data/*.db`). The news-signals cache lives at `desk/data/signals.db` locally; on Railway the path is overridden via `DESK_SIGNALS_DB_PATH` to a file on the mounted `/data` volume so the cache survives container restarts and deploys.
- **Desk output JSON lives on the Railway volume too.** `DESK_OUTPUT_DIR=/data/output` on staging (set 2026-05-30) so the per-match + per-outright JSON the publisher writes survives redeploys. **All three readers/writer honour the env var**: the publisher (`desk/desk/publish/writer.py` → resolves through `desk/desk/config.py`), the API (`desk_api.py:63`), and the static-site renderer (`site/generate.py:40`). Without the env var they fall back to repo-relative `desk/data/output/`. The volume is mounted at `/data` (see `RAILWAY_VOLUME_MOUNT_PATH`); same volume already holds `signals.db`, `api_football.db`, `forward_validation.db`, and `ops/`. Apply the same env var to prod when promoting.
- **Postgres is activity-signals only; everything else is sqlite.** New domains should default to sqlite unless the access pattern requires concurrent writers (which is what pushed activity onto Postgres). One Railway Postgres add-on per environment (staging / prod). The Prophet app reads `DATABASE_URL` (Railway private network, free egress) referenced *from* the Postgres service; `DATABASE_PUBLIC_URL` is operator-only — never let it leak into the app or a committed file (it bills egress per byte).
- **Migrations are plain SQL applied by hand** via Railway → Postgres → Data → Query. Files in `migrations/YYYYMMDD_short_name.sql`, each wrapped in `BEGIN; … COMMIT;` with `IF NOT EXISTS` on every statement so re-applies are safe. No migration framework — the directory is the audit trail. Add Alembic only when a second Postgres-backed domain shows up.
- **`desk_refresh_loop.py` runs on a schedule of UTC clock hours controlled by the Ops dashboard.** Each entry in the schedule fires one tick per day at the top of that hour. Operators add/remove hours and toggle the master enable flag at `/desk/ops/admin` → **Desk admin**; changes land on the loop's next scheduling decision (no restart). State persists at `{ops_root}/control.json` (`{ enabled, hours: [int 0..23] }`) so prod and staging each carry their own schedule. Default on a fresh install: `hours: [6]` (one run daily at 06:00 UTC). `DESK_AUTORUN=0` is the deploy-time kill switch (use it only when the dashboard isn't reachable). Each tick runs `desk run --once` (timeout 600s) → `desk outrights` → `site/generate.py` → `desk fetch-signals` (if `DESK_SIGNALS_FETCH=1`) → `desk extract-signals` (if `DESK_SIGNALS_EXTRACT=1` + `ANTHROPIC_API_KEY` set) → `desk fetch-injuries` (if `DESK_INJURY_FETCH=1`) → `desk fetch-cards` (if `DESK_CARD_FETCH=1`; runs after injuries so the at-risk reconcile sees the latest suspension set) → `desk fetch-lineups --window-hours 24` (if `DESK_LINEUP_FETCH=1`). **Matches runs first** so the dashboard-critical artifacts always land before signals work can eat the time budget — signals enrich the *next* tick's matches (one-tick lag is fine; missing matches is not). Set `DESK_SIGNALS_EXTRACT_LIMIT=25` on prod to keep Haiku extraction inside its 600s timeout and cost predictable. A boot tick fires automatically `DESK_INITIAL_DELAY_SEC` (default 60s) after server start whenever the dashboard schedule is enabled with at least one hour — `DESK_FORCE_TICK_ON_BOOT=1` overrides that gate so a redeploy can guarantee a fresh tick even when the schedule is paused or empty.
- **`desk_lineups_refresh_loop.py` runs separately at a 15-minute cadence (`DESK_LINEUP_LOOP_TICK_SEC`), scoped to the next 2 hours of kickoffs (`DESK_LINEUP_LOOP_WINDOW_HOURS`).** Off by default; flip `DESK_LINEUP_LOOP_ENABLED=1` to start it. Each tick calls `desk fetch-lineups --window-hours 2`; on any successful fetch (api-football flagged at least one fixture's confirmed XI) the loop also runs `desk run --once` + `site/generate.py` so the new starters reach the published JSON + static HTML before kickoff (skip the publish step with `DESK_LINEUP_LOOP_PUBLISH=0`). Sits alongside the daily refresh loop in `main.py`; honours `DESK_AUTORUN=0` as the kill switch.
- **Ops dashboard has two views** at `/desk/ops`: a left-sidebar nav with **The Desk** (read-only run history with Date / Start / End / Trigger / Status / Pub. / Picks / Δ / Cost columns + **External providers** panel showing api-football + live Elo + openweathermap health + Sources read + News signals + per-run cost) and **Desk admin** (master enable toggle + a list of scheduled UTC hours with Add/Remove). The **External providers** panel calls `GET /api/desk/ops/data-sources` independently of the run-history fetch so a fresh-deploy with zero runs still surfaces provider health; each provider card shows a status pill (`live` / `fetch off` / `no cache yet` / `no key` / `probe-only`) + count of cached rows + recent fetch timestamps. **OpenWeatherMap intentionally surfaces as `probe-only`** — the key is verified but B.2 weather fetch/cache/hook isn't wired. Both views share the same HTTP Basic auth gate (`DESK_OPS_USER` / `DESK_OPS_PASS`); `server.py` wraps the SPA catch-all under `/desk/ops/*` with that gate so `/desk/ops/admin` can never be reached unauthed. The admin page writes `control.json` directly — the loop polls it on every scheduling decision.
- **Per-tick Anthropic cost is captured for the dashboard.** Each Haiku call (`desk/desk/signals/extract.py`, `desk/desk/explainer/haiku.py`) appends one row to `{ops_root}/costs.jsonl` tagged with the loop's `DESK_TICK_ID`. After all subprocesses for a tick complete, the refresh loop sums those rows and appends a `tick-totals.jsonl` entry keyed by the matches RunReport's `run_id`. The ops API joins this onto the run history table so `/desk/ops` shows a per-run **Cost** column. Pricing constants (Haiku 4.5 input $1/Mtok, output $5/Mtok, cache read $0.10/Mtok, cache write $1.25/Mtok) live in `desk/desk/ops/cost.py:_PRICING`; bump them when Anthropic updates the public price list.
- **`KALSHI_PRIVATE_KEY_PATH` must be a filesystem path, never inline PEM.** Setting it to PEM contents causes a `FileNotFoundError` whose message includes the whole key — and the scheduler used to log that verbatim every 30s. The loader in `core/auth.py` now raises a clean error when it sees `-----BEGIN` in the path, and `scheduler.py` redacts any error message containing a PEM block. On Railway, mount the key as a file (or write it from a separate env var at boot) and point this env var at the file path.
- **DW (Deutsche Welle) feed is RSS 1.0 / RDF**, which the stdlib parser in `desk/signals/parse.py` doesn't handle. One source out of 13 currently dropping `parse_error`. Not blocking — fix when convenient.
- **8 trust-only sources** (Reuters, AP, AFP, FIFA, UEFA, The Athletic, Eurosport, Goal.com) carry `feed_type=none`. They're in the registry for trust weighting but can't be fetched today — each needs a paid API integration or custom adapter to activate.
- **VS Code git/PR extension auto-stages files.** If `git status` shows surprise staged content, run `git reset` (touches no files) before committing.
- **api-football team-search gotcha — `bih` + `cod` don't resolve out-of-the-box.** Their canonical national-side names on api-football are `"Bosnia & Herzegovina"` (id 1113) and `"Congo DR"` (id 1508). The `/teams?search=` endpoint rejects `&` (`"Search field may only contain alpha-numeric characters and spaces"`) AND won't accept `"DR Congo"` (prefix order matters). Working searches: `"Bosnia"` and `"Congo DR"`. Without these two, WC26 fixture-coverage drops to 91.7% (below the 98% pre-publish WARN threshold in `desk/desk/data/api_football/coverage.py`). Shipped in commit `ff79261` (2026-05-30) — registry values updated to the working search strings; verify against the live key with `desk fetch-rank-form --iso3 bih --iso3 cod` after any future registry edits.
- **Watch the Anthropic credit balance.** Haiku blurb-writer + news-signals extractor both fail with HTTP 400 *"Your credit balance is too low to access the Anthropic API"* once the workspace runs out. Pipeline keeps shipping (fallback to templated stub) but every match-page blurb degrades silently. Staging hit this on 2026-05-30 mid-session. Enable auto-recharge on the Anthropic console or watch the per-tick cost in the Ops dashboard.
- When you say "save session", "snapshot", "load context", or "sync memory", follow `~/Google Drive/My Drive/Claude/memory/session-snapshot-SKILL.md`.
