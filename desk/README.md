# The Desk

Engine that evaluates **every priced football match** and publishes a verdict
JSON consumed by Faktor's site. Football is the first sport; the architecture
admits more sports as separate packages. WC 2026 is the launch wedge.

The engine has six steps — Ingest → Features → Model → Verdict → Explainer →
Publish — each independently replaceable.

## Status

**v0.1 · PR 1** — output contract + static-file publisher.

PR ladder per `THE_DESK_SPEC.md` §4:

- [x] PR 1 — skeleton + output contract (this PR)
- [ ] PR 2 — fixture ingest + match identity
- [ ] PR 3 — football model v1 (Elo + host/home + altitude)
- [ ] PR 4 — verdict step + thresholds
- [ ] PR 5 — explainer (3 Haiku prompts)
- [ ] PR 6 — scheduler + CLI + serve

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
│   ├── config.py                 # env + thresholds
│   ├── sport.py                  # Sport ABC (PR 2+)
│   ├── publish/
│   │   ├── contract.py           # Pydantic v2 — single source of truth
│   │   ├── writer.py             # static-file publisher + sport-partitioned index.json
│   │   └── etag.py               # content-hash → ETag
│   ├── contract.schema.json      # generated; commit this
│   ├── ingest/                   # PR 2+
│   ├── features/                 # PR 2+
│   ├── verdict/                  # PR 4+
│   ├── explainer/                # PR 5+
│   ├── sports/football/          # PR 2+
│   └── scheduler.py              # PR 6+
├── tests/
└── data/output/football/         # published JSON lives here
```

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
