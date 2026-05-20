# TASK-311 — Desk outrights support (tournament / season-long winners)

Author: @adida8 (drafted)
Status: proposal
Owner-on-merge: split (backend + desk dev — see §9)
Source-of-truth predecessors:
  - [docs/desk-integration.md](../../docs/desk-integration.md) — Vercel ↔ Railway seam (don't re-litigate)
  - [tasks/research/TASK-141-events-markets-plan.md](TASK-141-events-markets-plan.md) — events / markets / outcomes schema
  - [tasks/research/TASK-167-event-setup-plan.md](TASK-167-event-setup-plan.md) — operator-curation pivot, `event_provider_configs`
  - [tasks/research/TASK-276-desk-python-audit.md](TASK-276-desk-python-audit.md) — desk-side audit (HTTP publish, DB-read posture)

## 0. Problem statement

The desk engine today prices **match-only** events: a two-team fixture with a scheduled kickoff, a 3-way `(a, draw, b)` market universe, and a football-specific Elo model. The pipeline rejects anything else at the adapter layer.

Tournament-winner markets ("Who wins the World Cup?", "Who wins Premier League 2025/26") are a first-class shape the desk should support — they're already ingested on the TS side (Polymarket / Kalshi expose them as events with N binary YES/NO child markets, one per participant) but the desk-side adapter discards them.

Goal: ship a parallel desk pipeline that ingests, models, prices, and publishes outright (N-way winner) verdicts, reusing the existing `events / markets / outcomes` schema and the existing `/api/desk/publish` HTTP seam — no schema upheaval, no new top-level contract.

## 1. Scope

In:
1. **DB**: one additive column on `events` (`kind`) to discriminate outright from match.
2. **Desk types**: a parallel `OutrightRef` dataclass + a discriminated `EventFixture` union (no breaking change to `FixtureRef`).
3. **Desk ingest adapter**: a new `supabase_outrights.py` under `desk/desk/sports/football/` that shapes outright event rows into `(OutrightRef, OutrightSnapshot)`.
4. **Desk model**: a market-anchored v1 (`desk/desk/sports/football/outright_model.py`) — market-prior with a small Elo-based tilt; gated behind the same threshold ladder as matches.
5. **Desk decide / publish path**: per-participant edges; the most-mispriced participant becomes the Pick; threshold ladder reused.
6. **Wire format**: NO change for v1 — reuse `deskContentPublishSchema` as-is. `verdict_side` = participant name. Follow-up adds an additive `verdict_participants[]` payload once the renderer is ready.
7. **Operator UX**: add a `kind` toggle on the event-create / event-detail forms (default `'match'`).
8. **Process-event dispatch**: route by `event.kind` in `desk/desk/process_event.py`.

Out:
- Brand-new contract surface (`OutrightOutput`) — the published `event_contents` row format stays event-agnostic at the column level. The full-distribution participant table is a follow-up (§7.2).
- Multi-sport outrights — football-only in v1. Tennis tournament winners follow the same shape but live in a future tennis package.
- Live re-pricing intra-tournament — same cadence as match events (notify-tick driven, ~30 min).
- Backtest support for outrights — non-trivial because resolution is single-event-per-tournament, not per-fixture. Tracked in §10.

## 2. Schema additions

One migration. Forward-only, additive, no backfill needed (existing rows default to `'match'`).

### 2.1 `event_kind` enum + `events.kind` column

```sql
-- supabase/migrations/<ts>_events_kind.sql

DO $$
BEGIN
  CREATE TYPE public.event_kind AS ENUM ('match', 'outright');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS kind public.event_kind NOT NULL DEFAULT 'match';

COMMENT ON COLUMN public.events.kind IS
  'Discriminator for desk-side dispatch. ''match'' = two-side fixture with '
  'kickoff_utc; ''outright'' = N-way tournament/season winner with no kickoff. '
  'Operator-set on event create — providers do not tag this reliably enough '
  'to auto-derive.';

CREATE INDEX IF NOT EXISTS events_kind_idx
  ON public.events (kind)
  WHERE deleted_at IS NULL;
```

Why a new enum and not a boolean: leaves room for future kinds (`'series'`, `'props'`, `'milestone'`) without an ALTER TYPE migration. Two-state booleans age badly in this codebase — see how `mutually_exclusive` already collides with what `kind = 'outright'` implies.

Why operator-set: Polymarket's `tag_slug=games` filter and Kalshi's series boundaries don't reliably separate outright markets from match markets; the operator already curates events per TASK-167. Adding a `kind` field to the create form is a one-line UI change.

Why NOT NULL DEFAULT `'match'`: all existing rows are matches (the adapter never produced anything else). Default keeps the migration forward-only with zero touch on existing rows.

### 2.2 No changes to `markets` or `outcomes`

The existing schema already supports the outright shape with zero migrations:

- An outright event has one row in `events` (e.g. "World Cup 2026 winner"), `kind = 'outright'`, `end_time` = tournament close.
- Each participant is one row in `markets`, binary YES/NO, e.g. question = "Will France win the World Cup 2026?".
- Each market has the usual two `outcomes` rows (`yes` / `no`, position_index 0 / 1).
- `outcomes.position_index` already reserves 2..N for forward-compat (per `0011_events_markets.sql:264`). Outrights don't need it but it's there if a provider ever ships non-binary outcome shapes.

The desk adapter reads "all live markets under event_id, treat each YES outcome as participant probability." That's a join, not a schema change.

### 2.3 Anon RLS — already correct

The existing anon-read policy on `events` (`events_public_read` in `0011`, status `IN ('active', 'closed')`) and the parallel ones on `markets` / `outcomes` apply unchanged. No new policies needed. Outright events go through the same gate.

### 2.4 Operator-side validation

Zod schema in `lib/schemas/event.ts` widens to include `kind: z.enum(['match', 'outright']).default('match')`. The create / update forms add a Select (default 'match'). The TS dashboard does NOT enforce kickoff presence based on kind today — that's a desk-side concern (outright events legitimately have a null `start_time`, end_time = tournament close).

## 3. Desk-side type changes

### 3.1 New dataclass parallel to `FixtureRef`

`desk/desk/sport.py` gains a sibling, not a replacement:

```python
@dataclass(frozen=True)
class OutrightRef:
    """A tournament / season-long winner market as the engine sees it.

    Parallels FixtureRef but the "participants" replace (team_a, team_b)
    and there is no kickoff — instead `closes_at` is the trading-window
    close (= events.end_time).
    """
    event_id:          str          # canonical Supabase UUID
    sport:             str
    competition_code:  str
    competition_label: str
    competition_stage: str | None    # e.g. 'group_stage_open', 'knockouts_in_progress'
    participants:      tuple[str, ...]      # ordered, e.g. ('France', 'Brazil', 'England', ...)
    closes_at:         datetime              # trading-window close (UTC)
    venue_country:     str | None            # host country (ISO-2) when known
    source_event_slug: str | None = None
    source_venue:      str | None = None
```

Key differences from `FixtureRef`:
- No `match_id` — outrights are identified by `event_id` (the Supabase UUID). The desk's `match_id` regex (`^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$`) hard-codes a date suffix; outrights don't have one. Reusing `event_id` removes the temptation to invent a fake date.
- `participants` is an ordered tuple (N ≥ 2), not a fixed pair.
- `closes_at` replaces `kickoff_utc`. The verdict step's "data must be fresher than the event" check still applies (the snapshot's asof must be ≤ now AND we must be before `closes_at`).

