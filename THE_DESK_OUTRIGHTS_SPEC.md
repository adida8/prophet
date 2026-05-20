# The Desk — Outrights (Winner-Market) Spec

**Status:** v0.2 build spec, 2026-05-18. Supersedes v0.1 (prophet folder, 2026-05-11) and TASK-311 (the market-anchored draft in the integration repo). Both predecessors got *half* of the problem right: v0.1 had the right model approach (Monte Carlo tournament simulation, independent), TASK-311 had the right plumbing (event_id identity, reuse the wire). This spec is the consolidation — and adds the position-list framing the waist refactor unlocks.
**Target consumer:** Claude Code (agentic CLI), Faktor (engineering).
**Owner:** Adi (product).
**Sits on top of:** `THE_DESK_POSITION_WAIST_SPEC.md` v0.2 (refactor must land first) and `THE_DESK_DATA_LAYER_SPEC.md` v0.5 Phase 1b (live Elo — credibility-load-bearing).
**Launch market:** the FIFA World Cup 2026 winner market on Polymarket.

> **Before you build — verify the codebase.** Inherits the data layer spec's
> verify-first preamble. The outright code paths live in the same modules the
> data layer spec asserts the shape of (`desk/desk/ingest/base.py`,
> `process_event.py`, `desk/sports/football/...`); confirm those before writing
> outright code, same drill as the other specs.

---

## 0. Mission

The desk today evaluates priced *matches*. **Outrights** — single, long-dated
markets where you bet on the winner of a whole tournament — are a different
shape: one market per team, ~48 teams, no head-to-head. Today's adapter
discards them.

This spec adds outright support. Launch wedge: the WC 2026 winner market. The
architecture is sport-tagged so club outrights (UCL winner, EPL champion) plug
in later without a refactor.

The model is a Monte Carlo simulation of the tournament: stable inputs (live
Elo from the data layer, the fixed bracket structure) produce per-team
`P(team wins)` by simulating the tournament thousands of times. The verdict
step is **unchanged** — outrights feed the same generic `PositionSet` that
matches do, into the same generic `decide()`. The waist refactor made this
possible.

### 0.1 What's settled, what was wrong before

Two earlier drafts touched this territory; both are now superseded:

- **prophet v0.1 outrights spec.** Got the model right (MC sim, independent
  from the market) but predates the waist refactor — proposed a parallel
  `TournamentOutright` contract and a per-team-verdict array, building a
  parallel pipeline next to the match pipeline.
- **TASK-311.** Got the plumbing right (event_id identity, additive `kind`
  enum, reuse the published contract) but proposed a **market-anchored
  model** (80% market prior + 20% Elo tilt). Both adversarial reviews flagged
  this as the structural flaw — a model that's 80% market can't meaningfully
  disagree with the market, so it can almost never Pick. The
  *independent-`model_p`* invariant codified in the waist spec rules it out
  on principle.

v0.2 takes the good half of each: **independent MC model** (v0.1) + **event_id
identity, contract reuse where possible** (TASK-311). Plus the one thing
neither had: outrights feed the **position-list waist** — YES *and* NO per
team are first-class positions, which dissolves the broken "Avoid" state on
this market shape and naturally surfaces both "buy YES on Argentina" and "buy
NO on Holland" with the same verdict logic.

## 1. Out of scope

- **Anything but the WC 2026 winner market in v1.** Architecture is sport- +
  market-type-tagged so club outrights / golden boot / group winners plug in
  later; only WC-winner wired in v1.
- **In-tournament re-conditioning.** Once the tournament starts, real results
  collapse the bracket. v1 freezes the sim on pre-tournament inputs (or
  re-runs nightly with results-as-givens, but no live mid-match shifts). Live
  conditioning is an outright-v1.1 follow-up.
- **Backtest harness for outrights.** WC 2022 is a natural target (Argentina
  won) but the desk's backtest is match-shaped; an outright backtest is its
  own multi-PR effort. v1 ships forward-validated only.
- **Kalshi outright ingest.** Polymarket only in v1; Kalshi follows with a
  separate `Source` registration once Polymarket is stable.
- **Penalty-shootout modelling.** v1 resolves drawn knockout ties by
  Elo-weighted coin flip (a stronger side outperforms in extra time even if
  penalties are roughly coin flips). Explicit-penalty modelling is a v1.1
  refinement if backtest demands it.

