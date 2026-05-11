# The Desk — SEO Copy Method (Brief)

**Status:** v0.1 brief, 2026-05-10. For Claude Code.
**Owner:** Adi.
**Pre-req:** PR 5 (Haiku explainer) — this brief extends PR 5 from a single
prose mode into a multi-mode SEO-aware generator.
**Renderer:** TBD. This brief is renderer-agnostic — it specifies the
**method** that produces the strings + structured fields. How they're
embedded in HTML (Faktor, our own static publisher, anything else) is a
later decision.

---

## 1. Goal

Extend the explainer so every published view carries copy that ranks for
the queries readers actually type. The blurb is the primary target —
that's where readers (and Google) spend time — but the title tag, meta
description, H1, and FAQ pairs all need SEO discipline because they
gate the click and the rich result.

Three view types ship: **match**, **competition**, **team**. The same
pipeline emits all three; only the prompt template, target queries, and
length caps differ.

## 2. What "SEO-optimized" means here

Concretely, every generated view must:

1. **Target a real query.** Each view type has a primary query pattern
   and 1–3 secondary queries. The primary query token must appear in
   the title tag, the H1, and at least once in the blurb.
2. **Cover the entities a reader needs.** For a match view: both teams,
   competition, kickoff date, model probability, market probability,
   the verdict state, and the edge in percentage points. Missing
   entities = page is thin.
3. **Stay within length caps.** Title tag ≤60 chars (Google truncation
   threshold), meta description ≤155 chars, H1 ≤80 chars, blurb 180–320
   words. Over the cap = post-check fails, regenerate.