### 3.2 Discriminated union for downstream callers

```python
EventFixture = FixtureRef | OutrightRef
```

`Sport` protocol stays unchanged — it already returns `Iterable[FixtureRef]`. We add a parallel method:

```python
class Sport(Protocol):
    # ... existing ...

    def list_outright_priced(self) -> Iterable[tuple[OutrightRef, "OutrightSnapshot"]]:
        """Iterable of (outright, snapshot) pairs. Default impl returns []
        for sports that don't support outrights yet.
        """
        ...
```

Default to returning `()` on `FootballSport` until the adapter ships, so adding the protocol method doesn't break the runner.

### 3.3 OutrightSnapshot

Parallels `MarketSnapshot` in `desk/desk/verdict/compare.py`:

```python
@dataclass(frozen=True)
class ParticipantPrice:
    venue:        str               # 'polymarket' / 'kalshi'
    participant:  str               # e.g. 'France'
    implied_p:    float             # YES outcome's implied probability, [0, 1]

@dataclass(frozen=True)
class OutrightSnapshot:
    event_id: str
    asof:     datetime
    prices:   tuple[ParticipantPrice, ...] = ()

    def best_for(self, participant: str) -> ParticipantPrice | None: ...
    def has_full_coverage(self, participants: tuple[str, ...]) -> bool: ...
    def stale(self, *, now: datetime, max_age_sec: int = 1800) -> bool: ...
```

