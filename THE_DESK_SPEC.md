# The Desk — Build Spec for Claude Code

**Status:** v0.2 build spec, 2026-05-09. Derived from `RECOMMENDATION_ENGINE_DESIGN.md` v0.2.
**Target consumer:** Claude Code (agentic CLI).
**Owner:** Adi.
**Launch wedge:** WC 2026 (~2026-05-09 beta → 2026-06-13 kickoff). Engine is **not** WC-specific.

---

## 1. Mission

Build **The Desk** — the core engine that evaluates **every priced football match**, not just the World Cup. WC 2026 is the launch wedge; the architecture must comfortably handle club football (EPL, La Liga, UCL, MLS, etc.) the day after the tournament ends, with no rewrite. Football is the first sport. The engine must be designed so other sports (basketball, tennis, NFL) can plug in as separate modules in a later version without disturbing the football pipeline.

For each match, The Desk produces a `verdict.json` (Pick / Pass / Avoid) plus three rendered editorial strings. Faktor's site is the only consumer and reads only a CDN-fronted JSON contract. Internals are private.

The engine's six steps (Ingest → Features → Model → Verdict → Explainer → Publish) must each be replaceable independently. v1 is deliberately small: Elo prior, host/home adjustment, altitude bonus, Haiku explainer. Engineering effort goes into data plumbing, not the maths.

## 2. Out of scope (do not build)

- Real money flows, stake sizing, Kelly, "place bet" CTAs.
- A devig / market-microstructure model. The model **never reads market prices**.
- A leaderboard, hit-rate counter, or any tipster framing.
- Auth, accounts, a database. v1 is files-on-disk + JSON over HTTP.
- Any direct Faktor coupling. Faktor consumes the contract, period.
- Non-football sports in v1 — but the architecture must cleanly admit them in a later version (see §3 sport boundary).
- Paper-trading bot framing or any reuse of `prophet/` Kalshi-trading code beyond the API client patterns.

## 3. Repo plan — sport-aware from day one

Build a new module rooted at `desk/` inside the existing project. Do not touch `prophet/` (paper-trading bot — separate concern).

The cardinal rule: **anything sport-specific lives under `desk/sports/{sport}/`**, anything sport-agnostic lives at the top of `desk/`. v1 only ships `sports/football/`, but the boundary is enforced by the package layout and a `Sport` ABC. Adding `sports/basketball/` later means writing a new package — not modifying football code.

