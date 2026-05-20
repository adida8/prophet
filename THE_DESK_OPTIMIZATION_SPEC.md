# The Desk — Optimization Spec (v1.1 + v1.2 trustability roadmap)

**Status:** v0.1 consolidation, 2026-05-18. Supersedes `THE_DESK_TRUSTABILITY_BRIEF.md` (2026-05-09) as the active roadmap. Reflects Phase A as-built (per `STATUS.md` 2026-05-09) plus a re-scoped Phase B aligned with `THE_DESK_DATA_LAYER_SPEC.md` v0.4.
**Target consumer:** Claude Code (implementation), Adi (decisions), Faktor (Phase B model-hook owner).
**Owner:** Adi.
**Relationship to other specs:**
- `THE_DESK_TRUSTABILITY_BRIEF.md` — *predecessor*; this spec consolidates and updates it.
- `THE_DESK_SPEC.md` — *parent architecture*; unchanged.
- `THE_DESK_DATA_LAYER_SPEC.md` v0.4 — *data side* of Phase B; this spec owns the *model side*.
- `THE_DESK_POSITION_WAIST_SPEC.md` — orthogonal refactor; doesn't intersect with calibration work.
- `STATUS.md` — Phase A as-built status; quoted in §3.

---

## 0. Why this spec exists

The Desk's WC 2022 backtest produced a striking pair of findings:

| Axis | Original result | Reading |
|---|---|---|
| **Calibration** (when we say 70%, does 70% happen?) | 0.581 mean Brier vs 0.579 closing market — within 0.2% across 64 matches | We forecast about as accurately as Pinnacle. The credibility number holds. |
| **Selection** (which fixtures get Picked) | 61/64 Picks → 95% Pick rate | We Pick almost everything. The model lacks information the market already has — Picks are not yet trustworthy. |

Calibration earns the right to publish; selection earns the right to *recommend acting*. The first is real; the second was broken. This spec is the path to fixing selection without weakening calibration, then surpassing the market on calibration too.

### What "trustable" means here (six criteria, unchanged from the brief)

A reader picking up a Pick must be able to:

1. **See why it's a Pick** — drivers attributed to specific features.
2. **See the model's calibration history** — rolling Brier, hit-rate per probability bin.
3. **See what we don't know** — features marked unavailable rather than zero-filled.
4. **See the cited source** — every fact footnoted.
5. **Distinguish model probability from market probability** — verdict prose never collapses the two.
6. **Trust the Pick rate** — when the dashboard says 12 Picks in 100 matches, those 12 are real edges.

## 1. Out of scope

- **Replacing the maths.** The Elo + venue + altitude cascade in `desk/sports/football/model.py` stays. Work is data depth, selection discipline, and model-hook *additions*.
- **A new contract.** `MatchOutput` shape is unchanged. (Outright work goes through the waist refactor.)
- **Real-money flows.** Read-only forever.
- **Non-football sports.** Tennis / basketball stay deferred.
- **Data *collection* design.** That lives in `THE_DESK_DATA_LAYER_SPEC.md`. This spec owns *how the data moves the probability*.

## 2. Status snapshot — what's landed, what's open