The stale window widens vs the match snapshot's 300s — outright prices move on news cycles, not minutes. 1800s matches the notify-tick cadence.

## 4. Desk-side ingest adapter

New module: `desk/desk/sports/football/supabase_outrights.py`. Same neighbourhood as `supabase_fixtures.py` for symmetry.

### 4.1 Entry point

```python
def outright_and_snapshot_from_row(
    row: dict[str, Any],
    *,
    asof: datetime | None = None,
) -> tuple[OutrightRef, OutrightSnapshot] | None:
    """Shape one outright event row into (OutrightRef, OutrightSnapshot).

    Returns None when the row can't be shaped — no markets, all markets
    deleted, or fewer than 2 participants resolvable.
    """
```

### 4.2 Participant extraction

Each child market is one participant. Resolution:

1. Parse the participant name from `markets.question`. Polymarket's outright questions follow `"Will <participant> win the <tournament>?"` — a regex over `^Will (.+?) win` extracts the participant. Kalshi outright markets follow a different but equally regular template; the adapter tries Polymarket regex first, falls back to Kalshi-shaped (`^Will (.+?) be the <tournament> champion`), then to the `markets.slug` segment after the event slug.
2. Normalise via `desk/desk/sports/football/teams.py:normalize_team` — same path the match adapter uses, so "USA" / "United States" / "🇺🇸" collapse to a canonical form.
3. Skip markets where extraction yields empty / a single token that's a stopword (`"draw"`, `"no winner"`, `"other"`).

Edge cases — explicitly skipped:
- "Field" / "Other" / "Any other team" — Polymarket emits these as a catch-all participant. Skip; they pollute the participant set and the model has nothing meaningful to say about them. Operator can re-include via a future allowlist column on `markets` if it matters.
- Resolved markets (`markets.status = 'resolved'`) — the participant is either confirmed loser (no=true → drop) or confirmed winner (yes=true → terminal event, skip publish). Both paths early-return None at the adapter layer; the publish path doesn't fire.

### 4.3 Price extraction

For each non-deleted, non-resolved market under the event:
- Find the YES outcome (`side = 'yes'`, fallback `position_index = 0`).
- Read `last_price_cents`, convert to `implied_p = cents / 100.0`.
- Skip when cents is null (outcome never priced) or out of range.

Probability mass normalisation: the YES implied probabilities across participants should sum to ~1.0 if the markets are mutually exclusive. They won't sum to exactly 1.0 in practice (venue overround). The model layer (§5) normalises; the snapshot layer reports raw implieds and lets downstream decide.

### 4.4 Competition resolution