## 2. Identity — `OutrightRef`

A new frozen dataclass parallel to `FixtureRef`, in `desk/desk/sport.py`:

```python
@dataclass(frozen=True)
class OutrightRef:
    """A tournament / season-long winner market as the engine sees it.

    Parallels FixtureRef: where a match has (team_a, team_b, kickoff_utc),
    an outright has (field, resolution_utc). Identified by event_id
    (the Supabase UUID), not a synthetic match_id — outrights have no
    kickoff to encode.
    """
    event_id:          str            # canonical Supabase UUID
    sport:             str
    competition_code:  str            # "wc26"
    competition_label: str            # "FIFA World Cup 2026"
    competition_stage: str | None     # "group_stage_open" / "knockouts_in_progress" / etc.
    market_type:       str            # "outright_winner"
    field:             tuple[str, ...]  # ordered participant team names
    resolution_utc:    datetime         # tournament close (the final)
    venue_country:     str | None       # host country (ISO-2) when known
    source_event_slug: str | None = None
    source_venue:      str | None = None   # "polymarket" / "kalshi"
```

Key choices, locked:

- **`event_id` is the identity, not `match_id`.** The match_id regex
  (`^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$`) hard-codes a date
  suffix; outrights don't have one. Reusing `event_id` removes the temptation
  to invent a fake date. The match_id regex stays unchanged — outrights don't
  use it.
- **`field`** is an ordered tuple of participant names (display strings,
  resolved to canonical team ids via the data-layer registry §3.3 — inbound
  resolution).
- **`resolution_utc`** replaces `kickoff_utc`. The freshness gate "data must
  be fresher than the event" still applies: snapshots must be before
  `resolution_utc`.

## 3. The 7-stage pipeline — what changes, what doesn't

The waist refactor (v0.2) made stages 5–7 generic. Outright support is
therefore concentrated above the waist — stages 1–4 + the 4.5 converter.

### Stage 1 — anon Supabase REST read (UNCHANGED)

Same `GET /rest/v1/events?id=eq.<uuid>&select=*,markets(*,outcomes(*))`. The
read doesn't care whether the event is a match or an outright — the dispatch
happens at stage 2.

### Stage 2 — adapter (NEW — `supabase_outrights.py`)

A sibling to `supabase_fixtures.py`, in `desk/desk/sports/football/`. The
dispatch is by `events.kind` (per TASK-311's schema addition — kept; one
additive enum column on `events`):

```
events.kind ∈ {'match', 'outright'} -- default 'match' for backward-compat
```

When `kind = 'outright'`, dispatch goes to `outright_from_row(row)` →
`OutrightRef` + the raw per-team Polymarket binary markets the row carries.

