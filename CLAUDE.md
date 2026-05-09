# Prophet · Ledger · The Desk

This repo carries three discrete products. They share a Python + React
stack but are independent — each can run, deploy, and ship without the
others.

| Product | What it is | Lives at | Status |
|---|---|---|---|
| **Prophet** | Paper-trading bot for prediction markets, plus the platform's market data engine and React dashboard | `prophet/` (or repo root for legacy code), `frontend/` | shipping; deployed to Railway |
| **Ledger** | Connected portfolio tracker for Polymarket (Kalshi in Phase 1). Paste-a-wallet viewer at `/ledger`. | `ledger/`, `frontend/src/ledger/` | Phase 0 shipped; live on Railway |
| **The Desk** | Verdict engine that evaluates every priced football match (WC 2026 launch wedge → club football right after) | `desk/` | PRs 1–4 + backtest + 4.5 sanity + explainer stub + **optimization-spec Phase A** all landed; Phase B (form / FIFA / weather / injuries) + PR 5 Haiku + PR 6 scheduler outstanding |

Build specs live alongside the code:

- `THE_DESK_SPEC.md` — six-PR build plan for The Desk
- `THE_DESK_PR_BACKTEST_BRIEF.md` — backtest harness brief (shipped)
- `THE_DESK_PR_4_5_BRIEF.md` — sanity layer brief (shipped)
- `THE_DESK_TRUSTABILITY_BRIEF.md` — first trustability roadmap (superseded by the optimization spec)
- `THE_DESK_OPTIMIZATION_SPEC.md` — v1.1 + v1.2 optimization spec; **Phase A landed**, B–F outstanding
- `STATUS.md` — overnight-run briefing (refreshed when an autonomous run lands work; check it in the morning)
- `ledger-phase-0-brief.md` — Phase 0 brief for Ledger
- `Odds Primer Design System/` — voice, palette, type, components
- `branding/bars-locked-v2.html` — locked logo (Source Serif 4 wordmark + bars glyph)

## Deploy

Default branch: **`init/project-setup`** — Railway watches it and deploys on every push. Live URL: `https://web-production-9e0f9.up.railway.app/`.

PRs land into `init/project-setup`. There's no separate staging environment yet. Build pipeline: `railpack.json` runs `npm install` + `vite build` for the frontend, then `python main.py --dashboard --port $PORT` as the start command.

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

Engine that evaluates **every priced football match** (not just WC 2026). For each match it produces a `verdict.json` (Pick / Pass / Avoid) + three rendered editorial strings (title / summary / blurb). Faktor's site is the only consumer; it reads only the CDN-fronted JSON contract.

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
- ⬜ PR 5 — explainer Haiku replacement (needs `ANTHROPIC_API_KEY`)
- ⬜ PR 6 — scheduler + CLI + serve
- ⬜ Phase B (form / FIFA-rank residual / weather / injuries) — biggest Brier lever
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
`init/project-setup`. Railway redeploys on every push.

### Quick start

```bash
cd desk
python -m pip install -e ".[dev]"
pytest                          # 146 tests, all green

python -m desk sports                       # list registered sports
python -m desk run --once                   # live pipeline → data/output/football/*.json
python -m desk match fb-wc26-fra-mex-20260612
python -m desk backtest --tournament wc-2022 # historical replay → workbook + dashboard
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
│   │   └── stub.py                   # templated copy until PR 5 wires Haiku
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
│   │       └── metadata/             # FIFA + club adapters
│   ├── backtest/                     # READ-ONLY side workflow
│   │   ├── tournaments.py            # WC 2022 + future tournaments
│   │   ├── historical/               # Elo / markets / results loaders
│   │   ├── replay.py                 # SnapshotRow + replay_match (no live ingest!)
│   │   ├── writers/                  # xlsx + dashboard regenerators
│   │   └── runner.py                 # run_backtest() orchestrator
│   ├── runner.py                     # run_once() — full live pipeline
│   ├── cli.py                        # `desk run / sports / match / backtest / replay`
│   └── contract.schema.json          # generated; in-sync test enforces
├── tests/                            # 101 green
└── data/
    ├── output/football/              # live per-match JSON + index.json
    └── backtest/                     # frozen Elo snapshots + manual CSVs
```

### Sport boundary (non-negotiable)

Anything sport-specific lives under `desk/sports/{sport}/`. Anything sport-agnostic (`verdict/`, `publish/`, `runner.py`, `scheduler.py`, `cli.py`) **never** imports from a sport package — only through the `Sport` Protocol. Adding tennis later = a new package, not a refactor.

### Match-id format

`{sport_short}-{competition}-{team_a}-{team_b}-{yyyymmdd}` — e.g.

- `fb-wc26-fra-mex-20260612` (national: ISO3 lowercase)
- `fb-epl-mun-liv-20260815` (clubs: `{league}-{short}`)
- `fb-ucl-bay-psg-20260506`

### Verdict thresholds (locked, env-overridable)

| State | Rule |
|---|---|
| Pick | `model_p − best_market_p ≥ 3.0pp` for some side |
| Pass | every side: `\|model_p − best_market_p\| < 1.0pp` |
| Avoid | every side: `model_p − best_market_p ≤ −2.0pp` |

Override via `DESK_PICK_PP` / `DESK_PASS_PP` / `DESK_AVOID_PP` in `.env`.

### Output contract (what Faktor consumes)

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
  "copy": { "title": "...", "summary": "...", "blurb": "...", "citations": [...] },
  "updated_at": "2026-06-12T17:00:00Z"
}
```

Internals (`p_a/p_draw/p_b`, drivers, raw market prices) **stay inside The Desk**. Adding a contract field requires an ADR.

---

## Tech stack

**Backend** Python 3.11+, httpx, websockets, cryptography, pandas, FastAPI, uvicorn, Pydantic v2, aiosqlite, APScheduler (PR 6+), Anthropic SDK (PR 5+).

**Frontend** React 19, Vite, Recharts, Lucide React. The Ledger uses the Odds Primer Design System (`Odds Primer Design System/`) — Source Serif 4, Inter Tight, JetBrains Mono. The Prophet dashboard still uses its older dark-theme tokens.

---

## Conventions

- **Branch off `init/project-setup`** for every PR. Default branch is the deploy target.
- **`init` branch is production.** No separate staging yet. Don't push directly; open a PR.
- **Never commit `data/*.db`.** Already in `.gitignore`.
- **VS Code git/PR extension auto-stages files.** If `git status` shows surprise staged content, run `git reset` (touches no files) before committing.
- When you say "save session", "snapshot", "load context", or "sync memory", follow `~/Google Drive/My Drive/Claude/memory/session-snapshot-SKILL.md`.