Reuse `_resolve_competition` from `supabase_fixtures.py:110-144` — same slug-then-tags-then-unknown ladder. Outright events generally have well-tagged slugs (`worldcup-2026-winner`, `epl-2025-2026-winner`) so the prefix-match path hits more often than for matches.

## 5. Desk-side model — v1

New module: `desk/desk/sports/football/outright_model.py`.

### 5.1 Model strategy

The match model's Elo→3-way logistic doesn't generalise to N-way tournament outcomes (Elo gives pairwise win probability, not a tournament-winner distribution). Computing a true tournament-winner distribution requires either a Monte Carlo over the bracket (expensive, needs the full draw) or a stale closed-form approximation (unreliable for non-elimination formats like league seasons).

v1 takes the **market-prior, Elo-tilt** approach — small, honest, defensible:

1. **Start from the market's normalised distribution.** Sum the venue-best YES implieds across participants; divide each by the sum. This is the "market consensus" prior with overround removed.
2. **Compute an Elo-based prior** over the same participant set. For each participant, look up their current Elo (national for tournaments, club for leagues — `is_international_competition` already gates this). Convert to a softmax-shaped prior: `prior_p_i = exp(elo_i / scale) / Σ exp(elo_j / scale)`. `scale = 200` keeps the prior diffuse (a 200-Elo gap is ~e:1 odds, not 50:1).
3. **Blend.** `model_p = w * elo_prior + (1 - w) * market_prior`, with `w = 0.20`. The market dominates because we trust it for second-order corrections (form, injuries, news) we don't model. The 20% Elo tilt is just enough to flag participants the market is mispricing relative to baseline strength.
4. **Confidence band.** Bootstrap the same way the match model does (100 samples, ±50 Elo perturbation per participant, ±0.05 perturbation on `w`). Per-participant 5th/95th percentile bounds.

The blend weight `w` is a tunable constant at the top of the module, alongside the match model's `HOST_BONUS_ELO` etc. Backtest results (when wired — §10) drive the eventual choice.

### 5.2 When the model abstains

Force every participant to `Pass` (no Pick possible) when:
- Any participant's Elo source is `"stub"` — same guard as the match model (`decide.py:14-19`). For outrights, more permissive: if ≥ 80% of participants have real Elo, the remaining 20% just keep their market_prior unchanged (model contributes 0 for them). Only abstain when < 80% coverage.
- The market snapshot has < 80% participant coverage from any single venue. A snapshot with only 3 of 32 World Cup participants priced is unreliable.
- Snapshot is `stale(now, max_age_sec=1800)`.

### 5.3 Module signature

```python
@dataclass(frozen=True)
class OutrightFeatures:
    participants:       tuple[str, ...]
    is_international:   bool
    competition_code:   str
    market_implied:     dict[str, float]    # participant -> normalised market_p
    elo_by_participant: dict[str, float]
    elo_source_by_participant: dict[str, str]   # 'wiki' / 'clubelo' / 'stub'

@dataclass(frozen=True)
class OutrightModelOutput:
    model_p:       dict[str, float]
    model_p_lower: dict[str, float]
    model_p_upper: dict[str, float]
    elo_source_coverage: float   # 0..1
    abstain_reason: str | None   # None when model is confident enough to feed decide()

def compute(features: OutrightFeatures) -> OutrightModelOutput: ...
```

## 6. Desk-side decide path

New module: `desk/desk/verdict/decide_outright.py`. Parallels `decide.py` but operates per-participant.

### 6.1 Threshold ladder

Reuse the existing match thresholds (`DESK_PICK_PP`, `DESK_PASS_PP`, `DESK_AVOID_PP` from env, defaults 3.0 / 1.0 / -2.0). Per-participant edges:

```
edge_pp[p] = (model_p[p] - market_p[p]) * 100
```

Pick: the participant with `max(edge_pp) ≥ pick_pp`. Wins ties when multiple branches could fire.
Avoid: every participant's edge_pp ≤ avoid_pp. Rare in practice — the model is market-anchored so it can't all-Pass-and-some-Avoid simultaneously.
Pass: anything else.