| Phase | Status | Effect |
|---|---|---|
| A.1 — Bootstrap CI | **LANDED** (PR #21, `d441c20`) | 90% confidence band around `model_p`; Pick gate uses lower bound |
| A.2 — Band tuning | **LANDED** (`af156ad`) | `ELO_PERTURBATION` 20 → 50; band magnitude is the trustability lever |
| A.3 — Multi-window persistence | **LANDED, no-op pending Phase D** (`58d2545`) | Rule + tests in place; activates when walk-forward harness ships |
| A.4 — Avoid threshold + structural finding | **LANDED** (`4ce1cee`) | `DESK_AVOID_PP` -2.0 → -1.5; Avoid is mathematically impossible on single-venue normalized markets |
| B — Late-binding model hooks (form, weather, injuries, lineup) | **OUTSTANDING** | The biggest Brier lever still on the table |
| C — Data quality | **partly subsumed by data layer spec** | What remains: source-state surfacing, fixture-to-stadium maps |
| D — Backtest expansion + walk-forward harness | **OUTSTANDING** | Activates A.3; ≥ 150 historical matches |
| E — Public track record | **OUTSTANDING** | Live `/track-record` page; immutable Pick log |
| F — Voice + explainer trustworthiness | **OUTSTANDING** | Folds into PR 5's Haiku swap |

WC 2022 backtest after Phase A: **47% Pick rate** (down from 95%), Brier 0.5806 vs 0.5794 market. Pick rate still outside the 5–20% target — that's Phase B's job.

## 3. Phase A — Selection discipline (LANDED — retrospective)

Phase A's thesis: *cut Pick rate by being honest about model uncertainty, not by raising the threshold.* Same `pick_pp = 3.0`, narrower call surface.

### A.1 — Bootstrap confidence band around `model_p`

Implementation: `desk/sports/football/model.py:_confidence_band`. 100 samples per fixture, deterministic seed (MD5 of feature fields), perturbations:

- Elo (each team) ± uniform(`ELO_PERTURBATION`)
- Host bonus ± uniform(`HOST_BONUS_PERTURBATION`)
- Home-ground bonus ± uniform(`HOME_BONUS_PERTURBATION`)
- Altitude rate ± uniform(`ALTITUDE_BONUS_PERTURBATION`)

Bounds are 5th / 95th percentile of the perturbed distribution. Pick gate (`desk/verdict/decide.py`) uses the *lower bound*, not the point estimate:

```
(model_p_lower[side] − market_p[side]) × 100 ≥ pick_pp
```

A model with a wide band on a side fails the gate even when its central estimate looks attractive. **This is the engine being honest about what it doesn't know.**

### A.2 — Band tuning (the magnitude IS the lever)

`ELO_PERTURBATION` was tuned **20 → 50** after the first cut produced a 77% Pick rate on WC 2022 — too aggressive. ±50 reflects realistic Elo uncertainty: a tournament can shift a national side ±30, transfer windows shift clubs ±30, recent form swings ±20–50.

The original spec proposed a *dual-gate* (raw edge ≥ 3pp AND lower-CI edge ≥ 1pp). It was implemented locally (`444a7f7`) but **abandoned** — the same selection discipline falls out of widening the band on a single gate, without adding a new threshold field. The wider band IS the dual gate, expressed cleaner.

### A.3 — Multi-window persistence

`desk/verdict/persistence.py`. Rule: a Pick must persist across at least N windows (default 2: T−5d and T−1h) to fire. Single-window 3pp edges are noise; edges that survive new information are signal.

**Current state:** in place, **no-op on the WC 2022 backtest**. The backtest replays a single closing-market snapshot per match; multi-window persistence has nothing to compare against. It activates with:

1. Phase D's walk-forward harness with per-window market data, *or*
2. PR 6's scheduler in live mode (writes per-snapshot files).

This is the largest known latent improvement — multi-window persistence is expected to drop Pick rate another 5–10pp once it can fire.

### A.4 — Avoid threshold relaxation + structural finding

Two parts:

1. **`DESK_AVOID_PP` relaxed -2.0 → -1.5pp** per the original spec.
2. **Structural finding documented:** Avoid is mathematically impossible on single-venue normalized closing odds. Per-side edges sum to zero (since model probabilities sum to 1 and market probabilities sum to 1+overround), so at least one side always has positive edge. Avoid only fires in multi-venue mode where `sum(best_for(side)) < 1`.

**ADR candidate (v1.2):** redefine Avoid as `max-side edge ≤ avoid_pp` *or* a market-distortion metric, so it can fire on single-venue data. Not in scope for v1.1.

*Note: the original brief's A.4 was a "calibration-aware threshold" — that work is moved to Phase E (it depends on rolling history that doesn't exist yet).*

### Phase A — bottom-line numbers

