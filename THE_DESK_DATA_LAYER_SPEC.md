# The Desk — Data Layer Build Spec

**Status:** v0.5 build spec, 2026-05-18. Incorporates Faktor's engineering review on top of v0.4: Phase 1 split into 1a (foundation skeleton + forward-validation harness) and 1b (Elo wired through 1a); §3.3 made explicit on inbound slug→canonical resolution; `Source.fetch` signature corrected to async; env-var name aligned with the live repo.
**Target consumer:** Claude Code (agentic CLI).
**Owner:** Adi (desk dev).
**Scope:** football only; source-ingest architecture + a phased rollout. Budget ceiling ~$20/month.
**Predecessor docs:** `docs/how-the-desk-model-works.md` (what the model is starved of), `THE_DESK_SPEC.md` §3 + §7 (the original ingest + late-binding design this builds out).

> **Before you build — verify the codebase.** This spec asserts the existence
> and shape of `desk/desk/ingest/base.py`, the `Source` ABC + registry,
> `features_builder.py`, `_club_id_from_match_id`, `elo_seed.py`, the Supabase
> market ingest, `/healthz`, and the repo's migration protocol. These are
> inferred from `docs/how-the-desk-model-works.md`, not proven here. **Confirm
> each against the live repo before writing code; if a name or abstraction has
> drifted, adjust to what exists — do not build glue against an imagined
> architecture.**

> **Implementation guardrails — five hard rules, non-negotiable.**
> 1. **Phase 1 only** may affect live verdicts immediately. Phases 2–4 do not
>    touch verdicts until their forward-validation threshold is met (rule 2).
> 2. Phases 2–4 run in **Shadow mode** — collecting data, logging scored
>    predictions — until their paired model hook clears forward-validation
>    (§5). Shadow is the default state of every new phase.
> 3. A missing **critical** feature widens confidence or forces Pass per the
>    fixed criticality table in §3.6 — never a silent confident Pick.
> 4. The API-Football, OpenWeatherMap, and Railway assumptions in §4 / §3.4 are
>    **verified against current vendor terms before any code is written**.
> 5. **No change to the published JSON contract** without an ADR and Faktor
>    sign-off (§7).

---

## 0. Mission

The model isn't thin because the maths is wrong — it's thin because it's
**starved**. Today it reads Elo + venue + altitude, all from static files
committed weeks ago. No live Elo, club football is a dead zone (stub-Elo →
forced Pass), no form, no rank, no weather, no injuries.

This spec builds the **data layer**: the component that collects current,
cited, sport/team/event-keyed data from external sources and delivers it as a
clean feature row — so the model has something real to reason over.

North star: **the desk positions itself as the most credible engine in the
market.** "Credible" is made measurable in §1 — freshness leads it. This is an
*internal build target*, not launch copy — until model calibration and
forward-validation actually exist, the product surface should claim no more
than "traceable, fresh football market analysis". The spec aims at "most
credible"; the website earns the phrase later.

Football only in v1. Sources are sport-tagged so other sports plug in later
without a refactor. The roster in §4 lands at ~$19/month.

### 0.1 What changed from v0.1 — the central correction

v0.1 scoped the *model changes that consume the new data* entirely out, to be
"specced separately." Both adversarial reviews independently flagged this as
the spec's central flaw: a data layer that attaches features to a row the model
never reads **changes no verdict and moves no Brier score** — its phase PRs
would fail their own calibration acceptance tests.

v0.2 corrects this. The model-hook *design* can still live in a separate model
document (turning injuries into an Elo penalty is genuinely different work).
But the **sequencing is now coupled**: no data phase is "done" until its paired
model hook lands and the coupled unit passes a calibration check (§5). The data
layer is never built ahead of the model's ability to consume it.

## 1. What "credible" means — the measurable north star

Four pillars. Each is defined so it can actually be tested — vague pillars are
not acceptance criteria.

1. **Freshness — never stale.** Every datum has a freshness budget (TTL) and a
   binding window. The layer serves data inside its budget or marks the feature
   **absent** — it never serves a stale number as if current. *Measurable:* no
   datum reaches a verdict older than its TTL; a feature outside its
   late-binding window is absent, not zero-filled (unit-tested).
2. **Provenance — every claim is cited.** Every *externally-sourced* datum
   carries `(source_id, source_url, fetched_at)`. Derived features carry
   *lineage* — the set of source citations they were computed from plus the
   transform name (§3.5). *Measurable:* no externally-sourced field in a
   published verdict lacks a citation; no derived field lacks a lineage record.
   (Existing static tables — venue, altitude — carry a static-source citation;
   see §3.5.)
3. **Coverage — no structural dead zones.** Two parts. (a) *Structural:* the
   stub-Elo class of dead zone is eliminated by Phase 1 — no fixture with a
   known team falls back to a 1500 stub. (b) *Rate:* per live competition, a
   measured share of priced fixtures resolve to a full feature set; a
   competition below the floor (§3.3) does not go live. *Measurable:* coverage
   rate per competition, reported pre-publish.