### 6.2 Liquidity gate

Mirror `decide.py:14-15`'s liquidity rule, but at the participant level: participants with `market_implied ≤ 0.005` or `≥ 0.5` are excluded from the Pick search (a 50%+ implied is rare on an outright and usually signals tournament near-resolved, not a genuine edge).

The 0.5 ceiling is a guess — needs backtest tuning (§10).

### 6.3 Publish payload

Reuse `DeskContentPublish` as-is. Field mapping for an outright Pick:

| Wire field | Source |
|---|---|
| `event_id` | `OutrightRef.event_id` |
| `verdict` | `"Pick France (polymarket +280, edge +6.2pp) — World Cup 2026 winner."` |
| `article_body` | `copy.blurb` or templated fallback (same as match) |
| `verdict_state` | `'pick'` / `'pass'` / `'avoid'` |
| `verdict_side` | participant name, e.g. `"France"` |
| `verdict_market_venue` | venue of the best YES price |
| `verdict_price` | American-odds string from venue YES implied |
| `verdict_edge_pp` | picked participant's edge |
| `copy_title` / `copy_summary` | from explainer (templated v1, Haiku later) |
| `sources` | citations from explainer |

The B2C renderer (`components/b2c/event-content-section.tsx`) consumes these fields agnostic to event kind — nothing else changes downstream. The "Model: 18% · Market: 12% · Edge: +6.0pp" badge renders identically.

## 7. Wire-format follow-up (additive, post-v1)

### 7.1 What ships in v1

No change to `lib/desk/contract.ts:deskContentPublishSchema` or `desk/desk/publish/contract.py:DeskContentPublish`. The wire is event-agnostic at the column level. Reuse it.

### 7.2 What lands later — `verdict_participants[]`

Once the engine is reliably emitting full N-way distributions and the renderer wants to show a runner-ups table on outright B2C pages:

```ts
// additive nullable field, schema_version stays at 1
verdict_participants: z.array(z.object({
  name: z.string().min(1).max(200),
  model_p: z.number().min(0).max(1),
  market_p: z.number().min(0).max(1),
  edge_pp: z.number().min(-100).max(100),
  market_venue: z.string().min(1).max(50).nullable(),
})).nullable(),
```

Lockstep with the Pydantic mirror per [docs/desk-integration.md §3](../../docs/desk-integration.md). Forward-only nullable, no `schema_version` bump — additive nullable is the standard path.

Out-of-scope for this task. Tracked as a follow-up; flag the field in `tasks/research/` when the renderer change lands.

## 8. Operator UX

### 8.1 Event create / detail form

`components/event/event-form.tsx` (or equivalent) gains a Select:

```tsx
<Label htmlFor="kind">Event kind</Label>
<Select name="kind" defaultValue={event?.kind ?? 'match'}>
  <SelectItem value="match">Match (two-side fixture)</SelectItem>
  <SelectItem value="outright">Outright (tournament / season winner)</SelectItem>
</Select>
```

Zod schema (`lib/schemas/event.ts`) widens:

```ts
export const eventBaseSchema = z.object({
  // ...existing...
  kind: z.enum(['match', 'outright']).default('match'),
});
```

No validation coupling between `kind` and `start_time` / `end_time` at the action layer — the desk-side adapter is the one place that requires `closes_at` for outrights, and it skips rather than rejects. Keeping the operator UX permissive lets the operator save a draft outright before resolving the close-date.

### 8.2 Dashboard list affordance

`app/dashboard/events/page.tsx` gains a column / badge showing `kind`. Filter dropdown to scope to outrights / matches. Same pattern as the existing `status` filter.

### 8.3 No new operator allowlist

Outright events use the existing `CATEGORY_CREATE_ALLOWLIST` gate (per `0015_event_provider_configs.sql` + `app/actions/event*.ts`). Outrights are no riskier than matches.

