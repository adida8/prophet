# The Desk — Ops Dashboard Spec (v0.1 draft)

**Status:** draft, for build by Claude Code.
**Engine owner:** Adi — built in the `prophet` repo with Claude Code.
**Date:** 2026-05-21.
**Scope:** football matches only. Outrights are out of scope for v1 (§13).

**Relationship to existing specs**

- Reads from the **Publish** step of the pipeline in `THE_DESK_SPEC.md`; instruments **`run_once()`** in `desk/desk/runner.py`.
- Ties to **PR 6** (scheduler) for the run `trigger` field — until PR 6 lands, every run is `manual`.
- Surfaces the funnel that Phase B and live Elo (`THE_DESK_NEWS_SIGNALS_SPEC.md` §9.5) move — the stub-Elo count is a live read on whether match Picks are real signals yet.

---

## 0. The one principle

**The dashboard is read-only over a persisted run log. The engine's job is to leave a record of every run; the dashboard's job is to render it.**

Today the engine leaves no record. `run_once()` logs counts to the logger and returns a `dict[str, list[Path]]`, then forgets everything — there is no run history, no per-run snapshot, and therefore nothing to diff against. The load-bearing work in this spec is the **instrumentation + persistence** (§4–§6); the API (§7) and the UI (§8) are thin layers on top.

---

## 1. The gate-semantics correction (read this first)

The pipeline does **not drop** fixtures at the liquidity and stub-Elo gates. Per `desk/desk/verdict/decide.py`, both gates **force a `Pass`** — the fixture is still built and published, it just can't earn a Pick. So the funnel is **not** "how many survived to publish" (almost all do). It is:

> of the priced fixtures, how many were **eligible for a real verdict** — i.e. not forced to Pass by a gate.

The funnel narrows toward *Pick-eligibility*, and each narrowing carries a reason (`illiquid`, `stub_elo`). Publishing is near-total; the signal is in the forced-Pass reasons.

---

## 2. Goals / non-goals

**Goals**

- Persist a structured `RunReport` for every `run_once()` pass.
- Render a latest-run-first ops view: pipeline funnel, source freshness, verdict split, errors/filters, and a typed list of match changes vs the previous run.
- A clickable run history that loads any past run into the same view.
- Internal-only access (§9).

**Non-goals**

- No change to the published output contract (`publish/contract.py`, `contract.schema.json`). The run log is a **separate** internal artifact.
- No change to verdict thresholds, gate logic, or market-reading.
- No outrights (v1) — see §13.
- Not a public surface; not linked from the editorial site.

---

## 3. Where it sits

```
Ingest → Features → Model → Verdict → Publish
                                  │
                                  ▼
                          desk/ops/recorder.py   ← writes RunReport per run
                                  │
                          desk/data/output/ops/   ← run JSON + manifest (gitignored)
                                  │
                    desk_ops_api.py (/api/desk/ops/*)  ← read-only, access-gated
                                  │
                  frontend/src/desk/ops/  (React, /desk/ops route)
```

New **sport-agnostic** subsystem:

```
desk/ops/
├── report.py      # RunReport, StageCount, SourceStatus, MatchChange (Pydantic v2)
├── recorder.py    # build a RunReport during run_once; persist; prune retention
└── diff.py        # previous snapshot × current → list[MatchChange]
```

**Sport-boundary compliance (per CLAUDE.md):** `desk/ops/` is sport-agnostic and never imports from a sport package. The runner hands it already-computed counts and per-fixture verdict rows; `desk/ops/` never reaches into `desk/sports/`. Funnel stage *labels* are generic strings, so a future sport adds rows, not code.

---

## 4. The `RunReport` (data model)

One JSON document per run, written to `desk/data/output/ops/runs/{run_id}.json`. `run_id` = `run-{YYYYMMDDTHHMMSSZ}` (UTC, second precision).

