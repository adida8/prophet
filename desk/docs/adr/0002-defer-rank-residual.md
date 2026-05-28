# ADR 0002 — Defer `rank_residual` from Phase B.1

- Date: 2026-05-28
- Status: Accepted
- Driver: Phase B.1 ship readiness (data-layer Phase 2 coupled unit)
- Authority: `THE_DESK_OPTIMIZATION_SPEC.md` §4.B.1; `THE_DESK_DATA_LAYER_SPEC.md` §3.6

## Context

`THE_DESK_OPTIMIZATION_SPEC.md` §4.B.1 defines the Phase B.1 model
hook as a form / FIFA-rank residual on the Elo prior:

```
elo_a_adj += FORM_WEIGHT * form_delta(team_a) \
           + RANK_WEIGHT * rank_residual(team_a, team_b)
```

`rank_residual` is intended to capture the gap between Elo-implied
rank and FIFA's published World Ranking — "information the market
sees that Elo misses (recent regression-to-mean, qualification
context)."

The data-layer spec §3.6 splits "rank" into four explicit fields so
they're never collapsed into one comparable number:
`fifa_rank`, `league_table_position`, `league_points_per_match`,
`competition_stage_rank`.

For Phase 2 (WC26 national sides) the only relevant field is
`fifa_rank` — internationals don't have league standings.

## Decision

Phase B.1 ships **form_delta only**. `rank_residual` stays absent
(`None`) on every `FootballFeatures` row, the model hook treats absent
as zero contribution per spec §3.6 (no penalty for absent), and no
data layer code is wired to populate it.

## Why

Three reasons.

**1. api-football's standard `/teams` endpoint doesn't expose FIFA
World Ranking.** Their `/teams?search=...` payload includes name,
country, founded year, venue, and `national: true|false` — no rank
field. There's no FIFA-rank endpoint in the Pro plan we currently
hold. Buying a separate FIFA-rank source (or a paid api-sports add-on
if/when one exists) is a vendor decision that costs more money + more
verification effort and shouldn't block form from shipping.

**2. form is the bigger lever.** The spec's initial estimates are
`FORM_WEIGHT ≈ 20` Elo per point of form-delta vs `RANK_WEIGHT ≈ 10`
Elo per rank-residual position. Form alone covers the dominant share
of B.1's expected Brier improvement.

**3. The hook's math is already rank-aware.** `_adjusted_elos` adds
`RANK_WEIGHT * rank_residual` only when the value is non-None. Once
we land a FIFA-rank source the math turns on automatically — no model
refactor required.

## Consequences

- B.1 ships with one of two hook terms wired; the other is dead-but-
  ready. CLAUDE.md flags this in the Phase B.1 status line so future
  sessions don't re-discover it.
- The Phase 2 coupled-unit forward-validation report compares
  *form-only-with vs form-off* Brier; if form alone clears §1.4, B.1
  graduates Shadow → Live without rank. If form alone *doesn't* clear,
  rank becomes the next experiment (and unblocks an explicit
  cost/benefit decision on the rank source).
- The `team_*_rank_residual` field stays on `FootballFeatures` (no
  schema churn) so adding rank later is a pure data-layer change.

## Unblocks

To revisit, two paths:

- **a)** A FIFA-rank-publishing source enters the data layer.
  Candidates: fifa.com scraped (no API; brittle), a paid api-sports
  add-on, or a competing API (footballdata.org publishes FIFA rank
  monthly).
- **b)** Phase B.1's form-only forward-validation report shows form
  alone doesn't clear §1.4's Brier-no-regression gate. That triggers
  this ADR's revisit.

Either path is a separate PR; this ADR doesn't pre-decide which.

## Status of related code

- `desk/desk/sports/football/model.py` — `RANK_WEIGHT` constant
  stays. `FootballFeatures.team_*_rank_residual` stays.
- `desk/desk/sports/football/features_builder.py` — `_FormSource`
  protocol exists; an analogous `_RankSource` will be added when (a)
  lands.
- `desk/desk/data/api_football/` — no `rank.py` module exists.
- Tests cover form path; rank path has no tests (would be dead code).