## 9. Phasing / PR plan

Five PRs, sequenced so each merges in a working state.

### PR 1 — schema + operator UX (TS)

- Migration: `events.kind` enum + column + index (§2.1).
- Zod widening: `eventBaseSchema.kind` (§8.1).
- Form change: `<Select>` for kind (§8.1).
- Dashboard column + filter (§8.2).
- Tests: Zod accepts both values; form round-trips both kinds.

Per CLAUDE.md "Migrations (agent ↔ operator split)": ship the SQL + `.env.example` + docs prose. Operator runs `db push` against staging → smoke → merge → prod → `npm run types:generate` → commit types diff as `chore(types):` directly on `main`.

Owner: backend.

### PR 2 — desk types + adapter (Python)

- `desk/desk/sport.py`: add `OutrightRef`, widen `Sport` protocol with `list_outright_priced` (default `() -> []`).
- `desk/desk/verdict/compare.py`: add `OutrightSnapshot`, `ParticipantPrice`.
- `desk/desk/sports/football/supabase_outrights.py`: new module (§4).
- Tests: round-trip from a fixture-DB-row JSON blob through `outright_and_snapshot_from_row` produces expected `OutrightRef` + `OutrightSnapshot`.

No wire change. No operator-side concern.

Owner: desk dev.

### PR 3 — desk model + decide (Python)

- `desk/desk/sports/football/outright_model.py`: new module (§5).
- `desk/desk/verdict/decide_outright.py`: new module (§6).
- Tests: model produces normalised distributions; decide selects the participant with max edge when above threshold; falls back to Pass on coverage / liquidity gates.

No wire change. No operator-side concern.

Owner: desk dev.

### PR 4 — process_event dispatch (Python)

- `desk/desk/process_event.py:46-103`: branch on `row.get('kind')`. For `'outright'`, route to a new `_process_outright` that calls `outright_and_snapshot_from_row` → `compute` → `decide` → `_build_publish_payload`. The existing match path stays unchanged.
- `desk/desk/process_event.py:_build_publish_payload` widens to accept either an `OutrightRef` or `FixtureRef`; the templated verdict text branches on type. `_render_verdict_text` similarly.
- Tests: end-to-end with a mocked anon REST returning an outright event row produces a valid `DeskContentPublish`.

Owner: desk dev.

### PR 5 — observability + operator-doc

- Log lines: `process_event` log lines carry `kind=<match|outright>` so the operator can grep Vercel + Railway logs by event kind.
- `docs/desk-integration.md` §1 (Topology) gains a note: "outright events flow through the same hops; the dispatch happens inside `process_event.py`."
- `tasks/research/TASK-167-event-setup-plan.md` gains a follow-up note: "outright events: set `kind='outright'`, leave `start_time` null, set `end_time` to tournament close."
- This planning doc gets moved from `tasks/research/TASK-311-desk-outrights-plan.md` to itself with status flipped to `done`.

Owner: backend (docs) + desk dev (logs).

### Deploy-order across PRs

PR 1 (TS migration + form) must merge + ship to prod **before** PR 4 (Python dispatch) is enabled in production, otherwise `events.kind` is undefined on the read path and the dispatch defaults the wrong way. Easy: PR 1 ships first, operator merges, Vercel deploys, types regen → `chore(types):` on main. PR 2/3 are Python-only and merge in any order. PR 4 must merge after PR 1's types regen lands on main. PR 5 is doc / log only and can merge any time post-PR-4.

## 10. Risks / open questions

### 10.1 Model is weak in v1

The blend (`w=0.20` Elo tilt over market prior) is conservative. The Picks it surfaces will be near-market, which means most of them won't fire above the 3.0pp threshold. Expected outright Pick rate per tournament: 0–3 per surface (vs 5–20% of fixtures on the match side per editorial target).