| Bar | Target (v1.1 acceptance) | Phase A current | Status |
|---|---|---|---|
| Pick rate inside 5–20% | 5–20% | 47% | RED |
| Mean Brier ≤ 0.55, beat market by 0.02 | model − market ≤ −0.02 | tied at +0.0012 | AMBER |
| Calibration error ≤ 5pp every populated bin | — | several bins > 10pp drift on 64-sample set | AMBER |
| Zero stub sources in production | — | unchanged from PR 4.5 | depends on Phase C / data layer |

**Honest read:** Phase A cut the cosmetic problem (Pick rate). The tail-tightness problem requires Phase B's late-binding features. Phase A is the foundation — bands + persistence + a real Avoid rule once multi-venue ships — but the headline numbers come from Phase B.

## 4. Phase B — Late-binding model hooks (OUTSTANDING)

Phase B is where this spec stops being a retrospective and becomes a plan. Each Phase B hook is the **model-side counterpart** to a data layer phase. The data layer collects the data; this spec defines how the model consumes it to move `model_p`.

**Sequencing rule (inherited from the data layer spec):** every Phase B hook ships *coupled* with its data layer phase. The data layer phase stays in Shadow until its paired Phase B hook clears forward-validation — and the hook ships in this spec's PR ladder, not as scattered model-spec docs.

**Calibration gate (per data layer §1.4):** a coupled (data, hook) unit passes when its Brier is no worse than the prior phase + the feature shows sane directional behaviour. Forward-validated, not historically backtested (per data layer §5 — leakage rule).

### B.1 — Form / FIFA-rank residual on the Elo prior (highest leverage)

**Pair with:** data layer Phase 2 (rank + form via API-Football).
**Goal:** Brier 0.5806 → ≤ 0.570 on a forward-validated sample of ≥ 100 fixtures.

**Design.** Add a residual term to adjusted Elo before `_probs_from_elos`:

```python
elo_a_adj += FORM_WEIGHT * form_delta(team_a) \
           + RANK_WEIGHT * rank_residual(team_a, team_b)
# symmetric for elo_b
```

- `form_delta(team)`: weighted last-N results (3-1-0 points, exponential decay over the last 10 matches), normalised so the long-run mean is zero. A team in a hot streak gets a positive delta; a team in a slump, negative.
- `rank_residual(team_a, team_b)`: the *gap* between FIFA / league-table position the model would predict from Elo alone, and what it actually is. Captures information the market sees that Elo misses (recent regression-to-mean, qualification context).

`FORM_WEIGHT` and `RANK_WEIGHT` are tunable constants; backtest tunes them. Initial estimates: `FORM_WEIGHT ≈ 20` Elo per point of weighted form-delta; `RANK_WEIGHT ≈ 10` Elo per rank-residual position.

**Field shape (consumed from data layer Phase 2):** the data layer ships `fifa_rank`, `league_table_position`, `league_points_per_match`, `competition_stage_rank`, `rank_context`. The hook reads only the fields applicable per `rank_context`; absent fields produce zero contribution (no penalty for absent — penalties are §3.6 of the data layer spec).

**Drivers attribution:** when the residual contributes ≥ 15 Elo to either side, the explainer's drivers list adds a line ("Brazil's last-10 form is +1.4 points/match above season norm").

**Acceptance:** forward-validation Brier improves on the Phase A baseline; no new sanity-gate failures; drivers fire on at least 30% of Pick fixtures.

### B.2 — Weather adjustment

**Pair with:** data layer Phase 3 (OpenWeatherMap, late-binding T−5d).
**Goal:** modest Brier lever. Honest about that — the data layer spec already says weather may stay display-only if the model hook doesn't move Brier.

**Design.** A weather adjustment fires only when conditions are *extreme*; mild weather contributes nothing:

