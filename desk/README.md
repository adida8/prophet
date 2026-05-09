# The Desk

Engine that evaluates **every priced football match** and publishes a verdict
JSON consumed by Faktor's site. Football is the first sport; the architecture
admits more sports as separate packages. WC 2026 is the launch wedge.

The engine has six steps — Ingest → Features → Model → Verdict → Explainer →
Publish — each independently replaceable.

## Status

PR ladder per `THE_DESK_SPEC.md` §4 + `THE_DESK_PR_BACKTEST_BRIEF.md`:

- [x] PR 1 — skeleton + output contract
- [x] PR 2 — fixture ingest + match identity
- [x] PR 3 — football model v1 (Elo + host/home + altitude)
- [x] PR 4 — verdict step + thresholds (end-to-end pipeline)
- [x] **Backtest harness** — `desk backtest --tournament wc-2022`
- [x] **PR 4.5** — sanity layer (liquidity + stub-Elo gate + Avoid edge_pp fix)
- [x] **Phase A.3** — confidence band (Elo jackknife ±50, lower-bound Pick gate)
- [x] **Explainer stub** — templated copy.title/summary/blurb with voice-rule enforcement
- [ ] PR 5 — explainer Haiku replacement (3 prompts; needs ANTHROPIC_API_KEY)
- [ ] PR 6 — scheduler + CLI + serve

Trustability progress (Phase A of `THE_DESK_TRUSTABILITY_BRIEF.md`):

| Run | Original | After PR 4.5 | After Phase A.3 |
|---|---|---|---|
| WC 2022 backtest | 95% Pick | 95% (gates didn't fire — real Elo, well-priced) | **16%** |
| Live (78 priced fixtures) | 62% Pick | 23% | **6%** |

Both runs now sit inside the 5–20% target. The backtest dashboard's
Selection card flips from red to green; calibration unchanged at
parity with the closing market.

## Run

```bash
cd desk
python -m pip install -e ".[dev]"
pytest
```

## Layout

```
desk/
├── desk/
│   ├── config.py                 # env + thresholds + paths
│   ├── sport.py                  # Sport ABC + FixtureRef
│   ├── publish/                  # Pydantic contract + static-file publisher + ETag
│   ├── ingest/                   # Source ABC + Polymarket gamma client
│   ├── verdict/                  # MarketSnapshot + decide() + thresholds
│   ├── sports/football/          # FootballSport + features + model + metadata
│   ├── backtest/                 # historical loaders + replay + writers + harness
│   ├── runner.py                 # run_once() — full live pipeline
│   ├── cli.py                    # `desk run / sports / match / backtest / replay`
│   └── contract.schema.json      # generated; sync-check test enforces
├── data/
│   ├── output/football/          # live published JSON
│   └── backtest/                 # frozen Elo snapshots + manual CSVs
└── tests/
```

## Backtest

```
desk backtest --tournament wc-2022
```

Replays the engine across a frozen historical sample and writes:

- `desk_backtest.xlsx` — Snapshots + Match Universe rebuilt from real
  inputs. Brier and verdict-resolution formulas auto-recompute when
  Excel opens the file.
- `desk_backtest_dashboard.html` — KPI strip, reliability bins, match
  table regenerated. Disclaimer shows the run date and competition list.

Single-tournament run finishes in well under a second on
this laptop (256 snapshots × full pipeline). Headline number printed by
the CLI is **mean Brier vs closing-market Brier** across KO snapshots —
the only credibility metric that matters for the prelaunch story.

The historical Elo source is a frozen pre-tournament snapshot under
`data/backtest/elo/intl/{yyyymmdd}.json`; markets come from a curated
CSV under `data/backtest/manual/{competition}_{season}.csv`. Both are
checked into git so the backtest is reproducible without network.

Critical invariant: `desk/backtest/replay.py` never imports from
`desk/sports/football/ingest/` — that's how we guarantee no run leaks
today's data into a 2022 fixture.

## Output contract — quick view

Faktor consumes this. Schema lives in `desk/contract.schema.json`. Sample:

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
    "title": "France v Mexico · class shows",
    "summary": "Two short sentences in Odds Primer voice.",
    "blurb": "Sixty to ninety words explaining the verdict.",
    "citations": ["https://lequipe.fr/...", "https://globoesporte.com/..."]
  },
  "updated_at": "2026-06-12T17:00:00Z"
}
```

## Match-ID convention

`{sport_short}-{competition}-{team_a}-{team_b}-{yyyymmdd}`

- `sport_short` — `fb` for football. Each `Sport` exposes its short code; `sport` field still holds the long name (`"football"`).
- `competition` — league or tournament code. `wc26`, `epl`, `laliga`, `ucl`, `mls`.
- Team IDs:
  - National sides — lowercase ISO3 (`fra`, `mex`, `usa`).
  - Clubs — `{league}-{short}` (`epl-mun`, `laliga-rma`). The same physical club always carries its primary-league slug across competitions, so a UCL fixture between Bayern and Real Madrid is still `fb-ucl-bundesliga-bay-laliga-rma-…` — TBD if we want a flatter form (PR 2 work).

Date is the kickoff date in UTC.

## Thresholds (locked, override via `.env`)

| State | Rule |
|---|---|
| Pick | `model_p − best_market_p ≥ 3.0pp` |
| Pass | every side: `\|model_p − best_market_p\| < 1.0pp` |
| Avoid | every side: `model_p − best_market_p ≤ −2.0pp` |

Thresholds enforced in PR 4. PR 1 only carries the constants.