```
RunReport
  run_id          run-20260521T060000Z
  started_at      ISO-8601 UTC
  finished_at     ISO-8601 UTC
  duration_s      float
  trigger         manual | scheduled        # scheduled only once PR 6 lands
  status          ok | partial | fail        # see §4.1
  competitions    ["wc26"]                    # from DESK_COMPETITIONS

  funnel          [StageCount]                # ordered, see §4.2
  forced_pass     { illiquid: int, stub_elo: int }
  verdicts        { pick: int, pass: int, avoid: int }

  sources         [SourceStatus]              # §4.3
  errors          [ { level, stage, message } ]   # level = warn | error
  changes         [MatchChange]               # vs previous run, §5

  snapshot        [FixtureRow]                # internal; basis for NEXT run's diff (§5)

StageCount   { stage: str, n: int, note: str | None }
SourceStatus { id, status, last_ok: ISO|null, detail: str }   # status = fresh|stale|failed|frozen|static
MatchChange  { type, match_id, from?, to?, detail? }          # §5
FixtureRow   { match_id, verdict_state, pick_side|null, edge_pp|null,
               venues: [str], copy_hash: str }                # copy_hash = sha256 of title+summary+blurb
```

`snapshot` is **internal** and never leaves the engine via the public contract; it exists so the next run can compute `changes`. It may be served to the *internal* ops API but is not part of `/api/desk/*`.

### 4.1 Run status

- `ok` — pipeline completed, Polymarket ingest succeeded.
- `partial` — completed but a non-fatal source failed (e.g. Kalshi pull failed, or a Polymarket page errored and was skipped) — captured in `errors`.
- `fail` — Polymarket ingest returned nothing / aborted before publish; `funnel` all-zero.

### 4.2 Funnel stages (ordered, football v1)

| stage | n = | source of the count |
|---|---|---|
| `polymarket_events` | raw events fetched from gamma | `PolymarketSoccerEventsSource.fetch()` length |
| `after_competition_filter` | kept after `DESK_COMPETITIONS` allowlist | `priced.py` allowlist log |
| `priced_fixtures` | fixtures with usable Polymarket prices | `list_priced_fixtures()` length; `note` = "N with kalshi coverage" |
| `verdict_eligible` | priced − illiquid − stub_elo | priced minus `forced_pass.*` |
| `published` | match JSONs written | count of `write_match` successes |

`verdict_eligible` is the meaningful bottom of the funnel (see §1). `published` should equal `priced_fixtures` minus per-fixture build/write failures — if it doesn't, that's a red flag the dashboard surfaces.

### 4.3 Sources (football v1)

| id | status derivation | detail |
|---|---|---|
| `polymarket_gamma` | `fresh` on success; `stale`/`failed` on error | "fixture-of-record · N markets" |
| `kalshi_kxwcgame` | `fresh` on success; `failed` if pull raised | "2nd venue · M of N matches priced" |
| `elo_seed` | `frozen` always until live Elo lands | "model prior · K of N fixtures on stub" — K is `forced_pass.stub_elo` proxy |
| `wc26_venues` | `static` | "16 venues" |

The `elo_seed` row is deliberately a live read on the live-Elo migration: while it says `frozen` and shows fixtures on stub, match Picks are not yet real signals. When `THE_DESK_NEWS_SIGNALS_SPEC.md` §9.5 / Phase 1b lands, this row flips to `fresh` and the stub count goes to zero on its own.

---

## 5. Diff engine (`desk/ops/diff.py`)

At the end of a run, load the previous run's `snapshot`, compare to the current run's, emit `changes`. Match key = `match_id`. Change types:

| type | fires when | carries |
|---|---|---|
| `new` | match_id present now, absent before | — |
| `dropped` | present before, absent now | — |
| `flip` | `verdict_state` changed | `from`, `to` (pick/pass/avoid) |
| `side` | state stayed `pick` but `pick_side` changed | `from`, `to` (team) |
| `edge` | `\|edge_pp_now − edge_pp_before\|` ≥ threshold (default 1.0pp) | `detail` = "+2.1pp (3.4 → 5.5)" |
| `venue` | `venues` set gained/lost a member | `detail` = "+ kalshi" / "− kalshi" |
| `copy` | `copy_hash` changed | — |