- **Heat × altitude interaction:** at venue temperature ≥ 32°C AND altitude ≥ 1500m, apply −20 Elo to the side that's *not* altitude-acclimatised (`is_altitude_acclimatised(iso3)` already in the seed). Reasoning: heat compounds altitude stress; this is where weather has the strongest documented effect.
- **Heavy rain / waterlogged pitch:** at modelled precipitation ≥ 10mm in the match hour, increase `DRAW_PEAK` by 5pp for that fixture's draw-share calculation. Rain compresses skill differentials.
- **Strong wind (≥ 30 km/h):** small effect, possibly draw-tilt. Park as a v1.2 refinement unless backtest demands it.

**Field shape (consumed from data layer Phase 3):** temperature_c, precipitation_mm_per_hour, wind_kmh, all per-fixture at kickoff.

**Gate before going Live:** the data layer spec already requires the hook PR to *demonstrate* on forward-validation that weather moves Brier. If it doesn't, weather stays display-only.

**Acceptance:** forward-validation Brier ≥ Phase B.1's baseline; weather contribution clearly attributed in drivers when ≥ 10 Elo applied.

### B.3 — Injury / availability → Elo penalty

**Pair with:** data layer Phase 4 (API-Football injuries + lineups). Gated by the data layer's pre-Phase-4 source audit.
**Goal:** big lever in principle; in practice constrained by source quality. Critical to get the *importance weighting* right — naïve "missing player count" hurts calibration.

**Design.** For each absent player on a team, compute a player-importance score from the data layer's player-level attributes, then sum to an Elo penalty:

```python
importance = (
    POSITION_WEIGHT[player.position]      # GK 1.5, CB/DM 1.2, FW 1.0, depth 0.4
    × min(player.recent_minutes_share, 1.0)  # 0–1 fraction of available minutes started
    × ROLE_BUMP[player.role]              # captain 1.2, regular starter 1.0, rotation 0.6
)
elo_penalty = INJURY_BASE_PENALTY * importance     # e.g. 60 Elo × importance
```

A missing first-choice keeper = ~90 Elo; missing third-choice fullback = ~3 Elo. The penalty *scales*, which is the whole point — and exactly why the data layer's `recent_minutes_share` + `position` + `role` attributes are non-negotiable.

**Fallback when source audit fails:** if API-Football can't provide player-level attributes for a competition, B.3 ships *disabled* for that competition (data layer ships availability-only, hook stays in Shadow). No proxy modelling — proxies hurt calibration more than they help.

**Confirmed XI overlay (T−1h):** when a lineup arrives, compare against the model's expected XI (derived from `recent_minutes_share`). Surprise omissions trigger an extra penalty on the missing player's importance; surprise inclusions of high-importance rotation players give a small bonus. Bounded to ±15 Elo total to prevent late-binding overreach.

**Acceptance:** the data-layer audit passes; forward-validation Brier improves on B.2's baseline; penalty distribution makes physical sense (no team penalised more than ~150 Elo total, no team unexpectedly *boosted* on a routine injury).

### Phase B sequencing