4. **Calibration — the number is honest.** A coupled data+hook unit **passes**
   calibration when its Brier on the validation set (§5) is **no worse than the
   prior phase by more than a defined tolerance** *and* the feature shows sane
   directional behaviour — it moves probabilities the way the feature's theory
   predicts, not randomly. Beating the closing-market benchmark is the
   *long-term* north star, **not** a per-phase gate: a noisy ~100-fixture
   sample can look worse than the market even when a feature is directionally
   useful, so the phase gate is "no regression + sane direction", not
   "superiority". Calibration is checked on the *coupled unit*, never on a data
   phase alone — see §5.

## 2. Out of scope

- **The model-hook *design*.** *How* the model turns form/injuries into
  probability movement is specced in a separate model document. But per §0.1
  the hooks are **sequenced and gated with** their data phase — out of scope to
  *design here*, in scope to *land together*.
- **Non-football sources.** Architecture is sport-tagged; only football sources
  wired in v1.
- **Writing to Supabase from the desk.** The desk holds the anon key and stays
  DB-read-only for the *application* path. (Cache persistence is a separate
  question — see §3.4.)
- **Market-price ingest.** Already exists (Polymarket / Kalshi via Supabase).
  This spec is everything *except* market prices.
- **Winner-market data needs.** Separate spec — but the team registry (§3.3)
  and the `Source` layer (§3.1) are built **market-agnostic** so winners reuse
  them rather than re-implementing identity and ingest.

## 3. Architecture

### 3.1 The `Source` abstraction

Extends the existing `desk/desk/ingest/base.py` `Source` ABC + registry. Every
source declares:

```python
class Source:
    id:        str             # "clubelo", "api_football.injuries", ...
    sport:     str             # "football" — sources are sport-tagged
    data_type: DataType        # ELO | RANK | FORM | WEATHER | INJURIES | LINEUP | EXPERT
    tier:      int             # 1 = authoritative, 2 = corroborating / fallback
    ttl:       timedelta       # freshness budget
    binds_at:  timedelta | None  # late-binding: None = always; else "T minus X"
    rate_limit: RateLimit      # declared, enforced by a shared limiter (§4)
    async def fetch(self, key: FetchKey) -> list[Datum]: ...
    def cite(self, datum: Datum) -> Citation: ...
```

`fetch` is **async** — matches the existing `desk/desk/ingest/base.py` seam,
which is async today. (v0.4 wrote it sync by mistake; corrected per Faktor's
review.)

```python
```

Existing market-event sources are key-less fetch-all; new feature sources are
**keyed** (§3.2). Model this as a `KeyedSource(Source)` subclass or an optional
key param — implementer's call. Sources auto-register into `SOURCE_REGISTRY` at
import.

**Separation of concerns.** Keep two layers distinct so an absent feature is
debuggable: a **resolution/collection layer** (key derivation → source routing
→ fetch → cache → sanity gate) and a **feature-assembly layer** (builds the
`FootballFeatures` row from whatever the collection layer returned). An absent
feature carries a **reason code** — `unresolved_alias` / `outside_window` /
`source_failed` / `failed_sanity` / `rate_limited` — so a missing field is
never a mystery. (Same pattern as `abstain_reason` in the position-waist spec.)

### 3.2 Fetch keying — "collect based on sport, team, event"

A source is never "fetch everything" — it is fetched against a `FetchKey`
derived from the fixture:

| data_type | fetch key | granularity |
|---|---|---|
| ELO (national) | team ISO3 | per team |
| ELO (club) | canonical club id | per team |
| RANK | team id + competition context | per team |
| FORM | team id | last-N results, per team |
| WEATHER | (venue lat/lon, kickoff datetime) | per venue-day (batched) |
| INJURIES | team id | per team (batched by league where the API allows) |
| LINEUP | event id | per fixture |
| EXPERT | (team id, competition) | per team / competition |

The resolution layer walks a fixture, derives the keys, and asks the registry
for the active tier-1 source of each `(sport, data_type)`, fetched at the right
key. That walk is the collection logic.

### 3.3 The canonical team registry — the spine

Every source names teams differently: ClubElo `"ManCity"`, API-Football a
numeric id, World Football Elo `"England"`. **Identity drift is the data
layer's single biggest practical risk** — if the registry is wrong, *every*
downstream feature for that team is confidently wrong. This is not a support
table; it is the spine. v0.1 underspecced it; v0.2 gives it its own section.

**Canonical id.**
- National sides: ISO3 (`bra`, `eng`).
- Clubs: a **league-independent** stable id — e.g. an opaque slug `clb-<n>` or a
  name-derived slug that does **not** encode league. v0.1 proposed
  `{league}-{short}`; that is rejected — clubs are promoted, relegated, and
  move between competitions, and a league-encoded id breaks on every such move.