```
/Users/adi/Documents/Claude/Projects/prophet/
└── desk/
    ├── README.md                        # one-page how-to-run
    ├── pyproject.toml                   # deps, ruff, pytest config
    ├── .env.example
    ├── desk/
    │   ├── __init__.py
    │   ├── config.py                    # env + constants (thresholds, cadences)
    │   ├── sport.py                     # Sport ABC — registry, fixture iter, model factory
    │   │
    │   ├── ingest/                      # SPORT-AGNOSTIC ingest infrastructure
    │   │   ├── base.py                  # Source ABC, retry, cache, registry
    │   │   ├── kalshi.py                # market list + prices (filtered per-sport at the registry)
    │   │   ├── polymarket.py            # market list + prices
    │   │   ├── weather.py               # OpenWeatherMap, T−5 binding
    │   │   └── news.py                  # tiered RSS/scrape → Haiku fact extractor (sport-tagged)
    │   │
    │   ├── features/
    │   │   ├── store.py                 # parquet/JSON feature snapshots, versioned, sport-namespaced
    │   │   └── builder.py               # delegates row assembly to the active Sport
    │   │
    │   ├── verdict/                     # SPORT-AGNOSTIC — operates on probabilities + market prices
    │   │   ├── thresholds.py            # Pick / Pass / Avoid logic
    │   │   └── compare.py               # model_p vs market_p across venues
    │   │
    │   ├── explainer/                   # SPORT-AGNOSTIC scaffold; per-sport voice templates injected
    │   │   ├── prompts.py               # 3 Haiku prompts (title, summary, blurb)
    │   │   ├── client.py                # Anthropic client wrapper
    │   │   └── cache.py                 # only re-call on state transition
    │   │
    │   ├── publish/
    │   │   ├── contract.py              # output JSON schema (Pydantic) — sport tag is a field
    │   │   ├── writer.py                # write per-match + index.json (sport-partitioned)
    │   │   └── etag.py                  # content hash for ETag/If-None-Match
    │   │
    │   ├── sports/
    │   │   ├── __init__.py              # SPORT_REGISTRY = {"football": FootballSport(), ...}
    │   │   └── football/
    │   │       ├── __init__.py
    │   │       ├── sport.py             # FootballSport(Sport) — wires the rest
    │   │       ├── fixtures.py          # fixture-list adapter (any priced football match, not WC-only)
    │   │       ├── teams.py             # team-id system (clubs + national sides) — see §10 q
    │   │       ├── metadata/
    │   │       │   ├── fifa.py          # international metadata (venue, group, kickoff)
    │   │       │   └── club.py          # club-football metadata (league, matchday, ground)
    │   │       ├── ingest/
    │   │       │   ├── elo_intl.py      # Wikipedia data module — international Elo
    │   │       │   └── elo_club.py      # ClubElo / FBref — club Elo (stub in v1, live in v1.1)
    │   │       ├── model.py             # Elo + host/home + altitude → p_a / p_draw / p_b
    │   │       ├── drivers.py           # ranked driver list (football-specific)
    │   │       ├── voice.py             # football explainer voice templates
    │   │       └── calibration.py       # Brier, reliability bins (offline)
    │   │
    │   ├── scheduler.py                 # APScheduler — three speeds (model/verdict/explainer)
    │   └── cli.py                       # `desk run`, `desk match <id>`, `desk replay <id>`, `desk sports`
    │
    ├── tests/
    │   ├── conftest.py
    │   ├── fixtures/                    # frozen feature vectors, market snapshots
    │   ├── test_contract.py             # sport-tagged contract round-trips
    │   ├── test_verdict.py              # threshold logic, sport-agnostic
    │   ├── test_late_binding.py         # late-binding rule
    │   ├── test_explainer_voice.py      # voice-rule asserts on prompt outputs
    │   └── sports/football/
    │       ├── test_model.py
    │       └── test_fixtures.py
    └── data/
        ├── output/
        │   └── football/                # per-match JSON + index.json — sport-partitioned
        ├── snapshots/
        └── cache/
```

### Sport boundary — what `Sport` ABC enforces

`desk/sport.py` defines:

```python
class Sport(Protocol):
    code: str                            # "football", "basketball", ...
    def list_fixtures(self) -> Iterable[FixtureRef]: ...
    def build_features(self, fx: FixtureRef, asof: datetime) -> FeatureRow: ...
    def model(self, features: FeatureRow) -> ModelOutput: ...   # returns p per outcome + drivers
    def voice_templates(self) -> ExplainerTemplates: ...
    def market_outcomes(self) -> list[str]:                     # ["a", "draw", "b"] for football, ["a", "b"] for tennis
```

The verdict step, explainer scaffold, scheduler, and publisher are all written against this protocol — they never import from `sports/football/` directly. Adding tennis later = a new package implementing `Sport`. The `SPORT_REGISTRY` enables/disables sports per-environment.

## 4. Build order — six PRs

Each PR must ship green tests and update `desk/README.md`. Don't open the next until the previous is merged.

### PR 1 — skeleton + output contract (½ day)
Pydantic models for the published JSON. Static-file publisher writing `data/output/{match_id}.json` and `data/output/index.json`. ETag from content hash.

**Acceptance.** `pytest tests/test_contract.py` green. A hand-built `MatchOutput` round-trips through the publisher and reloads identically. `index.json` lists every match with `match_id`, `kickoff_utc`, `updated_at`.

### PR 2 — fixture ingest + match identity (1 day)
Pull **every priced football match** from Kalshi + Polymarket — not WC-only. International fixtures join FIFA metadata; club fixtures join a club-metadata adapter (stadium, league, matchday). Normalised to one `FixtureRef` per match. WC 2026 is just one slice of the fixture list.

**Match ID format:** `{sport}-{competition}-{team_a}-{team_b}-{yyyymmdd}`. Examples:

- WC 2026 group: `fb-wc26-fra-mex-20260612` (ISO3 codes for national sides)
- Premier League: `fb-epl-mun-liv-20260815` (canonical club slugs)
- UCL knockout: `fb-ucl-rma-bay-20260311`

