# Prophet · Ledger · The Desk · Odds Primer site

This repo carries four discrete surfaces. They share a Python + React
stack but are independent — each can run, deploy, and ship without the
others.

| Product | What it is | Lives at | Status |
|---|---|---|---|
| **Prophet** | Paper-trading bot for prediction markets, plus the platform's market data engine and React dashboard | `prophet/` (or repo root for legacy code), `frontend/` | shipping; deployed to Railway |
| **Ledger** | Connected portfolio tracker for Polymarket (Kalshi in Phase 1). Paste-a-wallet viewer at `/ledger`. | `ledger/`, `frontend/src/ledger/` | Phase 0 shipped; live on Railway |
| **The Desk** | Verdict engine that evaluates every priced football match + the WC 2026 outright winner market | `desk/` | PRs 1–4 + backtest + 4.5 sanity + explainer stub + **optimization-spec Phase A** + **outright engine (parallel pipeline, live on Polymarket)** + **WC26-only ingest filter** + **per-team outright ladder UI** + **team-id collision fix + seed-Elo audit** + **news-signals PRs A–F all live in production** (12 trusted-core RSS → Haiku → `copy.editorial_citations` + bounded Elo nudges) + **PR 5 Haiku blurb-writer** (gated on `DESK_BLURB_HAIKU=1`, falls back to stub on any failure) all landed; PR 6 scheduler still outstanding |
| **Odds Primer site (React)** | Editorial front-of-house: home (`/`), about (`/about`), learn (`/learn` + 3 primers). Reuses the design system; hardcoded sample data — live wiring is a later workstream. Legacy Prophet trading dashboard moved to `/dashboard` (unlinked). | `frontend/src/op/` | shipped to staging 2026-05-13 (PR #27). **Route conflict at `/` with `site/generate.py`'s static site (`/`, `/matches`, `/outrights`) needs reconciling before prod promote.** |

Build specs live alongside the code:

- `THE_DESK_SPEC.md` — six-PR build plan for The Desk
- `THE_DESK_PR_BACKTEST_BRIEF.md` — backtest harness brief (shipped)
- `THE_DESK_PR_4_5_BRIEF.md` — sanity layer brief (shipped)
- `THE_DESK_TRUSTABILITY_BRIEF.md` — first trustability roadmap (superseded by the optimization spec)
- `THE_DESK_OPTIMIZATION_SPEC.md` — v1.1 + v1.2 optimization spec; **Phase A landed**, B–F outstanding
- `THE_DESK_OUTRIGHTS_SPEC.md` — outright winner build spec; v0.2 supersedes earlier drafts. Note: v0.2 wants outrights folded through the position-list waist, but **the parallel-pipeline implementation in `desk/outrights/` shipped first** — it predates the waist refactor and runs live on Polymarket today.
- `THE_DESK_DATA_LAYER_SPEC.md` — data layer spec; Phase 1b (live Elo from eloratings.net / clubelo.com) is the credibility-load-bearing piece the match-Pick page needs before its Picks become real signals
- `THE_DESK_NEWS_SIGNALS_SPEC.md` — news & editorial signals spec (v0.1 draft). PRs A–F **all shipped** as of 2026-05-21 — sport-agnostic source registry + resolver, RSS fetcher + cache, Haiku extractor, editorial track → `copy.editorial_citations`, GDELT aggregator path, hard-track Elo adjustments. Live on Railway behind `DESK_SIGNALS_FETCH=1` + `DESK_SIGNALS_EXTRACT=1` (needs `ANTHROPIC_API_KEY`).
- `desk/VOICE.md` — **canonical editorial voice for all Desk-generated copy** (V1: dry wit with a spine; 120–180-word blurbs, every blurb has a point + is sourced, never invent a citation). PR 5's Haiku blurb-writer prompt MUST point here. Hard "never" rules are enforced in `desk/desk/explainer/voice.py`; brand-level prose lives in `Odds Primer Design System/README.md`.
- `STATUS.md` — overnight-run briefing (refreshed when an autonomous run lands work; check it in the morning)
- `ledger-phase-0-brief.md` — Phase 0 brief for Ledger
- `Odds Primer Design System/` — voice, palette, type, components. Canonical brand assets live at the **top level**: `assets/wordmark.svg`, `assets/wordmark-tagline.svg`, `assets/glyph-bars.svg`, with the lockup spec in `preview/wordmark.html`. Wordmark is **Inter Tight 700** (not Source Serif 4); bars glyph uses `viewBox 0 0 38 34`. The earlier `branding/locked/` folder is **archived** — don't read or import from it.

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
- ✅ News-signals PRs A–F (per `THE_DESK_NEWS_SIGNALS_SPEC.md`) — 21-source global registry (13 RSS active + 8 trust-only / `feed_type=none` reserved for licensed APIs), `desk fetch-signals` populates `desk/data/signals.db`, `desk extract-signals` runs Haiku with prompt caching + tool-use schema (cost ~$0.003/article, content-hash dedupe makes steady-state nearly free), `copy.editorial_citations` filled by `build_citations` with team binding to the participating sides + ≥2-org consensus detector for plural attribution, hard-track injury/suspension Signals from `can_feed_model` sources nudge each team's Elo within the 5-day late-binding window (bounded -8 injury / -6 suspension, capped -30 total per team). Wired into `desk_refresh_loop.py` so the hourly tick fetches + extracts + republishes JSON.
- ✅ PR 5 — explainer Haiku replacement. `desk/desk/explainer/haiku.py` is the blurb-writer (`claude-haiku-4-5`, forced tool-use, system prompt loads `desk/VOICE.md` verbatim + cache_control ephemeral so a single run amortises across 70+ matches). `desk/desk/explainer/__init__.py` dispatches: when `DESK_BLURB_HAIKU=1` + `ANTHROPIC_API_KEY` set, Haiku writes title/summary/blurb; stub still produces `drivers` + the merged Copy is voice-checked one more time. Falls back to the templated stub on any failure (no key, network/timeout, voice-rule violation, blurb outside [80, 220] words, attribution to an outlet not in `editorial_citations`).
- ⬜ PR 6 — scheduler + CLI + serve
- ⬜ Phase B (form / FIFA-rank residual / weather / injuries) — biggest Brier lever
- ⬜ Phase C–F per optimization spec
- ⬜ Data Layer Phase 1b — live Elo ingest. **Match Picks are not real betting signals until this lands** (the seed audit gets them defensible but not validated).

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
│   │   ├── haiku.py                  # PR 5 — Haiku blurb-writer (forced tool-use; gated on DESK_BLURB_HAIKU=1)
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
│   │       └── hard_signals.py       # Signal → bounded Elo adjustment (PR F)
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
│   ├── cli.py                        # `desk run / sports / match / outrights / backtest`
│   └── contract.schema.json          # generated; in-sync test enforces
├── tests/                            # 172 green
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
| `DESK_OPS_DIR` | unset → `{DESK_OUTPUT_DIR}/ops` | Where the ops dashboard's `RunReport` history is persisted. On Railway, point this at a mounted volume (e.g. `/data/ops`) so run history survives deploys — without it, every redeploy wipes the dashboard back to "no runs recorded yet". Honoured by both writer (`desk/desk/runner.py`) and reader (`desk_ops_api.py`). |
| `DESK_OPS_EDGE_DELTA_PP` | `1.0` | Minimum |edge_pp| delta between consecutive runs that fires an `edge` change in the diff engine. |
| `ANTHROPIC_API_KEY` | unset | Required for `desk extract-signals` (Haiku). Without it, extraction exits non-zero — the rest of the pipeline still runs and the cache still fills via fetch, just no Signals are produced. |
| `DESK_SIGNALS_FETCH` | `0` | Set to `1` to enable the hourly RSS fetch step in `desk_refresh_loop.py`. Off by default so a fresh deploy doesn't hit external services until the operator opts in. |
| `DESK_SIGNALS_EXTRACT` | `0` | Set to `1` to enable the hourly Haiku extraction step. Needs `ANTHROPIC_API_KEY` to actually run; logs a warning + skips if the key isn't present. |
| `DESK_SIGNALS_EXTRACT_LIMIT` | unset | Optional per-source-per-tick cap on extraction. E.g. `25` keeps steady-state Anthropic cost predictable while the source set is being tuned. |
| `DESK_SIGNALS_DB_PATH` | unset → `desk/data/signals.db` | Override the signals cache path. **Set this on Railway** to a mounted volume (e.g. `/data/signals.db`) so the news-signals cache survives deploys — without it, every redeploy wipes `signals.db` and the first post-deploy tick publishes matches with no citations. Honoured by both writers (`desk fetch-signals`, `desk extract-signals`) and reader (`SignalsRuntime.for_sport` in `desk/desk/runner.py`). |
| `DESK_HARD_SIGNAL_INJURY_ELO` | `8.0` | Magnitude of the Elo penalty applied for a single confirmed injury signal (from a `can_feed_model` source, inside the late-binding window). |
| `DESK_HARD_SIGNAL_SUSPENSION_ELO` | `6.0` | Same, for confirmed suspensions / bans. |
| `DESK_HARD_SIGNAL_MAX_ELO` | `30.0` | Hard per-team cap on total hard-signal Elo penalty. Multiple injuries cumulate but never below this floor. |
| `DESK_HARD_SIGNAL_WINDOW_DAYS` | `5` | Late-binding window. A hard signal only adjusts Elo when the fixture's kickoff is within this many days. Outside the window, the path is a no-op. |
| `DESK_BLURB_HAIKU` | `0` | Set to `1` to route the explainer's title/summary/blurb through `desk/desk/explainer/haiku.py` (Haiku 4.5, system prompt sourced from `desk/VOICE.md`). Needs `ANTHROPIC_API_KEY`. Off by default — without it, the templated stub still ships. |
| `DESK_BLURB_HAIKU_MODEL` | `claude-haiku-4-5` | Override the Haiku model id. Useful for pinning a specific haiku build. |

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

## Tech stack

**Backend** Python 3.11+, httpx, websockets, cryptography, pandas, FastAPI, uvicorn, Pydantic v2, aiosqlite, APScheduler (PR 6+), Anthropic SDK (Haiku for news-signals extraction + future PR 5 blurb generation — listed in root `requirements.txt` so the Railway image installs it; `desk/pyproject.toml` is **not** pip-installed in production, the package runs as a subprocess via PYTHONPATH).

**Frontend** React 19, Vite, Recharts, Lucide React. The editorial site (`frontend/src/op/`), Ledger (`frontend/src/ledger/`), and Desk page (`frontend/src/desk/`) all use the Odds Primer Design System (`Odds Primer Design System/`) — Source Serif 4 (body), Inter Tight (wordmark + chrome), JetBrains Mono (numerics). All three share the locked tokens at `frontend/src/ledger/op-tokens.css`. The legacy Prophet trading dashboard at `/dashboard` still uses its older dark-theme tokens.

---

## Conventions

- **Work on `staging` by default.** Commit, push, check the staging URL. Feature branches are optional and only worth the overhead when two unrelated things are in flight at once.
- **`init/project-setup` is production.** Only receives merges from `staging` once changes have been eyeballed. Never push half-finished work straight to it.
- **Never commit `data/*.db`.** Already in `.gitignore` (covers root `data/*.db` AND `desk/data/*.db`). The news-signals cache lives at `desk/data/signals.db` locally; on Railway the path is overridden via `DESK_SIGNALS_DB_PATH` to a file on the mounted `/data` volume so the cache survives container restarts and deploys.
- **`desk_refresh_loop.py` runs hourly on Railway.** Each tick: `desk run --once` (timeout 600s) → `desk outrights` → `site/generate.py` → `desk fetch-signals` (if `DESK_SIGNALS_FETCH=1`) → `desk extract-signals` (if `DESK_SIGNALS_EXTRACT=1` + `ANTHROPIC_API_KEY` set). Disabled with `DESK_AUTORUN=0`. **Matches runs first** so the dashboard-critical artifacts always land before signals work can eat the time budget — signals enrich the *next* tick's matches (one-tick lag is fine; missing matches is not). Set `DESK_SIGNALS_EXTRACT_LIMIT=25` on prod to keep Haiku extraction inside its 600s timeout and cost predictable.
- **`KALSHI_PRIVATE_KEY_PATH` must be a filesystem path, never inline PEM.** Setting it to PEM contents causes a `FileNotFoundError` whose message includes the whole key — and the scheduler used to log that verbatim every 30s. The loader in `core/auth.py` now raises a clean error when it sees `-----BEGIN` in the path, and `scheduler.py` redacts any error message containing a PEM block. On Railway, mount the key as a file (or write it from a separate env var at boot) and point this env var at the file path.
- **DW (Deutsche Welle) feed is RSS 1.0 / RDF**, which the stdlib parser in `desk/signals/parse.py` doesn't handle. One source out of 13 currently dropping `parse_error`. Not blocking — fix when convenient.
- **8 trust-only sources** (Reuters, AP, AFP, FIFA, UEFA, The Athletic, Eurosport, Goal.com) carry `feed_type=none`. They're in the registry for trust weighting but can't be fetched today — each needs a paid API integration or custom adapter to activate.
- **VS Code git/PR extension auto-stages files.** If `git status` shows surprise staged content, run `git reset` (touches no files) before committing.
- When you say "save session", "snapshot", "load context", or "sync memory", follow `~/Google Drive/My Drive/Claude/memory/session-snapshot-SKILL.md`.