**The registry must handle, explicitly:** club renames and mergers; B / reserve
/ youth teams as distinct entities from the senior side; men's vs women's
sides; duplicate city names; historical names; accented vs ASCII forms; and one
canonical id mapping to *many* per-source aliases.

**The registry owns *both* directions of identity:**

- **Inbound — slug → canonical.** When a Polymarket / Kalshi event arrives,
  its slug fragments (e.g. `mun`, `fra`, `mci`) must resolve to canonical ids.
  This is the half that closes the prototype's "26 unmapped" dead zone — today
  `_club_id_from_match_id` returns `None` unconditionally, so *every* club
  fixture's Elo lookup misses. Phase 1a (§5) builds this inbound resolution
  alongside the registry itself.
- **Outbound — canonical → source-alias.** When the resolution layer asks a
  source for a datum, the registry translates the canonical id to that
  source's identifier (ClubElo's `"ManCity"`, API-Football's numeric id, World
  Football Elo's `"England"`, etc.).

A fixture's teams resolve to canonical ids once (inbound) and each source then
resolves canonical → its own key (outbound). A key that cannot resolve in
*either* direction → that datum is **absent** with reason `unresolved_alias`,
and the miss is recorded (§6).

**Resolution is a pre-flight blocking gate, not a reactive log.** Because
Phase 1 removes the stub-Elo safety net, an unresolved alias on match day → a
forced Pass on a real fixture. So: **a competition does not go live until its
alias coverage clears a two-part floor** — **≥95% of its known teams** *and*
**≥98% of the priced fixtures in the next publish window** resolve across all
required tier-1 sources. The fixture floor matters more than the team floor: a
team-level percentage can hide a high-traffic failure — the unresolved 5% being
exactly the popular clubs. Coverage below *either* floor blocks the competition
from the live surface; it does not silently degrade individual matches on the
day. Adding a new league is therefore an explicit onboarding step, not an
emergent one.

### 3.4 Cache, freshness & deployment reality

Each datum is cached with `fetched_at`. On read:

- inside TTL → serve;
- past TTL → refetch; on refetch failure, serve last-good **only if** within a
  hard `max_stale`, flagged; past `max_stale` → absent (reason `source_failed`).

The layer never silently serves a stale number as current.

**Deployment reality (this bit the v0.1 design).** The desk runs on Railway,
whose container filesystem is **ephemeral** — a redeploy or restart wipes a
local disk cache, and multiple instances don't share one. A naive local cache
therefore causes a **cold-start refetch storm** that blows the rate caps (§4).
Requirements:
- Cache directory on a **Railway persistent volume** if available; otherwise
  the cache is treated as cold-start-volatile and the next point applies.
  *Implementation note:* Railway mounts volumes at **runtime**, not at build or
  pre-deploy time — cache-directory initialisation must run at app startup
  *after* the mount, never during the build step, or it silently won't persist.
- **Rate-limit token accounting must survive restarts** — persist it, or on a
  cold start with no persisted state, assume the daily budget is partially
  spent and back off conservatively.
- **Cold-start backfill is throttled** — on an empty cache the layer refills
  gradually under the shared limiter, never blasting every source at once.

### 3.5 Provenance & lineage

Every externally-sourced `Datum` carries `Citation(source_id, source_url,
fetched_at)`. **Derived features** (`form_last_5`, `rank_delta`, an
`injury_severity` score) carry **lineage**: the set of source `Citation`s they
were computed from, plus the transform name. A verdict can always answer "where
did this come from, how old is it, and how was it computed."

Existing static inputs (the committed venue and altitude tables) are *not*
exempt from provenance — they carry a **static-source citation** (`source_id:
"static.venue_table"`, the commit/file as `source_url`). This keeps Pillar 2's
claim true without forcing a rewrite of the static tables: nothing is uncited,
but "cited" can mean "a committed static table" for inputs that aren't yet live.

### 3.6 Late-binding ladder — and what absence does to a verdict

Hard rule, enforced by the feature builder (per `THE_DESK_SPEC.md` §7 and the
late-binding feedback rule):

| Feature | Binds at | Refresh cadence |
|---|---|---|
| Elo, FIFA / club rank, recent form, altitude | always | weekly |
| Weather | T−5d | one multi-day forecast call, refreshed daily → hourly inside T−6h |
| Injuries / availability | T−3d | every 6–12h, then hourly inside T−24h |
| Confirmed XI | T−1h | poll from T−1h until confirmed or kickoff (not a single fetch) |
| Expert signal (free-content factual + editorial) | always (rolling) | daily; hourly extraction inside T−24h |

Outside its window a feature is **absent from the row**, not zero-filled. A
unit test fails if a T−10d build contains weather or injuries.