The `competition` segment encodes both league and stage where relevant. The team-ID system (clubs + national sides in one namespace) is parked at §10 — flag any ambiguity to Adi rather than guessing.

**Acceptance.** `desk run --once` writes one stub `MatchOutput` JSON per priced football fixture (covering the WC 2026 set + whatever club football is currently priced) with `verdict.state="pass"`, empty `copy.*`. `desk sports` lists `football` as the only active sport. `data/output/football/index.json` lists everything; sport partition exists on disk.

### PR 3 — football model v1 (1 day)
Lives at `desk/sports/football/model.py`. Elo prior — from Wikipedia data module for international, from ClubElo / FBref for club (club source can be a stub returning a fixed Elo with a TODO in v1; live in v1.1).

Adjustments:

- **Host bonus** (international tournaments at host venues): +75 Elo when `venue.country` ∈ host-list **and** the team ISO3 matches `venue.country`. WC 2026 host-list is {USA, CAN, MEX}.
- **Home-ground bonus** (club football): +60 Elo when the team is the home side at its registered ground. Mutually exclusive with host bonus.
- **Altitude bonus**: +X Elo per 1000m above 1000m for the team acclimatised to altitude (lookup table).

Map Elo diff → `p_a / p_draw / p_b` via standard Elo expectation + a draw-share function.

**Acceptance.** `tests/sports/football/test_model.py` covers three frozen feature vectors (one international, one club home-fixture, one altitude case) → expected probabilities (tolerance ±0.5pp). Sum = 1.0 ±1e−9. Host bonus does not fire for Mexico at MetLife. Home-ground bonus does not fire on neutral-venue club fixtures (e.g. UCL final).

### PR 4 — verdict step + thresholds (½ day)
Live market polling (60s default). Compare model probability for each side to best-of-Kalshi/Polymarket implied probability. **Codified thresholds** (lock these as constants in `desk/verdict/thresholds.py`, override in `.env`):

| State | Rule |
|---|---|
| Pick | `model_p − best_market_p ≥ 3.0pp` for some side |
| Pass | every side: `\|model_p − best_market_p\| < 1.0pp` |
| Avoid | every side: `model_p − best_market_p ≤ −2.0pp` (both venues priced inside our number across the board) |
| Default | anything in between → `pass` |

`market_venue` = whichever of Kalshi/Polymarket gives the better price for the called side.

**Acceptance.** `tests/test_verdict.py` exercises each branch with synthetic market snapshots. Threshold change in `.env` flips state without code change.

### PR 5 — explainer (1 day)
Three Haiku prompts (title, summary, blurb). Voice rules (sentence case, no emoji, no "bet/back/lock", attribution to publication for sourced facts) baked in as system prompt + post-generation regex assertions. Cache: re-call only when `verdict.state` transitions, **not** on `verdict.price` drift inside the same state.

**Acceptance.** `tests/test_explainer_voice.py` regex-asserts banned phrases never appear across 20 generated samples. State-transition cache miss/hit logic verified. Stub model that returns deterministic strings for offline test runs.

### PR 6 — scheduler + CLI + serve (½ day)
APScheduler in-process: model job (cadence ladder per `feedback_late_binding_features.md` — weekly outside T−5, daily T−5..T−3, hourly T−3..T−1h, final T−1h), verdict job (60s), explainer job (event-driven on state transition). FastAPI process serves `/output/*` static + `GET /healthz`.

**Acceptance.** `desk run` runs continuously, writes updated JSONs, `index.json` `updated_at` advances. `curl /output/index.json` returns the file with correct ETag. `desk replay <match_id> --as-of T-5d` recomputes from snapshot for evaluation.

## 5. Stack & conventions