Inside the adapter:
- Each child market is one participant (one binary YES/NO market — "Will
  Argentina win the 2026 FIFA World Cup?"). The participant name is extracted
  from `markets.question` (regex `^Will (.+?) win the 2026 FIFA World Cup\??$`),
  normalised to a canonical team id via the data-layer registry (§3.3 inbound).
- "Field" / "Other" / "Any other team" sub-markets — explicitly skipped.
  They aren't a real team; the model has nothing meaningful to say about
  them. The operator can re-include via the data-layer registry's per-source
  config later if it matters.
- Resolved markets (`markets.status = 'resolved'`) — the participant is
  eliminated. The adapter drops them; the model re-normalises over the
  remaining live field on each tick. Out at v1 if you'd rather freeze the
  pre-tournament field — operator config flag.

### Stage 3 — features (NEW — `outright_features_builder.py`)

The match `features_builder.py` produces `FootballFeatures` per fixture. The
outright equivalent produces an `OutrightFeatures` per outright event:

```python
@dataclass(frozen=True)
class OutrightFeatures:
    field:              tuple[str, ...]            # canonical team ids
    field_display:      tuple[str, ...]            # display names
    elo_by_team:        dict[str, float]
    elo_source_by_team: dict[str, str]             # "wiki" / "clubelo" / "stub"
    bracket:            BracketStructure           # see §4
    host_iso3:          str | None                 # for host-nation bonus inside sim
    altitude_acclim:    dict[str, bool]            # per team — for altitude bonus inside sim
    asof:               datetime
```

`elo_by_team` is fetched via the data layer (Phase 1b live national Elo). A
team in the field that resolves to **stub** Elo via the registry → that team
keeps `elo_source = "stub"`; the model treats it as a low-confidence
participant (see §4.5 abstain rule).

### Stage 4 — the model (NEW — `outright_model.py`)

See §4 below.

### Stage 4.5 — `build_position_set_outright` (NEW)

Converts the MC output + market snapshot into the generic `PositionSet`. See
§5.

### Stage 5 — decide (UNCHANGED — generic per waist v0.2)

The waist's `decide(positions: PositionSet, thresholds=None) -> Verdict` runs
the existing Pick/Pass/Avoid ladder, unchanged. With ~96 positions in the set
(YES + NO per team for ~48 teams), it iterates them all, computes per-position
edges, returns the max-edge candidate that clears the lower-bound gate.

### Stage 6 — explainer (UNCHANGED interface, outright-aware copy)

`build_copy((PositionSet, Verdict))` is the same interface; the football copy
builder gains an outright branch reading `competition_label` /
`competition_stage` off the `PositionSet`. Verdict prose for an outright Pick
reads naturally:

> The model gives Argentina a 20.9% chance to lift the trophy; Polymarket
> prices that at 8.6%. The +12.3pp gap is the basis for the Pick.

For an outright Pick on a NO position:

> The model gives Holland a 4.2% chance to lift the trophy; Polymarket prices
> that at 7.1%. The -2.9pp gap on the YES side flips to a +2.9pp Pick on the
> NO — the position pays out if Holland *don't* win, which the model thinks
> is more likely than the market.

### Stage 7 — publish (LIKELY UNCHANGED — see §7 ADR)

The published `DeskContentPublish` shape can probably stay event-agnostic at
the column level. The only outright-specific question is whether to add a
`verdict_participants[]` payload for the website's outright ladder render.
That's an ADR — see §7.

## 4. The model — Monte Carlo tournament simulation

Lives in `desk/desk/sports/football/outright_model.py`. The maths is
deliberately small — same posture as the match model. Engine edge comes from
clean inputs (live Elo from Phase 1b), not from a clever simulator.

### 4.1 The pairwise primitive — reuse the match model

Per simulated game, the model uses **the existing match-model probability
function** `_probs_from_elos(elo_a, elo_b)` from
`desk/sports/football/model.py`. Same Elo logistic, same draw-share function,
same constants (`DRAW_PEAK`, `DRAW_FLOOR`, `DRAW_DECAY_PER_ELO`). The
optimization spec's Phase A bootstrap CI work applies inside the sim too —
each sample of the bootstrap perturbs Elo across the tournament.

This is non-negotiable: the per-tie maths is shared with matches. Two reasons:
- **Calibration.** If the match model and the outright model disagree on the
  same fixture, the engine is incoherent.
- **No new constants.** No new draw curve, no new Elo logistic. The MC sim
  is *just structure on top of the existing primitive.*

### 4.2 The bracket structure

`BracketStructure` is bundled data in `desk/desk/sports/football/data/wc26_bracket.py`:

- The 12 groups of 4 (per Wikipedia / FIFA — already encoded in the prototype).
- The progression rule: top 2 of each group + 8 best 3rd-place teams →
  Round of 32.
- The R32 → final knockout bracket per FIFA's published cross-group
  assignments.

For v1, ship a **standard seeded R32 bracket** (1 vs 32, 2 vs 31, …) if the
FIFA cross-group bracket isn't fully encoded yet — note clearly in the spec
that this is a simplification and the headline P(win) is close (within a few
pp for top teams) but not exact. Replace with the FIFA bracket as soon as the
data is loaded.

### 4.3 The simulation

```
SIMS = 10_000             # tunable; balance precision vs compute
SEED = 42                 # deterministic; required for diffable runs

for sim in range(SIMS):
    standings = run_group_stage(bracket.groups)     # uses _probs_from_elos for each game
    qualifiers = resolve_qualifiers(standings)      # top 2 + 8 best 3rds
    winner = run_knockout(qualifiers, bracket.knockout_bracket)
    tally[winner] += 1

model_p[team] = tally[team] / SIMS
```

Per-game resolution:
- **Group stage:** 3 outcomes (W/D/L), sampled from `_probs_from_elos`.
- **Knockout:** no draws — resample from the same triplet, with the draw
  share redistributed to the two winning sides proportionally (Elo-weighted
  coin flip — stronger side wins draws more often, reflecting extra-time
  performance).

Standings tiebreak (group stage):
- Points → goal differential (Elo-based proxy in v1 — no goal model yet)
  → Elo as final tiebreak.

The simulation is the desk's heaviest single piece of compute. It runs **on
the data layer's late-binding cadence** — weekly outside T−5d of the
tournament start, daily inside T−5d, hourly inside T−24h. Cached in the
data-layer cache (§3.4 of the data layer spec); rerun is gated by Elo
freshness, not market freshness.

### 4.4 The confidence band (Phase A bootstrap, applied to outrights)

The match model has a 100-sample bootstrap producing a 90% CI per outcome.
Outrights need the same — the verdict's lower-bound Pick gate
(`model_p_lower − market_p ≥ pick_pp`) is the *whole* reason Phase A worked
on matches.

Bootstrap design:
- 100 samples (same as match model).
- Per sample, perturb each team's Elo by uniform(±`ELO_PERTURBATION`) — same
  constant as the match model (currently 50).
- Each sample runs `BOOTSTRAP_SIMS = 1_000` tournaments (10× smaller than the
  point estimate's 10k — total compute: 100 × 1k = 100k sims per outright
  refresh, ~10× the baseline).
- Per-team P(win) distribution across the 100 samples → 5th / 95th
  percentile → `model_p_lower` / `model_p_upper`.

Per-team seed (for the bootstrap *itself*, not each sim within) derived
deterministically from event_id + bind-window timestamp so two runs at the
same bind window produce identical bands.

### 4.5 Abstain rules

The outright model abstains (sets `abstain_reason` on the PositionSet → Pass)
when:

- Any of the top-10 teams (by Elo) in the field resolves to **stub** Elo
  source. Top-10 stub means the simulator can't trust the tournament's
  contenders; better to publish Pass than a confident wrong Pick.
- Market snapshot has < 80% participant coverage from any single venue. A
  snapshot with 12 of 48 teams priced is unreliable.
- Snapshot is `stale(now, max_age_sec=1800)` — same TTL as
  `OutrightSnapshot` (see §5).

Below-top-10 stub Elo is *not* an abstain — the field carries longshots whose
Elo nobody quite knows; the simulator handles those by giving them their stub
1500 and letting the bracket carry them out cheaply.

## 5. Building the `PositionSet` — YES and NO per team

The waist's generic `PositionSet` carries a `tuple[Position, ...]`. The
outright converter (`build_position_set_outright`) emits **two positions per
participant** — a YES and a NO — read from the per-team binary markets.

```python
def build_position_set_outright(
    outright: OutrightRef,
    model: OutrightModelOutput,           # P(win) + bootstrap band per team
    snapshot: OutrightSnapshot,            # per-team YES + NO prices
) -> PositionSet:
    positions = []
    for team in outright.field:
        # YES position
        positions.append(Position(
            key          = f"{team}-yes",
            label        = f"YES {team}",
            model_p      = model.p_win[team],
            model_p_lower= model.p_win_lower[team],
            model_p_upper= model.p_win_upper[team],
            market_price = snapshot.yes_price[team],     # READ DIRECTLY, not derived
            market_venue = snapshot.venue[team],
            market_url   = snapshot.market_url_yes[team],
        ))
        # NO position — symmetric
        positions.append(Position(
            key          = f"{team}-no",
            label        = f"NO {team}",
            model_p      = 1.0 - model.p_win[team],
            model_p_lower= 1.0 - model.p_win_upper[team],   # bound flips
            model_p_upper= 1.0 - model.p_win_lower[team],
            market_price = snapshot.no_price[team],         # READ DIRECTLY
            market_venue = snapshot.venue[team],
            market_url   = snapshot.market_url_no[team],
        ))
    return PositionSet(
        event_id          = outright.event_id,
        asof              = snapshot.asof,
        positions         = tuple(positions),
        competition_label = outright.competition_label,
        competition_stage = outright.competition_stage,
        market_url        = ...,                        # set-level event URL
        abstain_reason    = model.abstain_reason,       # propagates §4.5
    )
```

**Key points:**

- **YES and NO are *both* first-class positions.** The waist's invariant
  ("read `market_price` directly, never derive as `1 − something`") matters
  here: the YES/NO spread on a longshot is real money, and naïve `1 − YES`
  would systematically misprice the NO side. Read from each token's own
  market.
- **Model `model_p_lower` / `model_p_upper` flip** for the NO side
  (`1 − upper` becomes the new lower, etc.). The verdict step doesn't care —
  it just compares `(model_p_lower − market_price)` per position.
- **The output is one `PositionSet` with ~96 `Position`s** for the WC winner
  market (48 teams × 2). The waist's `decide()` iterates all of them,
  computes edges, finds the max-edge candidate. No code in `decide()`
  changes; it just sees a longer list.

### 5.1 Devig — *not* a problem on this market shape

A common worry on outright markets is the field-wide overround (the 48 YES
prices sum to ~1.05–1.10, not 1.0). The position-list framing dissolves it:
each binary market has YES + NO ≈ 1.0 with a small per-market vig. We
evaluate each *position* against *its own market* — no field-wide
normalisation needed. The overround manifests naturally as a small bias
toward "Pick NO" on longshots (where YES is overpriced because the longshot
carries disproportionate vig), which is correct behaviour.

This is intentional and worth flagging: the v0.1 spec proposed a field-wide
normalisation, which would have introduced a modelling assumption we don't
need to make.

## 6. Verdict — what falls out

The waist's `decide()` returns a `Verdict` with `state` ∈ {pick, pass, avoid}
and `side` = the winning position's `label` (e.g. `"YES Argentina"` or
`"NO Holland"`).