**Absence is not free — it has verdict consequences.** Distinguish two cases:
- *Absent because outside its window* (e.g. weather at T−10d) — expected,
  normal, no caveat. The UI's "updates closer to kickoff" copy covers it.
- *Absent because the source failed inside its window* (e.g. injuries missing
  at T−2d) — the verdict must **not** publish as if fully-informed. The model
  hook widens the confidence band for the missing feature, and the explainer
  emits a caveat ("injury picture unavailable at publish"). "Never stale" must
  not silently become "blind but still publishing a confident Pick."

**Feature criticality — what each missing feature actually does.** "Blind" is
not one thing; the consequence is fixed per feature so the model neither
over-penalises a harmless gap nor under-penalises a critical one:

| Missing feature | Consequence when absent inside its window |
|---|---|
| Elo | force Pass — no verdict without it |
| Rank / form | widen the confidence band slightly |
| Weather | no effect unless the weather model hook is Live |
| Injuries (inside T−3d) | widen the confidence band materially + explainer caveat |
| Confirmed lineup (inside T−1h) | widen the confidence band materially + explainer caveat |
| Expert signal | no model effect; explainer falls back to bare templated copy and fewer citations |

This table is the executable form of "never a confident Pick on a blind
feature row." Outside-window absence is exempt — it is expected, not blind.

### 3.7 Sanity gates — fresh + cited + wrong is still wrong

Freshness and citation gates do not catch *wrong* data, and wrong data with a
clean timestamp and a citation is the worst failure mode for a credibility
engine. Every datum passes plausibility checks before the feature-assembly
layer accepts it. At minimum:
- date/time sanity (kickoff not in the past, forecast date matches the fixture);
- entity match (the returned team/fixture is the one requested — no cross-wired
  squad, no lineup for the wrong fixture);
- range sanity (Elo within plausible bounds, weather coords within ~50km of the
  venue, standings from the current season);
- internal consistency (a YES implied probability in [0,1], a squad list of
  plausible size).

A datum failing a sanity gate is **absent** with reason `failed_sanity` and is
logged loudly — it is a source-quality signal, not a routine miss.

### 3.8 Tiering, fallback & failure isolation

Per data_type: one tier-1 (authoritative) source, optionally a tier-2
(corroborating / fallback). A source going down **never blocks a publish**
(`THE_DESK_SPEC.md` §9) — the feature degrades to absent (§3.6 governs the
verdict consequence). Where tier-1 and tier-2 cover the same datum and disagree
beyond a threshold, log it and prefer tier-1.

**Tier is overridable per competition** — API-Football may be strong for the
Premier League and weak for a smaller league's injuries. The registry's
per-source config (the original spec's pattern) carries a per-competition tier
override. v1 builds the *override hook*, not a full source × competition ×
recency reliability matrix — that breadth is a v2 concern.

**Tier-2 fallback is non-optional for INJURIES and LINEUP.** These are the
late-binding feeds whose absence most damages a verdict, and they ride the
single-provider spine (§4) — they get a real fallback in v1, not "optional."

## 4. Source roster & budget

What the architecture is wired to in v1. Every source is pluggable; this is the
recommended set, and it lands at ~$19/month.

| data_type | tier-1 | tier-2 | cost | notes |
|---|---|---|---|---|
| ELO national | World Football Elo Ratings (published table, parsed) | API-Football FIFA rank | free | weekly; updates after international windows |
| ELO club | ClubElo API (`api.clubelo.com`) | — | free | per-club CSV; carries point-in-time history |
| RANK | API-Football | — | incl. | FIFA rank + league standings |
| FORM | API-Football | — | incl. | last-N results per team |
| WEATHER | OpenWeatherMap | — | free | free tier ~1k calls/day — see budget below |
| INJURIES | API-Football | Highlightly (free, 100/day) | incl. | per-team availability |
| LINEUP | API-Football | Highlightly | incl. | confirmed XI ~1h pre-kickoff |
| EXPERT | curated local journalism + named-pundit public posts (free content only) | paywalled publications carried as citation-only | free | Phase 5; two-tier — factual corroborates Phase 4, editorial cites only |

**API-Football's entry plan — the spine** (covers RANK + FORM + INJURIES +
LINEUP). As of 2026-05-15 the Pro plan is listed at **$19/month, 7,500
requests/day, all endpoints** (injuries and lineups included) — pinned here as
a dependency, but **reconfirm against current vendor terms before
implementation** (guardrail 4). Cheaper and cleaner than four free scrapers.
**But the concentration is a real risk:** an API-Football outage or term change
degrades Phases 2–4 together. That is why the tier-2 fallback for
INJURIES/LINEUP is non-optional (§3.8), and why API-Football's coverage, ID
consistency, and historical depth must be *verified*, not assumed (§8).

### 4.1 Rate budget — reconcile cadence against caps (this must be shown, not asserted)