B.1 → B.2 → B.3 (and B.3's confirmed-XI overlay). Each is its own coupled (data PR, model-hook PR, forward-validation report) trio per the data layer spec. **B.1 first** — biggest Brier lever, no late-binding complexity, and it's the proving loop for the whole "data + hook + calibration" pattern.

## 5. Phase C — Data quality (mostly subsumed by data layer)

The original brief's Phase C had five items. Three migrate cleanly into the data layer spec (live Wikipedia Elo ingest → Phase 1; live ClubElo ingest → Phase 1; source-state surfacing → §6 Operational). Two stay in this spec because they're model-side:

1. **WC 2026 fixture-to-stadium map.** Without it the host bonus rarely fires (only when `team_iso3` matches `venue_country`). With it, every WC fixture knows its stadium + altitude, so the host *and* altitude bonuses activate. One-off data bundle (FIFA published schedule); not a live source.
2. **Club home-ground table expansion.** Currently 11 clubs in `data/club_grounds.py`. Expand to top 5 leagues × top 30 clubs/league. Static data, bundled.

Both are pure-data PRs, no model logic. Sequence them alongside data layer Phase 1.

## 6. Phase D — Backtest expansion + walk-forward harness (OUTSTANDING)

**Goal:** ≥ 150 historical matches in the calibration harness; walk-forward validation; activates A.3 multi-window persistence.

1. **Euro 2024 + Copa 2024.** Already in `desk/backtest/tournaments.py` as commented-out entries. Curate the manual CSVs (51 + 32 = 83 matches). Run the harness across all three tournaments.
2. **EPL 2023/24 + La Liga 2023/24** via football-data.co.uk (free CSVs at `E0.csv`, `SP1.csv`). Wire `historical/markets.py` to read them. ~760 matches across the two leagues.
3. **Walk-forward validation.** Train data through 2022-12-31, test on 2023; advance the cutoff month by month. Catches lookahead bugs that single-tournament backtests can't.
4. **Per-window market data.** A.3 needs multiple price snapshots per match; the walk-forward harness must replay them. This is what activates multi-window persistence.
5. **Calibration trend panel.** Per-tournament Brier strip in the dashboard so you see drift over time.

**Why size matters:** with 800+ matches the confidence interval on mean Brier shrinks below ±0.005 — narrower than the difference vs market. The calibration claim becomes statistically defensible.

**Phase D is the prerequisite for Phase E** (the public track record needs the historical depth) AND for A.3 actually firing in backtests.

## 7. Phase E — Public track record (OUTSTANDING)

**Goal:** a live `/track-record` page showing every Pick the Desk has ever issued, against the actual outcome. Updates automatically.

1. **`/track-record` route** with three sections:
   - **Headline:** rolling-30-day mean Brier vs market's mean Brier on the same matches; rolling-30-day Pick hit rate.
   - **Reliability diagram:** all Picks since launch, binned by stated probability.
   - **Pick log:** every Pick we've ever issued, immutable, dated, with the actual outcome.
2. **Immutability.** Per-snapshot `MatchOutput` files at `data/output/football/{match_id}-{snapshot_at}.json`. PR 6's scheduler writes per-snapshot; this just retains them instead of overwriting.
3. **Auto-refresh.** Page regenerated by the scheduler when a published match's outcome resolves.

**The track-record page IS the credibility story.** Faktor and end-readers don't have to take our word for the Brier number; the page shows every prediction we've ever made.

**Decision deferred (was an open question):** internal-only at v1.1, public at v1.2 — locked. Public surface waits for WC 2026 group stage to finish, so the launch carries real-time live results alongside.

## 8. Phase F — Voice + explainer trustworthiness (folds into PR 5)

These extend PR 5's Haiku swap, not a separate PR:

1. **Cited blurbs.** Every claim has a footnote URL. The Haiku prompt enforces it; a regex post-check rejects blurbs without ≥1 citation per fact-claim.
2. **Probability triplet always shown.** Title/summary/blurb must reference *both* the model's probability and the market's, never one in isolation.
3. **No false certainty.** Extend banned phrases: "will win", "is set to", "destined", "lock", "no-brainer". Soft-language requirement: probabilistic verbs only ("rates", "implies", "favours").
4. **Honest miss surfacing.** When a previously-issued Pick resolves as a miss, the next match for the same team carries a footnote: "Last Pick on this team missed (date)."
5. **Source attribution per driver.** Driver lines cite the data source by name ("Form data via API-Football; weather via OpenWeatherMap").

## 9. v1.1 / v1.2 release contract

**v1.1 ships when, in this order:**

1. **Calibration improves.** WC 2022 backtest mean Brier ≤ 0.55, beating closing market by ≥ 0.025 across 64+ matches.
2. **Selection earns trust.** Pick rate on both backtest and live engine sits in 5–20%; Pick hit rate matches mean Pick probability within ±10pp.
3. **No silent stubs.** Every `Source` reports `last_fetch_at` within its declared cadence; failures surface as footnotes (data layer §6).
4. **Explainer earns trust.** Voice tests pass on 100 samples; every blurb cites ≥ 1 source per fact claim; banned phrases zero.
5. **Backtest covers ≥ 150 matches.**

**v1.2** adds the public track record and the cross-venue Avoid redefinition (per A.4's ADR candidate).

When all five hold, the dashboard's bottom-line card flips from RED to GREEN. Until then, internal-only.

## 10. Open questions

Updated from the brief — several earlier ones are resolved.

| Question | Status |
|---|---|
| Confidence-interval breadth (±50 Elo) | **Resolved.** A.2 tuned 20 → 50; this IS the band magnitude. |
| Dual-gate vs single-gate with wider band | **Resolved.** Single-gate kept; dual-gate abandoned (see §3 A.2). |
| Friendlies in form features | **Still open.** Include / downweight / exclude? Needs answer before B.1 ships. Default leaning: downweight by 0.5. |
| Track-record audience | **Resolved.** Internal v1.1, public v1.2 post-WC group stage. |
| Calibration-aware threshold timing | **Resolved.** Moved to Phase E (needs rolling history); brief's A.4 is renamed. |
| Source-tier weighting per-sport | **Deferred.** Data layer's §3.8 per-competition tier override covers it for v1; full matrix is v2. |
| Avoid redefinition ADR | **Open.** v1.2 candidate per A.4's structural finding. |
| Draw-share function is eyeball-fit (`DRAW_PEAK=0.30`, `DRAW_FLOOR=0.10`, `DRAW_DECAY_PER_ELO=0.0006`) | **Open.** Per `how-the-desk-model-works.md` §10, the curve overstates draws in low-Elo-gap matches and understates in mid-gap. Replace with a function fitted from the Phase D backtest residuals. v1.2 candidate. |
| Confidence band is bootstrap-coarse, not fitted prediction-error variance | **Open.** Bounds today are honest about "Elo could be ±50 off" but not calibrated against actual prediction error. Once Phase D's walk-forward harness produces residuals, fit the perturbation magnitudes from observed error. v1.2 candidate. |

## 11. Sequencing summary

```
LANDED  ──▶ Phase A (selection discipline)
        ──▶ Data layer Phase 1a (skeleton)  [data layer spec]
        ──▶ Position-waist refactor          [waist spec]

NEXT    ──▶ Phase 1b (Elo wired) + Phase C.1/C.2 (stadium / club ground tables)
        ──▶ Phase B.1 = data layer Phase 2 + form/rank residual (coupled)
        ──▶ Phase D (walk-forward harness — activates A.3 in backtest)
        ──▶ Phase B.2 = data layer Phase 3 + weather hook (coupled)
        ──▶ Phase B.3 = data layer Phase 4 + injury hook (coupled, gated by source audit)
        ──▶ Phase F (voice trustworthiness, inside PR 5)
        ──▶ Phase E (public track record — needs Phase D depth)
        ──▶ v1.2: A.4 ADR (Avoid redefinition), Phase 5 expert signal, public track record live
```

Phases A–C land v1.1; D–F land v1.2.

## 12. What this spec does NOT promise

- That The Desk will beat the closing market on Brier in production. We're closing the gap; "beating" is a stretch goal.
- That selection lands at 5%. 5–20% is the target; 8–12% is realistic.
- A schedule. The ordering above is logical, not dated. Each phase is independently shippable.

## 13. References

- `THE_DESK_TRUSTABILITY_BRIEF.md` — predecessor strategic brief.
- `THE_DESK_SPEC.md` — parent architecture (§7 late-binding ladder is the source of the binding windows).
- `THE_DESK_DATA_LAYER_SPEC.md` v0.4 — Phase B's data side.
- `THE_DESK_POSITION_WAIST_SPEC.md` — orthogonal refactor.
- `STATUS.md` — Phase A as-built snapshot (2026-05-09).
- `feat/desk-phaseA1-bootstrap-ci-real`, `feat/desk-phaseA2-multi-window`, `feat/desk-phaseA3-confidence-intervals` — the Phase A branches.