Natural outcomes for an outright Pick:

- **YES Pick on a contender:** model thinks Argentina has more chance to win
  than the market does. Standard underdog-Pick framing.
- **NO Pick on a longshot:** model thinks Holland's YES is overpriced; the
  NO is the underpriced position. The verdict reads "Pick: NO Holland"
  naturally — no shoehorning into "Avoid YES."

**The "Avoid" state dissolves cleanly on this market shape.** v0.4 of the
data layer spec (and Phase A.4 of the optimization spec) noted that "Avoid"
is structurally impossible on single-venue normalised markets. On outrights
with YES + NO as separate positions, "Avoid the YES" *is* "Pick the NO" —
the same call, framed positively. v1 outright Picks/Passes; Avoid is
effectively unreachable on this market shape, by design.

## 7. Contract — ADR question

The website (Faktor's side) consumes the published JSON contract. Two
options:

- **Reuse `DeskContentPublish` as-is.** Set `verdict_side` to the winning
  position's label (e.g. `"NO Holland"`). The B2C renderer is event-agnostic
  at the column level. Cheapest, no contract change. **But:** the renderer
  only shows the single Pick; the rest of the ~48-team field is invisible.
  Outrights have a natural "show the whole ladder" UX that this throws away.
- **Add an additive `verdict_participants[]` field** (per TASK-311's §7.2 —
  the one piece of TASK-311 worth keeping). Nullable, forward-only, no
  schema-version bump. Carries per-team `{name, model_p, market_p, edge_pp,
  market_venue}` for the full field.

**My recommendation:** ship v1 with option 1 (reuse), and propose
`verdict_participants[]` as a follow-up ADR once the outright B2C renderer
is designed. Reasoning: the website's outright page doesn't exist yet, so
designing the contract for it is premature. Pick what the website actually
needs, ADR it, ship together.

Either way, this is a **contract change** (or a deliberate non-change) →
**ADR + Faktor sign-off** per the data layer spec's §7. Flagged here, not
decided in this spec.

## 8. PR plan

Each PR ships green tests + a backtest regen where applicable. Sequenced so
each merges in a working state. Branch off the integration repo's `main`.

### Prerequisites (must land first)

- `THE_DESK_POSITION_WAIST_SPEC.md` v0.2 → both PRs merged. The position-list
  is the spine.
- `THE_DESK_DATA_LAYER_SPEC.md` v0.5 Phase 1a + 1b → live Elo. The MC sim is
  not credible on stub Elo.

### PR O1 — `OutrightRef` + adapter + stub model

- `desk/desk/sport.py`: add `OutrightRef` alongside `FixtureRef`.
- TS-side migration (per TASK-311 §2.1, kept): `events.kind` enum + column.
  Default `'match'` for backward compatibility.
- `desk/desk/sports/football/supabase_outrights.py`: `outright_from_row` +
  the participant-extraction regex + the resolved-market skip.
- `desk/desk/sports/football/outright_model.py`: a **stub model** for this
  PR — produces `P(win) = softmax(elo / 200)` over the field. No MC sim yet.
  Lets the rest of the pipeline get wired without compute risk.
- `build_position_set_outright` per §5.
- `process_event.py` dispatch: route by `events.kind`.

**Acceptance.** End-to-end with a mocked Supabase row for the WC winner
event produces a valid `PositionSet` of ~96 `Position`s; `decide()` runs on
it without crashing; verdict is Pass-heavy (the stub model is uninformative)
but the contract round-trips.

### PR O2 — Monte Carlo simulator

- `desk/desk/sports/football/data/wc26_bracket.py`: the groups + R32 +
  knockout structure.
- `desk/desk/sports/football/outright_model.py`: replace stub with the MC
  sim per §4. 10,000 baseline sims, deterministic seed.
- Bootstrap CI per §4.4 — 100 samples × 1k sims, perturbed Elo. Per-team
  lower/upper bounds.
- Abstain rules per §4.5.

**Acceptance.** Deterministic at seed=42 (two runs produce identical
output). `P(win)` sums to 1.0 ± 1e-4 across the field. Sanity-check
top-5 by `P(win)` matches a frozen test fixture (the prototype's output is
the reference: Argentina ≥ 15%, France/Spain in the top 5). A frozen WC 2022
retrospective (run the sim with 2022 Elo + 2022 schedule) puts Argentina
in [0.10, 0.25] — closing market was ~0.11.

### PR O3 — outright explainer + dashboard surface

- `desk/desk/explainer/...`: outright copy templates per §3 stage 6.
- Voice tests (banned-phrase suite + no "the favourites" / "the dark horse"
  framings + the `model rates / model gives` longshot rule).
- Backtest dashboard extension: an outright section showing the field
  ladder, model vs market, Picks highlighted (per the prototype's output
  format).

**Acceptance.** A Pick / Pass verdict has voice-checked copy. The dashboard
renders the outright ladder. The route `/desk/outrights/wc26` (or whatever
the integration repo chooses) serves the latest `OutrightOutput` from
`event_contents`.

## 9. Open questions

- **Contract shape — `verdict_participants[]` or reuse?** See §7. ADR
  needed; my recommendation is reuse v1, add the field once the website's
  outright UX is designed.
- **In-tournament re-conditioning.** Once the tournament starts, real
  results collapse the bracket. v1 keeps the sim pre-tournament-frozen
  (or nightly-refresh with results-as-givens); live mid-match conditioning
  is a v1.1 follow-up. Is nightly-refresh acceptable for the WC launch
  window? Default: yes.
- **Sim count (`SIMS = 10_000`) and bootstrap budget.** 10k is the
  prototype's target. Tunable per profiling; the data layer's late-binding
  cadence absorbs the cost.
- **Outright Pick rate target.** Match Picks target 5–20% per the
  optimization spec. Outrights are a 96-position field; many edges will be
  small. Expected v1 Pick rate per tournament: 0–5 Picks (where "Pick" is a
  single position clearing the lower-bound gate). Confirm this is the
  product expectation.

## 10. References

- `THE_DESK_POSITION_WAIST_SPEC.md` v0.2 — the spine; outrights feed its
  generic `PositionSet`.
- `THE_DESK_DATA_LAYER_SPEC.md` v0.5 — Phase 1b is the live-Elo dependency;
  §3.3 is the team registry (inbound resolution closes the field's identity
  problem).
- `THE_DESK_OPTIMIZATION_SPEC.md` — Phase A bootstrap CI; the lower-bound
  Pick gate from A.3 applies on outrights too.
- `THE_DESK_SPEC.md` — parent architecture; §9 failure-isolation rules
  apply unchanged.
- `desk_prototype.py` + `desk_prototype_output.txt` — reference for what
  shape of outright numbers to expect. Not a build target.
- Predecessors (this spec supersedes both):
  - `THE_DESK_OUTRIGHTS_SPEC.md` v0.1 (prophet folder, 2026-05-11) — right
    model approach, wrong on architecture (predates the waist).
  - `tasks/research/TASK-311-desk-outrights-plan.md` — right plumbing,
    wrong on the model (market-anchored).