v0.1 asserted "usage stays an order of magnitude under the cap." The arithmetic
does not obviously hold: a 50-fixture club weekend, polling weather hourly per
fixture inside 24h, is ~1,200 calls against OpenWeatherMap's 1,000/day free
cap — and because the cap is *daily*, Friday's fixtures can drain the bucket
and silently degrade Sunday's matches.

The cadences in §3.6 are written to fit the caps; the implementation must
**prove** it with an instrumented count, not assume it. Levers, all baked into
§3.6 already:
- **Weather:** one multi-day forecast call per *venue-day* (not per fixture,
  not hourly) covering the whole T−5d window; refreshed daily; hourly polling
  only inside T−6h for fixtures kicking off that day. Batch fixtures sharing a
  venue/day into one call.
- **Injuries:** batch by league/date where API-Football allows it; cadence is
  6–12h until T−24h, hourly only inside the final day.
- **Cold starts:** §3.4's throttle prevents a redeploy from replaying the day's
  budget.

**OpenWeather overage.** OpenWeatherMap's One Call free allowance is ~1,000
calls/day; beyond it, it bills per call (≈ $0.0015/call as of 2026-05-15) —
overage is cents, not an outage. The design targets the free allowance but is
permitted to spill past it **under a hard monthly cap (≈ $1/month)**; past the
cap, weather degrades to absent / display-only rather than spending
uncontrolled. All-in cost: ~$19/month baseline, worst case ~$20 in
peak-fixture months — at the ~$20 ceiling, with the weather cap as the release
valve. (Flagged honestly: peak months sit *at* the ceiling, not comfortably
under it.)

**Acceptance (Phase 2):** an instrumented worst-case fixture-density estimate is
produced and shown to fit inside every source's cap with headroom for retries.
If it doesn't fit, widen cadences or budget the next API-Football tier — do not
ship a design that degrades on the busiest days.

## 5. Phased rollout — data + model-hook + calibration, as coupled units

Per §0.1, the unit of delivery is **not** a data phase — it is a data phase
*plus* its model hook *plus* a passing calibration check. The data-collection
PR and the model-hook PR may be separate PRs, but the phase is not "done" until
the coupled unit passes calibration. **Prove the loop end-to-end on Phase 2
before starting Phase 3** — Phase 2 is the pattern; if the data→hook→calibration
loop doesn't work there, it won't work for weather or injuries either.

### Calibration & the historical-data problem (read before Phase 2)

Live sources give *current* data. A naive WC-2022 backtest of a late-binding
feature would have to use **final match-day** weather/injuries — which leaks
future knowledge into the past and produces *falsely confident* calibration.
That is worse than no backtest. So:

- **Phase 1 (Elo)** — backtestable. ClubElo and World Football Elo carry
  point-in-time history; the WC-2022 backtest is valid.
- **Phases 2–4** — **forward-validated, not historically backtested.** At each
  bind point the layer logs the prediction, its as-of timestamp, and the
  feature set; as fixtures resolve, the prediction is scored. No late-binding
  feature is ever backtested with post-kickoff data.

**Three validation modes** — a phase moves through them in order; it never
skips:

1. **Shadow** — the phase collects data and logs scored predictions but **does
   not touch live verdicts**. The default state of every new phase. Starts as
   early as possible, well before launch, so evidence accumulates.
2. **Live** — the phase's model hook affects verdicts. A phase enters Live only
   after its forward-validation report clears the §1.4 gate over the minimum
   sample.
3. At **launch, only Phase 1 is Live.** Phases 2–4 are in Shadow at launch and
   graduate to Live independently as their evidence matures.

On the minimum sample: the target is ~100 resolved fixtures — **but the World
Cup is ~104 matches total, so waiting for 100 *World Cup* fixtures means the
tournament is over.** The forward-validation sample is therefore drawn from
*all priced fixtures the phase covers* (club football is year-round and
high-volume), not WC fixtures alone. The WC is the launch *surface*, not the
validation *sample*. A phase that genuinely cannot reach sample by a date that
matters simply stays in Shadow — Shadow is a safe, useful state, not a failure.

This makes the rollout slower to *prove* — but an honest forward-validation
beats a leaky backtest for an engine selling credibility.

### Phase 1a — Foundation skeleton (no behaviour change)

v0.4 framed Phase 1 as "swap the static `elo_seed.py` reads for live ones —
$0, no model hook." Faktor's review pushed back: the `Source` ABC in
`desk/desk/ingest/base.py` is currently a ~54-line stub (key-less async
`fetch()` returning `Any`, no `data_type` / `ttl` / `binds_at`, no `Datum` /
`Citation` / `RateLimit`, manual `register()`). The spec's §3 builds
substantially on top of it. So Phase 1 isn't "swap one read" — it's "build the
whole data-layer foundation, then wire Elo through it." Honest sequencing
splits these.