First run ever (no previous snapshot) → `changes = []`. Edge threshold is env-overridable (`DESK_OPS_EDGE_DELTA_PP`).

---

## 6. Instrumentation — wiring `run_once()`

The real work. Today `run_once()` (`desk/desk/runner.py`) catches per-fixture failures with bare `log.warning` and tallies only pick/pass/avoid. Changes:

1. **Build a `RunReport` as the pass executes** — capture `started_at`/`finished_at`, stage counts (§4.2), and per-source status. The priced-ingest layer already logs the counts it needs (`priced.py`); surface them as return values instead of log-only.
2. **Capture forced-Pass reasons.** `decide()` must report *why* it forced a Pass. Add an internal `DecisionMeta { forced_pass_reason: 'illiquid'|'stub_elo'|None, elo_source: 'wiki'|'clubelo'|'stub' }` returned alongside the `Verdict` (or via a side-channel the runner reads). Keep it **out of the published contract** — internal only. This is the one change that touches `verdict/`.
3. **Promote caught errors into the report.** Every `except` that currently does `log.warning(...)` also appends `{level, stage, message}` to `report.errors`. Logging stays; the report gains a structured copy.
4. **Compute `changes`** via `diff.py` against the previous run's snapshot.
5. **Persist** via `recorder.py`: atomic write of `{run_id}.json` (mirror the atomic-write discipline in `publish/writer.py`), update `ops/index.json` manifest, prune to the last `DESK_OPS_RETENTION` runs (default 200).

`run_once()` keeps its current return type for back-compat; the report is a side-effect. A run that aborts early still writes a `fail` report.

---

## 7. Ops API