4. **Read naturally.** No keyword stuffing — primary-query density <2%
   of total words. Flesch reading ease ≥45 (lower bound; "fairly
   difficult" but acceptable for sports content).
5. **Pass voice rules.** `desk/explainer/voice.py` is the gate. SEO
   mode does not relax it. New SEO-specific banned tokens listed
   in §6 below.
6. **Carry freshness.** Every blurb mentions the kickoff date in
   absolute form ("12 June 2026") and references `updated_at` so the
   renderer can surface a "Last updated…" line. Stale-feeling copy
   loses CTR even when Google shows it.

What we do **not** do: keyword density targeting beyond the <2% upper
bound, header keyword cramming, internal-link anchor stuffing, or
generating fake FAQ pairs to chase rich results. The voice rules
already forbid the language patterns that would tempt this.

## 3. Page-type taxonomy + target queries

| View | URL pattern (suggested) | Primary query | Secondary queries | Example primary |
|---|---|---|---|---|
| Match       | `/{competition}/{slug}/{date}` | `{team_a} vs {team_b} prediction` | `{team_a} vs {team_b} odds`, `{team_a} {team_b} pick`, `{competition} {team_a} {team_b}` | `france vs mexico prediction` |
| Competition | `/{competition}` | `{competition} predictions` | `{competition} picks`, `{competition} odds`, `{competition} matches today` | `world cup 2026 predictions` |
| Team        | `/team/{team_slug}` | `{team} {competition} predictions` | `{team} odds`, `{team} {competition} schedule`, `{team} fixtures` | `france world cup 2026 predictions` |

Slugs and URL patterns are renderer territory — the engine emits the
slug string, the renderer mounts it. Slug rules: lowercase ASCII,
team names ISO3 for nationals (`fra-mex`) or league-short for clubs
(`mun-liv`), competition codes from the existing competition map.

## 4. Method

The explainer takes existing pipeline outputs (`MatchOutput` for match
view; an aggregated rollup for competition/team views — see §7) and
produces an `SeoCopy` block per view.

### 4.1 Prompt structure

Three system prompts — one per view type. Each system prompt fixes:

- The voice rules verbatim (banned-phrase list inlined so the model has
  no excuse).
- The structural template the output must fit (title tag, meta, H1,
  blurb, optional FAQ pairs — fields per §5).
- The length caps.
- The "must include these entities" list for that view type.

The user prompt carries the per-view payload:

- **Match:** the `MatchOutput`, plus the rendered primary/secondary
  queries with team names already substituted in.
- **Competition:** the `CompetitionRollup` (count of priced matches,
  picks-rate, top edges, kickoff window) plus rendered queries.
- **Team:** the `TeamRollup` (this team's upcoming matches, priors,
  any active picks) plus rendered queries.

The model returns JSON. We parse, validate against `SeoCopy` (Pydantic
v2), then run the validation gates in §9.

### 4.2 Target-query injection

Query patterns live in `desk/explainer/seo/queries.py` as constants —
no config file in v1. Each pattern is a Python format string; the
explainer renders it with the entity payload before calling the model.
The rendered string is passed to the model in the user prompt as
"primary query" / "secondary queries" — not as a keyword the model
should stuff, but as the search intent the copy serves.

### 4.3 Entity-coverage injection

Each system prompt declares the must-cover entities for its view type.
The validation step (§9) checks each one is mentioned at least once in
the blurb. Examples:

- Match must-cover: team_a, team_b, competition.label, kickoff date,
  model_p (only when verdict is Pick), market_p (only when Pick),
  edge_pp (only when Pick or Avoid).
- Competition must-cover: competition.label, count of priced matches,
  the kickoff window dates, picks-rate.
- Team must-cover: team name, competition.label, count of upcoming
  matches, next kickoff date.

### 4.4 Retry-on-failure

Generation is wrapped in a retry loop: if the validation gates fail,
re-prompt with the specific failure message ("Blurb did not mention
kickoff date — regenerate") up to 2 retries. After 3 failures, fall
back to a templated stub (per state, per view type — analogous to
today's `desk/explainer/stub.py`) so we never publish nothing.

### 4.5 Determinism

Temperature 0.4 for the explainer call. Higher than today's stub
implies but kept low so re-runs don't churn the published copy. The
model's response is logged to `data/explainer/log/` for auditing.

## 5. Output fields per view type

A new `SeoCopy` Pydantic model lives in `desk/publish/contract.py`.
Whether it sits on the existing `Copy` model or as a sibling block is
deferred — both are easy. Fields, in order of priority:

```
match view (per MatchOutput):
  title_tag         str   ≤60   primary query + verdict cue
  meta_description  str   ≤155  what the reader will learn, with the verdict
  h1                str   ≤80   stronger headline form (no truncation pressure)
  blurb             str   180–320 words; the SEO-optimized prose
  faq               list  3 Q/A pairs, each Q ≤80 chars, A 30–60 words
  primary_query     str   the rendered target query (for renderer telemetry)
  entities_covered  list  validated entity names (for renderer + audit)

competition view (per CompetitionRollup):
  title_tag         str   ≤60
  meta_description  str   ≤155
  h1                str   ≤80
  blurb             str   220–360 words
  faq               list  4 Q/A pairs
  primary_query     str
  entities_covered  list

team view (per TeamRollup):
  title_tag         str   ≤60
  meta_description  str   ≤155
  h1                str   ≤80
  blurb             str   180–300 words
  faq               list  3 Q/A pairs
  primary_query     str
  entities_covered  list
```

`drivers` (the existing structured "Why this call?" list) stays on the
match view's `Copy` model alongside the SEO block — it's a UX
component, not SEO copy.

## 6. Voice rules — SEO mode

Reuse `desk/explainer/voice.py` verbatim. Add two SEO-specific
extensions in a `voice_seo.py` sibling:

- **Banned SEO patterns:** "best bets", "winning picks", "sure thing",
  "expert tips", "guaranteed wins", "click here", "learn more". These
  are sportsbook-affiliate vernacular and tank trust signals.
- **No question-stuffed H1s:** H1 must not be a question — questions
  belong in FAQ pairs only. Catches "Will France beat Mexico?" patterns
  Haiku will reach for if not blocked.

`assert_voice_clean()` runs first; the SEO extension runs second.
Failure of either raises `VoiceCheckFailed`, which the retry loop
catches.

## 7. Pipeline placement

Today's pipeline:

```
Ingest → Features → Model → Verdict → Explainer → Publish
```

Two changes:

1. **Explainer extends to multi-mode.** PR 5 already plans a Haiku
   replacement for the stub. This brief extends PR 5's scope so the
   explainer accepts a mode argument: `match`, `competition`, or
   `team`. Match mode runs per fixture as today; competition and team
   modes run per rollup (§7.2).

2. **Aggregator step before competition/team explainer runs.** New
   module `desk/publish/aggregator.py` rolls finished `MatchOutput`s
   into `CompetitionRollup` and `TeamRollup` view-models. Aggregation
   runs after the per-match explainer pass and before the per-rollup
   explainer pass. Pure functions — easy to unit test.

The publish step writes per-match JSON as today, plus per-competition
and per-team JSON. Schemas added to `desk/contract.schema.json`.

## 8. Model choice + volume

**Default: Haiku 4.5** for all three modes. SEO copy is prose-with-
constraints — Haiku handles it. Quality bar set by the eval harness
in §10; if Haiku fails the bar on a representative sample, fall back
to Sonnet 4.6 for that mode only (per-mode model override in
`config.py`). No dual-vendor stack — adds nothing.

**Volume per pipeline run** (WC 2026, ~78 priced fixtures, 32 teams,
1 competition):

- Match: 78 calls
- Competition: 1 call
- Team: 32 calls
- **Total: 111 generations per run.**

At Haiku's per-call cost this is rounding error. At pipeline cadence
(see PR 6 scheduler, hourly outside kickoff window, 5-minute inside),
total daily calls ≤3,000 even in the busiest WC week. Caching
suppresses repeat calls when inputs haven't changed (§9.6).

## 9. Validation gates

Every generated `SeoCopy` runs through these checks before publishing.
Failure raises a typed exception caught by the retry loop.

1. **Schema valid.** Pydantic v2 parses the model response.
2. **Voice clean.** `assert_voice_clean()` + SEO extension (§6).
3. **Length caps.** All fields within their caps; blurb word-count
   inside the per-view range.
4. **Primary-query placement.** Primary query (case-insensitive) appears
   in `title_tag`, `h1`, and at least once in `blurb`.
5. **Entity coverage.** Every entity in the must-cover list (§4.3)
   appears at least once in `blurb`.
6. **Keyword density.** Primary-query token frequency in blurb <2% of
   word count.
7. **Readability.** Flesch reading ease ≥45 on the blurb. Use
   `textstat` (pin in `pyproject.toml`).
8. **No-link-bait.** Title tag and meta description must not contain
   the SEO-banned patterns (§6).

A passing run sets `entities_covered` from the actual blurb match — the
renderer can audit which entities Haiku covered without re-parsing.

### 9.6 Caching

Hash the input payload (match data, queries, entity list) and skip the
Haiku call if the previous result for the same hash is on disk. Lives
at `data/explainer/cache/seo/{view}/{hash}.json`. Cache-bust on
content change is automatic since the hash includes the inputs.

## 10. Eval harness

Spec a small eval harness so model swaps don't regress quality.

- **Frozen test set:** 10 match fixtures + 1 competition + 5 teams
  drawn from the WC 2022 backtest snapshot. Fixed JSON inputs at
  `tests/explainer/seo/fixtures/`.
- **Snapshot tests:** schema-shape only (golden files at
  `tests/explainer/seo/golden/`). These guard against accidental
  contract drift, not prose quality.
- **Quality rubric (manual, run before each model swap):** 1–5 score
  on six dimensions — readability, accuracy of probabilities in prose,
  natural keyword placement, entity coverage feel, headline punch,
  FAQ usefulness. Rubric template at `tests/explainer/seo/rubric.md`.
  Mean ≥4.0 across all dimensions = pass.
- **Live monitoring:** log generation outcomes (pass / retry / stub
  fallback) to `data/explainer/log/seo.jsonl`. A daily summary surfaces
  the retry rate per view type — anything >5% means the prompt needs
  tightening.

## 11. Phasing

Ship in slices. Each slice green tests + dashboard regen.

- **SEO-1: Match mode.** Extend explainer with match SEO mode, add
  `SeoCopy` to contract, add validation gates, add eval fixtures for
  match. PR 5 absorbs this work.
- **SEO-2: Aggregator + competition mode.** New `aggregator.py`,
  `CompetitionRollup` view-model, competition mode in the explainer,
  per-competition JSON in the publish step.
- **SEO-3: Team mode.** Team rollup + team mode + per-team JSON.
- **SEO-4: Schema markup helpers.** Emit FAQPage and SportsEvent
  JSON-LD strings alongside the prose so any renderer can drop them
  into the page head verbatim. (Out of scope for v1 if the renderer
  prefers to build its own structured data.)

## 12. Open decisions / ADR candidates

- **Where does `SeoCopy` live?** On the existing `Copy` model, or as a
  sibling block on `MatchOutput` / new `CompetitionOutput` /
  `TeamOutput` containers? Recommend: sibling block — keeps the
  editorial UX copy (`drivers`) cleanly separate from the SEO copy
  (`SeoCopy`). ADR before SEO-1.
- **Pass / Avoid coverage on competition + team views.** Match mode
  generates copy for all three states (Pick / Pass / Avoid).
  Competition + team rollups should only surface Picks (the actionable
  signal); Pass + Avoid blurbs at fixture level still get generated
  but aren't aggregated up. Lock in SEO-2.
- **Multilingual.** WC 2026 audience is global. Defer until launch
  signal warrants it; if added, the prompt is the only thing that
  changes per locale, not the structure.
- **Schema markup ownership.** SEO-4 emits JSON-LD as strings; the
  renderer decides whether to use them. If the renderer wants the
  engine to skip JSON-LD entirely, the `SeoCopy` block stands alone.

---

## Acceptance criteria

SEO-1 ships when:

1. `desk/explainer/seo/` module exists, with one prompt template per
   view type and the validation pipeline wired in.
2. `MatchOutput.copy` (or sibling) carries an `SeoCopy` block on every
   published match.
3. All §9 validation gates run on every generation.
4. Retry-and-fall-back-to-stub path is exercised by tests.
5. Eval harness fixtures + snapshot tests in place.
6. Backtest re-run produces SEO copy for every fixture and the
   regenerated dashboard reads green.
7. Tests green: existing 146 + new SEO tests.

SEO-2 and SEO-3 follow the same shape with their own per-view fixtures.