Mitigation: ship the surface first, see how operators / B2C readers receive it, tune `w` via backtest (§10.4) before tightening or loosening thresholds.

### 10.2 Participant identity drift between venues

Polymarket calls France "France"; Kalshi might call it "FRA" or "France National Team". `normalize_team` handles most national-team aliases but tournament-specific edge cases (e.g. "USA" in Concacaf vs "United States" in FIFA contexts) will appear.

Mitigation: log every participant string the adapter extracts; operator audits via a one-shot SQL query post-rollout. Fix-as-needed in `desk/desk/sports/football/teams.py`.

### 10.3 Resolved markets mid-tournament

In an N-participant outright, individual participants get knocked out before the tournament ends — their YES market resolves NO, status flips to `'resolved'`. The adapter (§4.2) drops resolved markets; the model re-normalises over the remaining live participants on every notify-tick. This is correct behaviour, but needs an explicit test: as participants drop out, the surviving distribution adjusts and the operator-visible Picks shift accordingly.

### 10.4 Backtest support

The match backtest replays per-fixture: each historical fixture has a known resolution and a known closing price. Outright backtest needs a tournament-wide replay: a snapshot trajectory (one market state per notify-tick window) over the full tournament duration, with the eventual winner as ground truth.

Punted from v1. The desk has zero backtest harness for outrights and shipping one is its own multi-PR effort. Acceptable risk because outright Pick rate is low and the calibration cost is bounded.

### 10.5 Open question — should outrights publish to `event_contents` or a new table?

v1: same `event_contents` table. The schema is event-agnostic at the column level and B2C reads the latest non-deleted row per event regardless of kind.

Risk: if outright content is significantly different in shape (e.g. always carries a participants table once §7.2 lands), forcing it through the same table makes future shape divergence painful.

Recommendation: keep one table. Splitting now is premature. Revisit when §7.2's `verdict_participants[]` field becomes load-bearing for B2C render.

### 10.6 Open question — `closes_at` vs `kickoff_utc` invariants

The verdict step today uses `kickoff_utc` for the "snapshot must be before the event" gate. For outrights, the equivalent is "snapshot must be before `closes_at`" — same logic, different field name. The dispatch in PR 4 threads the right value per kind; tests pin both branches.

## 11. Acceptance criteria

A reader / reviewer should be able to verify:

1. `events.kind` column exists in prod, defaulting `'match'`. Operator can create an outright event via the dashboard.
2. The Python service routes by `events.kind` in `process_event.py` — log lines carry the kind on every event processed.
3. End-to-end: an operator creates a `'outright'` event with at least 3 child YES/NO markets, the next notify-tick triggers a desk run, and a row lands in `event_contents` with `verdict_state` populated and `verdict_side` matching one of the participants.
4. The B2C event page for an outright event renders the verdict badge identically to a match (no template fork — confirms the wire-format reuse holds).
5. The desk's `decide_outright` test suite covers: pick fires above threshold, pass fires below, avoid fires when every participant is over-priced, liquidity gate excludes near-resolved participants, abstain fires on low Elo coverage.
6. No regression on the match path — running the existing match-event fixtures through PR 4's widened dispatch produces byte-identical `event_contents` rows.

## 12. Cross-references

- [docs/desk-integration.md §3](../../docs/desk-integration.md) — contract / lockstep rules. v1 needs none of it (no wire change); §7.2 follow-up needs all of it.
- [tasks/research/TASK-141-events-markets-plan.md §2.2–2.4](TASK-141-events-markets-plan.md) — events / markets / outcomes schema authority.
- [tasks/research/TASK-167-event-setup-plan.md](TASK-167-event-setup-plan.md) — manual-curation posture; the `kind` toggle slots in naturally.
- [CLAUDE.md "Migrations (agent ↔ operator split)"](../../CLAUDE.md) — PR 1's migration follows this protocol verbatim.