New root-level adapter `desk_ops_api.py` (sibling of `desk_api.py`; same rationale — server runs from project root, `desk/` is an independent package). `APIRouter(prefix="/api/desk/ops")`, registered in `server.py` **before** the SPA catch-all (mirror the `/backtest` precedence note in CLAUDE.md). All routes behind the §9 gate.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/desk/ops/latest` | most recent `RunReport` |
| GET | `/api/desk/ops/runs?limit=50` | manifest rows: `run_id, finished_at, trigger, status, published, picks, change_count` |
| GET | `/api/desk/ops/runs/{run_id}` | full `RunReport` for one run |

`run_id` validated against `^run-\d{8}T\d{6}Z$` (defence-in-depth, like `_MATCH_ID_RE` in `desk_api.py`). 404 on unknown id.

---

## 8. Frontend — the dashboard

React page under `frontend/src/desk/ops/`, routed at **`/desk/ops`** (SPA). Reuses the existing `frontend/src/desk/` patterns and the Odds Primer tokens, but **utilitarian and dense** — this is an ops tool, not editorial. Visual reference: the approved mockup (`the_desk_ops_dashboard_mockup_v2`).

**Routing note:** `frontend/src/App.jsx` resolves routes with a manual `path.startsWith()` switch (no router library), and `path.startsWith('/desk')` already returns `<DeskApp />`. Add the `/desk/ops` branch **before** the general `/desk` line (or handle the sub-path inside `DeskApp`) so it doesn't fall through to the match list.

Layout, latest-run-first:

1. **Header strip** — run stamp + trigger, status pill, Reload button (re-hits `/latest`).
2. **Metric cards** — run id, status, duration, published, picks, changes.
3. **Pipeline funnel** — the five §4.2 stages as bars; forced-Pass reasons annotated under `verdict_eligible`.
4. **Sources read** — per-source freshness pill + last-ok + detail (§4.3).
5. **Verdict split** — pick/pass/avoid bar; note that Avoid is structurally ~0 on single-venue odds.
6. **Match changes since last run** — typed rows (§5), each with an icon + the change detail.
7. **Errors & filters** — structured `errors[]`.
8. **Run history** — manifest list from `/runs`; click a row to load that `run_id` into the whole view.

No new design tokens. Don't build a custom reload control beyond the header button. Mobile is not a requirement here (internal desktop tool) — but don't actively break narrow widths.

---

## 9. Access control — internal only

The site is public (`oddsprimer.com`), so the ops surface must be gated:

- HTTP Basic auth dependency on the `/api/desk/ops/*` router **and** the `/desk/ops` page, credentials from env (`DESK_OPS_USER`, `DESK_OPS_PASS`).
- If either env var is unset, the routes return **404** (not 401) — disabled-by-default, no acknowledgement that the surface exists.
- Document the env vars in `.env.example` and the CLAUDE.md Desk env table.

Basic auth over HTTPS is sufficient for a single-operator internal tool; a token or IP allowlist is an open decision (§14).

---

## 10. Testing

- **RunReport assembly:** a synthetic pipeline pass yields a report whose funnel counts are internally consistent (`verdict_eligible = priced − illiquid − stub_elo`; `pick+pass+avoid = published`).
- **Diff unit tests:** two consecutive snapshots → each change type fires exactly when §5 says (new/dropped/flip/side/edge/venue/copy), including the first-run empty case and the edge-threshold boundary.
- **Forced-Pass reason:** an illiquid market and a stub-Elo fixture each produce the right `DecisionMeta` reason and increment the right `forced_pass` counter.
- **Status classification:** Kalshi-fail → `partial`; Polymarket-empty → `fail`.
- **API gate:** missing creds → 404; wrong creds → 401; correct creds → 200. Bad `run_id` → 400/404.
- **Sport-boundary guard (mirror the backtest import-guard test):** assert no module in `desk/ops/` imports from `desk/sports/`.
- **Retention:** writing run N+1 past the cap prunes the oldest.
- No live network in tests — recorded fixtures only.

---

## 11. Cost & scale

Negligible. One small JSON per run (capped by retention), no LLM, no external calls beyond what the pipeline already makes. The diff loads exactly one previous file.

---

## 12. Phasing / PR ladder

Each PR ships tests green.

- **PR 1 — record.** `desk/ops/report.py` + `recorder.py`; instrument `run_once()` to build + persist a `RunReport` (funnel, sources, verdicts, errors, snapshot). No diff yet. *After this, every run leaves a record — the core dependency is satisfied.*
- **PR 2 — forced-Pass reasons.** `DecisionMeta` out of `decide()`; populate `forced_pass` + the `elo_seed` source detail. (Touches `verdict/`.)
- **PR 3 — diff.** `desk/ops/diff.py`; populate `changes` against the previous snapshot.
- **PR 4 — API.** `desk_ops_api.py` + the §9 gate; register in `server.py` before the SPA fallback.
- **PR 5 — dashboard.** React page at `/desk/ops` wired to the API; matches the mockup.
- **PR 6 — scheduler tie-in.** When PR 6 of the main ladder lands, set `trigger=scheduled` and confirm scheduled runs record cleanly.

PRs 1–3 are pure engine and independently useful (a persisted run log has value even before the UI). PRs 4–5 are the surface.

---

## 13. Outrights (deferred)

The outright engine (`desk/outrights/`) runs a parallel pipeline. Its run-level telemetry (MC-sim params, bootstrap CI width, per-team ladder moves) deserves the same treatment, but v1 is match-only. When added: a second `RunReport` flavour or a sibling `ops/outrights/` log, surfaced as a second tab. Designed-for, not built now.

---

## 14. Open decisions

- **Run-log storage:** per-run JSON files + manifest (proposed, mirrors `publish/writer.py`) vs a sqlite `desk/data/desk_ops.db`. JSON is inspectable and consistent; sqlite queries history better.
- **Forced-Pass reason channel:** `decide()` returns `(Verdict, DecisionMeta)` (proposed) vs a separate per-fixture meta map the runner assembles. The former is cleaner but touches every `decide()` caller.
- **Access:** HTTP Basic (proposed) vs signed token vs IP allowlist.
- **Retention `N`:** 200 runs proposed.
- **Frontend approach:** SPA route `/desk/ops` (proposed) vs a server-rendered HTML regenerated per run like `/backtest`. SPA gives clickable history for free; static is simpler to gate.
- **`snapshot` exposure:** serve the internal per-fixture snapshot on the *internal* ops API (handy for debugging) or keep it strictly engine-side.