Phase 1a builds the foundation, **with no behaviour change**:

- The keyed-and-typed `Source` ABC (§3.1), plus `Datum`, `Citation`, `FetchKey`,
  `DataType`, `RateLimit` types, and `SOURCE_REGISTRY` auto-registration.
- The resolution / collection vs feature-assembly split (§3.1) — including
  reason-coded absences.
- The canonical team registry (§3.3) — **both directions**: inbound
  slug→canonical AND outbound canonical→source-alias.
- The pre-flight coverage gate (§3.3) — competitions don't go live until the
  two-part floor clears.
- The cache + freshness model (§3.4) — Railway persistent-volume posture,
  restart-safe rate-token accounting, cold-start backfill throttle.
- The shared rate limiter (§4.1).
- Sanity gates (§3.7).
- Provenance + lineage scaffolding (§3.5), including static-source `Citation`
  for the committed venue / altitude tables.
- The **forward-validation harness** — net-new infrastructure flagged in
  Faktor's review. New module `desk/verdict/forward_validation.py`. At each
  bind point it logs `(match_id, asof, feature_set, model_prediction)`; as
  fixtures resolve, it scores the logged predictions. Required by Phases 2–4's
  calibration gates per §5's three-mode validation. Reads accumulate to a
  desk-local store under the same persistence rules as the cache (§3.4).

Phase 1a is **behaviour-neutral**. The static `elo_seed.py` still owns Elo;
`model.py` and `decide.py` unchanged; the verdict pipeline produces
byte-identical output. The point of 1a is the foundation. 1b is what makes it
produce *different* verdicts.

**Acceptance (1a):**
- the new types exist and are unit-tested;
- the registry resolves a curated test set in *both* directions (inbound and
  outbound);
- the cache survives a container restart (persistent volume + cold-start
  throttle proven);
- the forward-validation harness records and scores predictions on a synthetic
  fixture;
- **WC-2022 backtest byte-identical to pre-1a** (no behaviour change is the
  regression gate).

### Phase 1b — Elo wired through 1a (highest leverage, $0, no model hook needed)

With 1a's foundation in place, swap the static reads in `features_builder.py`
for source-backed live reads:

- **Live national Elo** from World Football Elo Ratings (parsed table — ships
  with **parser hardening**: schema/shape check on every parse, fall back to
  last-good cached values on mismatch, loud alert). A silent parser break here
  takes down the World Cup wedge.
- **Live club Elo** from ClubElo API (`api.clubelo.com`).
- `_club_id_from_match_id` returns real canonical ids via the registry's
  inbound resolution (§3.3).

**Why first (after 1a):** closes the structural stub-Elo dead zone; real
current Elo is *more confident* Elo → tighter bootstrap bands; unlocks the
year-round club surface. The model already consumes Elo — no model hook
required.

**Acceptance (1b):**
- no fixture with a known team resolves to stub-Elo source; club fixtures
  carry real, cited Elo;
- per-competition alias coverage ≥95% before that competition goes live (§3.3);
- every Elo datum carries a `Citation`; parser-hardening fallback is tested;
- WC-2022 backtest Brier no worse than today.

*(Note: v0.1 listed "club fixtures produce non-Pass verdicts" as an acceptance
criterion — removed in v0.2. Whether a verdict is non-Pass depends on model
thresholds and market prices, not the data layer. Forcing that outcome would
be tuning to the test.)*

### Phase 2 — structural features: rank + form (the proving loop; $19/mo enters)

**Data PR:** API-Football standings + recent form, added to `FootballFeatures`.
**"Rank" is not one field** — FIFA rank, a league-table position, and a
tournament-group position are different constructs and must not be collapsed
into one comparable number. Split them at the schema level now: `fifa_rank`,
`league_table_position`, `league_points_per_match`, `competition_stage_rank`,
plus a `rank_context` tag. Each is **competition-aware** — friendlies,
neutral-site games, cross-league cup ties, and newly-promoted sides legitimately
lack one or more of these; in those cases the field is *absent* (reason:
not-applicable), never a forced or normalised number.
**Model-hook PR (paired):** the model gains a form/rank residual on the Elo
prior — the original spec's "biggest Brier lever" — consuming the split fields,
never a generic `rank`.
**Calibration:** forward-validation per §5; the coupled unit clears the §1.4
gate (no regression + sane direction).

**Acceptance:** every applicable fixture carries the split rank fields + form
with `Citation`s, absent (not zero, not normalised) where not applicable; the
rate-budget instrumentation (§4.1) is produced and fits the caps; the coupled
unit's forward-validation report clears the §1.4 gate.

### Phase 3 — weather (free, late-binding T−5d)