- **Python 3.11**, `httpx` async client, `pydantic` v2, `APScheduler`, `anthropic` SDK, `pandas` + `pyarrow` for snapshots, `pytest` + `pytest-asyncio`, `ruff` (lint + format).
- No DB. JSON + parquet on disk. Cache TTLs in `desk/config.py`.
- One `Source` ABC in `desk/ingest/base.py` — every source subclasses it (`fetch()`, `cache_key`, `ttl`). Retry policy is shared.
- Pydantic v2 models for the output contract are the single source of truth. Generate JSON Schema from them; commit to `desk/contract.schema.json`.
- All times stored UTC. ISO-8601 with `Z` suffix.
- All scrapers respect robots.txt and the per-source rate limits noted in `RECOMMENDATION_ENGINE_DESIGN.md` (e.g. FBref ≤ 1 req / 3s).
- Anthropic key in `.env` only. Log token usage per match per day to `data/cache/llm_usage.csv`.

## 6. Output contract — canonical

The shape Faktor consumes — do not add fields without an ADR. Model internals (`p_a`, `p_draw`, `p_b`, `xg_*`, `drivers`, `confidence`, raw market prices) **stay inside The Desk**.

```json
{
  "match_id": "fb-wc26-fra-mex-20260612",
  "sport": "football",
  "competition": { "code": "wc26", "label": "FIFA World Cup 2026", "stage": "group_d" },
  "kickoff_utc": "2026-06-12T19:00:00Z",
  "team_a": "France",
  "team_b": "Mexico",
  "venue": { "city": "Guadalajara", "stadium": "Estadio Akron", "country": "MX" },
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

`sport` is the lookup key into `SPORT_REGISTRY`; `competition.code` is the league or tournament. `competition.stage` is optional (`"group_d"`, `"semi_final"`, `"matchday_8"` — populated when meaningful, omitted otherwise). The earlier top-level `group` field is gone — group is just one kind of stage.

`verdict.side` carries the team **name** or `"draw"` or `null` — never `"team_a"`. `verdict.market_venue` is `null` on Pass and Avoid. Pass has no CTA in the UI; Avoid renders distinctly (negative signal, no venue link). `market_outcomes` for football is `["a", "draw", "b"]`; for sports without a draw it'll be `["a", "b"]` — the contract accommodates both.

## 7. Late-binding features — codified

Hard rule, enforced by `desk/features/builder.py`:

| Feature | First binds at | Refresh cadence |
|---|---|---|
| Elo, FIFA rank, recent form, structural class, altitude | Always | Weekly |
| Weather (OpenWeatherMap) | T−5 days | Daily, then hourly inside T−24h, final at T−2h |
| Injury / availability picture (news pipeline) | T−3 days | Hourly |
| Confirmed XI | T−1h | Once |

Outside its window, a feature is **absent from the feature row**, not zero-filled. UI will surface "this updates closer to kickoff" copy off that absence. A unit test in `tests/test_late_binding.py` must fail if T−10d builds happen to include weather or injuries.

## 8. Tests / verification

- **Snapshot tests.** Three frozen WC matches with hand-built feature vectors → expected probabilities, expected verdict, expected blurb stub. Lock these as the regression guard.
- **Contract tests.** Round-trip every published JSON through Pydantic. Validate against `desk/contract.schema.json`.
- **Voice tests.** Banned-phrase regex over 20 generated explainer outputs (`bet`, `back the`, `lock`, emoji codepoints, all-caps stretches > 4 chars). Must pass.
- **Late-binding tests.** Build features at T−10, T−5, T−3, T−1h; assert the set of populated columns matches the table in §7 exactly.
- **Calibration harness.** `desk calibrate --from data/snapshots/` produces Brier and reliability bins on closed matches. Not blocking for v1 ship, but wire the command up.

## 9. Operational

- **Storage.** v1 publishes to local `data/output/`. Behind a `Publisher` interface so we can swap to S3 + CloudFront without touching the rest. Don't hardcode S3 in v1.
- **Logging.** Structured JSON to stdout. Per-job timing, per-source HTTP status, per-match LLM token counts.
- **Failure modes.** A source going down must not block a publish. Publish whatever's available; mark missing fields explicitly. The verdict step can run with stale market data up to 5 minutes; older than that → state defaults to `pass` and the blurb says so.
- **Observability.** `GET /healthz` returns last-publish timestamps for model / verdict / explainer jobs. That's the dashboard for v1.

## 10. Open questions for Adi (block these before merge)

- **Pick threshold pp.** Spec locks 3.0 / 1.0 / −2.0 as defaults. Confirm or override before PR 4.
- **Friendlies in form features.** Include / downweight / exclude? Need answer before PR 3 ships v1.1 with form.
- **Disclaimer surface.** Per-match card, footer, both? Affects the explainer prompt template.
- **CDN target.** Stay local for beta, or stand up S3 + CloudFront from day one? Affects PR 6 publisher.
- **Beta scope cut.** WC 2026 fixtures only on the public surface, with club football priced markets included as an internal output for evaluation? Or club football live from day one? The engine handles both — this is a UX call, not an architecture call.
- **Team-ID system.** National sides use ISO3. Clubs need a canonical slug — propose `{league_code}-{club_short}` (e.g. `epl-mun`, `laliga-rma`) but agree before PR 2.

## 11. v2 — admin backend for source control

Out of scope for v1, scoped here so PR layout doesn't paint us into a corner.

**What it does.** Lets Adi (and only Adi) toggle data sources on/off, adjust their tier weight in the news fact-extractor, override per-source refresh cadences, and override per-sport thresholds — without code changes or redeploys. Same surface used to enable a new sport package.

**Surface.**

- A YAML config at `data/config/sources.yaml` is the source of truth for source state, weights, and cadences.
- A small FastAPI admin app (`desk/admin/server.py`) on a separate port, single-user token from `.env` (`DESK_ADMIN_TOKEN`), endpoints:
  - `GET /admin/sources` — list every registered source with status, last fetch, last error.
  - `PATCH /admin/sources/{id}` — toggle enabled, change tier, change cadence override.
  - `GET /admin/sports` — list registered sports with active state.
  - `PATCH /admin/sports/{code}` — enable/disable a sport.
  - `GET /admin/thresholds` and `PATCH /admin/thresholds` — adjust Pick/Pass/Avoid pp.
  - `POST /admin/sources/{id}/test` — synchronously fetch + show what came back, without committing.
- A minimal React panel served at `/admin/ui` — table of sources with toggles, sliders for tier weight, last-error column. Hot-reloads on config change.

**v1 forward-compat preconditions.**

- Every ingest source registers itself at import time via `desk/ingest/base.py:registry`. v1 must wire this even though there's no UI — the registry is what v2's UI introspects.
- Per-source config fields (`enabled`, `tier`, `cadence_override`) live in `sources.yaml` from v1 onward, even if v1 only reads them on startup. The shape is fixed now.
- Per-sport `enabled` flag is read from `sources.yaml` at boot (defaults to `true` for football, `false` for everything else).
- Threshold constants in `desk/verdict/thresholds.py` are read once at process start; v1 can stop there. v2 makes them mutable.

**Acceptance for v2 (when it comes).** Toggle a source via the panel → next scheduled fetch reflects it without restart. Bump tier-2 to tier-1 → next news pull treats the source as primary. Add a fictional sport package and enable it via the panel → its fixtures appear in `index.json` within one scheduler tick.

## 12. What "done" looks like for v1

## 12. What "done" looks like for v1

- Every priced football match (WC 2026 fixtures + currently-priced club football) in `data/output/football/`, all green-validating against the schema.
- `data/output/football/index.json` lists every match with fresh `updated_at`.
- WC 2026 fixtures are individually addressable and complete (the launch-wedge guarantee).
- A picked match shows a `pick` verdict with non-null `side`, `market_venue`, `price`, and `edge_pp ≥ 3.0`.
- Three blurbs read in Odds Primer voice and pass the banned-phrase suite.
- `desk run` survives 24h continuous without crash; logs show all three job cadences firing.
- `desk sports` shows `football` enabled and the sport boundary holds — `grep -r "football" desk/verdict desk/explainer desk/scheduler desk/publish` returns zero hits.
- Faktor can `curl` `/output/football/index.json` and `/output/football/{match_id}.json` and render a card without any further coupling.

## 13. References

- `RECOMMENDATION_ENGINE_DESIGN.md` — architecture v0.2 (source of truth for the why).
- `Odds Primer Design System/` — voice, palette, type. Read `README.md` + `colors_and_type.css` before writing any explainer prompt.
- `faktor_engine_workbook_full.xlsx` — bespoke blurbs for matches 1–10, used as the voice-quality target for the explainer.
- `sports_data_sources_vetting.xlsx` — vetted source list.