**Data PR:** OpenWeatherMap, keyed per venue-day (§4.1 batching), on the §3.6
cadence. Requires venue geocoding — fold in a venue→lat/lon table extending the
existing `wc26_venues` + club-grounds data.
**Model-hook PR (paired):** a weather adjustment — and the hook PR must *first*
demonstrate, on forward-validation, that weather moves Brier at all. "Heavy rain
→ draw-share tilt" is folk wisdom until the data says otherwise; if it doesn't
move the number, weather stays a *displayed* feature, not a *model input*.
**Calibration:** forward-validation per §5 (sample from all covered fixtures,
leakage-free).

**Acceptance:** weather absent outside T−5d (late-binding test); present, fresh,
cited inside; the model-hook PR's forward-validation either shows a Brier
improvement or weather is explicitly demoted to display-only.

### Phase 4 — injuries & availability (late-binding T−3d / T−1h)

**Pre-Phase-4 source audit (gate — do this first).** Phase 4 wants
*player-level* importance attributes. Confirm API-Football actually provides,
for the competitions in scope and on the chosen plan's endpoints, reliable
recent minutes / appearances and role per player. **If it can't, Phase 4 ships
availability-only and the model hook stays disabled (Shadow)** — rather than the
model inventing weak proxies. Do not assume the attributes exist.

**Data PR:** API-Football injuries + confirmed lineups, tier-2 fallback
Highlightly. The data collected is **player-level** where the audit confirms it
is available — not just an "availability list" but, per player, the attributes
the model hook needs to weight importance: position, role, recent minutes
share. A missing third-choice full-back and a missing first-choice keeper
cannot carry equal weight, and the data layer must collect enough to tell them
apart.
**Model-hook PR (paired):** translates player-level availability into an Elo
penalty. Genuinely hard modelling — but the data layer's job here is to deliver
the *attributes that make the weighting possible*, not a flat list.
**Calibration:** forward-validation per §5 (sample from all covered fixtures).

**Acceptance:** the source audit is done and recorded; injuries absent before
T−3d, lineup absent before T−1h; both cited; player-level attributes present
where the audit confirmed them; a source going down degrades to absent with a
verdict caveat (§3.6), never a crash, never a silent confident Pick.

### Phase 5 — expert signal: local journalism + ex-player punditry (free extraction + paywalled citations)

v0.3 deferred this entirely; v0.4 re-includes it as Phase 5 per product
direction, but **with the adversarial reviewers' concerns baked in as
constraints, not waived.** Specifically: the paywall paradox is resolved by
splitting extraction (free-content only) from citation (paywalled allowed); the
attribution / hallucination risk is closed by hard rules below; the "near-zero
model leverage" critique is honoured by keeping this layer out of the model
maths.

**What this phase adds.** A second editorial dimension — human-expert
corroboration on top of the structured feeds. Lets a verdict read "the model
rates France at X; L'Équipe's correspondent flags the same midfield gap" —
human alongside machine. Plus a tier-2 corroboration source for the Phase 4
injury/availability picture (a player flagged "doubtful" by a named columnist
alongside the structured feed).

**Two tiers, kept deliberately apart:**

- **Factual tier** — concrete claims (player doubtful, formation change,
  manager confirming X). Extracted only from *freely-accessible* content.
  Acts as **tier-2 corroboration** for Phase 4 features. **Never** a tier-1
  source. **Never** a direct model input on its own.
- **Editorial tier** — qualitative context (a season narrative, tactical read,
  manager-under-pressure note). Feeds the explainer — `copy.citations` and the
  "why this call" drivers — **never the model maths.**

**Paywall constraint (non-negotiable).** Extraction is permitted only on
*freely-accessible* content. A paywalled L'Équipe / Marca / Bild / Süddeutsche
column is a **citation target, not a scrape target** — the desk may link to
it but never claim knowledge of its body. Bypassing paywalls is out of scope
and forbidden. Free-tier portions of paywalled publications are eligible **iff
they are served as free content** (no login wall, no metered access). A source
is registered with an `access_kind ∈ {free, paywalled}` flag; the registry
rejects the contradiction "tier-1 paywalled" — tier-1 implies extraction, which
requires free access.

**Attribution discipline (hard rules).** Every extracted item carries (a) the
named publication or pundit, (b) a dated URL to the source, (c) the original
publication date. Only what a source actually *said*; never a paraphrase that
becomes a fabricated quote. The voice + banned-phrase tests apply across the
sample. A failed attribution test marks the item **absent** — it never
publishes. An automated test asserts no source flagged `paywalled` ever
produces an extracted body, only a citation — and runs on every PR.

**Source curation.** Per competition, an operator-curated list of
`(publication-or-pundit, access_kind)` registered as `Source(data_type=EXPERT)`.
Starting set for the WC 2026 launch: ESPN (free), BBC Sport (free), Globo
Esporte (free portions), L'Équipe (free / paywalled depth as citation), Marca
(free / paywalled depth as citation), Bild (free / paywalled depth as
citation), named-pundit public posts on broadcaster sites + social. The
curation is explicit and reviewable, not scraped wholesale.

**Model hook:** **none direct.** Factual tier feeds Phase 4 as tier-2
corroboration only; editorial tier is consumed by the explainer. Phase 5
therefore does *not* need the data-plus-hook calibration coupling that Phases
2–4 require. Its gate is editorial quality + attribution discipline, not
Brier movement.

**Validation modes (different from Phases 2–4):**
- **Shadow** — sources are collected and extracted, but neither the factual
  tier reaches Phase 4 corroboration nor the editorial tier reaches the
  explainer's published output. Items are visible internally so curation
  quality can be reviewed.
- **Live** — Phase 5 only goes Live after a **legal / attribution review**
  passes (a real human checkpoint, listed in §8) and the automated
  attribution / paywall tests are green across a sample of ≥200 extracted
  items.

**Acceptance:**
- Free-content extraction works on the curated sample; voice + banned-phrase
  tests pass.
- Every published `copy.citations` item carries (publication, dated URL,
  publication date); no extracted item appears without attribution.
- Automated test asserts zero extracted bodies from `paywalled` sources —
  citation-only.
- Legal/attribution review checkpoint is signed off before Live.

## 6. Operational

- **Storage & cache:** see §3.4 — persistent volume preferred, rate-token
  accounting survives restarts, cold-start backfill throttled.
- **Secrets:** `API_FOOTBALL_KEY`, `OPENWEATHERMAP_API_KEY` in `.env` only
  (the OpenWeather key matches the repo's existing naming; v0.4 wrote
  `OPENWEATHER_KEY` by mistake — corrected per Faktor's review);
  `.env.example` updated per the repo's migration protocol.
- **Rate discipline:** every source declares its limit; a shared limiter
  enforces it; §4.1's instrumented budget is a build artefact, kept current.
- **Coverage & miss reporting.** Alias misses, sanity-gate failures, and
  source failures are not just log lines. The layer produces a **pre-publish
  coverage report** per competition (the §3.3 gate reads from it) and an
  **alert** when coverage drops below the floor or a source's failure rate
  crosses a threshold. A full operator admin UI is *not* in scope — that is the
  existing v2-admin plan — but "logs are not an operating system": the report
  and the alert threshold are.
- **Logging:** per-source fetch status, cache hit/miss, datum freshness age,
  and every absence with its reason code (§3.1).
- **Failure mode:** any source down → its features absent with a reason, the
  verdict carries the §3.6 consequence, publish proceeds. Never a crash; never
  stale-as-fresh; never a confident Pick on a blind feature row.
- **`/healthz`:** extend with last-successful-fetch timestamp per source and
  current coverage rate per live competition.

## 7. Output contract impact

The website (Faktor's side) consumes only the published JSON contract. New
provenance and freshness data is useless if it never reaches the contract — and
*changing* the contract is not unilateral.

- If citations / lineage / a staleness indicator should be **visible** to the
  reader, that is a **contract change** → requires an ADR and Faktor sign-off,
  same as any contract field. Flag it; do not quietly widen the schema.
- If they stay **desk-internal** (used for gating and logging only, never
  rendered), the contract is unchanged — state that explicitly so the intent is
  recorded.
- v1 default: provenance and freshness are **desk-internal**; surfacing them on
  the site is a deliberate, separate, ADR'd decision. The data layer must not
  assume the contract changes.

## 8. Open questions

The load-bearing ones from v0.1 have been promoted into the spec body
(historical data → §5; cache persistence → §3.4; rate budget → §4.1). What
remains:

- **API-Football verification.** Before Phase 2 commits the $19 spine: confirm
  league coverage for the competitions in scope, ID consistency *across*
  endpoints, injury/lineup completeness and latency, and the exact daily cap.
  Pricing is directionally confirmed; *quality* is not.
- **National Elo source longevity.** World Football Elo Ratings is a parsed
  table, not an API. §5's parser hardening makes it survivable; is it
  acceptable long-term, or worth a paid structured national-rating feed later?
- **Persistent-volume availability.** Confirm Railway offers a persistent
  volume on the current plan; if not, §3.4's cold-start posture becomes the
  primary defence, not the fallback.
- **Phase 5 legal / attribution review.** Phase 5 only goes Live after a
  human checkpoint reviews the curated source list against the attribution
  rules, paywall constraint, and (where relevant) the publishers' terms.
  Listed here as a load-bearing gate, not a footnote.

## 9. References

- `docs/how-the-desk-model-works.md` §5, §10 — what the model is starved of today.
- `THE_DESK_SPEC.md` §3 (ingest `Source` ABC + registry), §7 (late-binding
  ladder) — this spec is the build-out of that original vision.
- `THE_DESK_POSITION_WAIST_SPEC.md` — independent workstream. The waist sits
  *below* the model; this data layer sits *above* it. They don't collide.
