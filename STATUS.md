# Overnight status — outright engine pushed forward; 4 phases on staging (plus the other agent's Phase B.1)

**As of 2026-05-27 23:20 local.** All four of my committed phases are
pushed to `origin/staging`. The parallel Phase B.1 agent also shipped
their form-residual hook + API-Football data path tonight (`fad936e`),
landing between my third and fourth phase. Production branch
(`init/project-setup`) untouched — your eyeball gate.

## What shipped overnight

| # | Commit | Tests | What changed |
|---|---|---|---|
| 1 | `38460f9` | +13 (578 total) | **Hard-signals → outright sim.** News-signals subsystem (RSS → Haiku) now nudges per-team Elo in the WC26 MC sim. Bounded -8 per injury / -6 per suspension; capped -30 per team. Alias-aware matching (`United States` ↔ `USA`, `South Korea` ↔ `Korea Republic`). Audit surfaced as `model.hard_signal_adjustments` on the published JSON. **Bonus**: fixed a latent ISO3→ISO2 alias gap in `desk/sports/football/signals_glue.py` that was silently dropping `country:de` for Germany, `country:hr` for Croatia, `country:sa` for Saudi Arabia, etc. — **affects matches too**, not just outrights. |
| 2 | `7174cf2` | +12 (590 total) | **WC22 outright backtest harness.** `python -m desk.outrights.backtest` replays the engine against frozen 2022 inputs (8 groups → R16, 32 teams, 2022-11-20 Elo). Scores against Argentina (the actual winner): Brier, log score, rank-of-winner, top-N hit. Self-contained HTML dashboard. Also generalises `model.py` to take a `TournamentStructure` (no parallel sim implementations). |
| 3 | `d4a4d7c` | +2 (640 total) | **FIFA cross-group bracket for WC26.** Replaces the placeholder seeded R32 with FIFA's actual published bracket (Wikipedia: "2026 FIFA World Cup knockout stage", Match 73–88). New slot grammar `3RD@{groups}` for constrained third-place slots, resolved by greedy constraint-respecting assignment. Approximation of FIFA's 495-scenario Annex C table; sub-pp impact on top teams. |
| 4 | `e26762a` | +7 (647 total) | **Three-stage knockout resolution.** Old model gave the favourite their full Elo advantage on every drawn KO tie — too tilted. New model: 90' (full Elo) → extra time (favourite-weighted, 50% of post-90 draws) → pens (flat ±10pp cap with 0.00025/Elo tilt). Matches empirical pens behaviour (close to coin flip with mild skill effect). Constants tunable in `model.py`. |

## Live engine output on the WC26 sim — top 10 today

| # | Team | P(win) | vs pre-overnight |
|---|---|---|---|
| 1 | Argentina | **18.1%** | was 14.8% (was #2) |
| 2 | France | 15.9% | was 13.3% (was #4) |
| 3 | Spain | 12.7% | was 15.4% (was #1) |
| 4 | Brazil | 9.2% | was 14.0% (was #3) |
| 5 | Germany | 8.0% | was 7.8% |
| 6 | England | 7.6% | was 6.3% |
| 7 | Portugal | 5.2% | was 4.7% |
| 8 | Netherlands | 4.8% | was 4.0% |

The major re-ranking is driven by the FIFA bracket (Phase 3) — Argentina
and Spain were on the wrong sides of the placeholder bracket. Pens
refinement (Phase 4) trimmed top-favourite mass by 1-3pp each, pushing
some probability into the tail.

## WC22 backtest headline

```
sims              5,000 (defaults; 10,000 = production)
true winner       Argentina
model rank        #2     (top-3 hit ✓)
model P(winner)   18.4%  (after pens refinement; was 20.9%)
Brier             0.7645  (model)
                  0.8804  (market consensus reference)
                  0.9688  (uniform 1/32)
log score         1.691   (model)
```

The engine beats the market reference and the uniform baseline. The
absolute Brier is high on a 32-team field with one realised outcome
— Brier on winner-take-all has a floor of ~0.97 for uniform. **The
informative read is the rank-of-winner and the delta vs reference**,
not the absolute number.

## What's outstanding (deferred with reasons)

These were on the punch-list but **not done overnight**:

- **Waist integration** (refactor outrights through the generic
  `PositionSet` / `decide()` waist). Biggest refactor on the list and
  directly overlaps with the parallel Phase B.1 agent's work in
  `desk/sports/football/`. Shipping in parallel would almost guarantee
  a painful merge. Defer until their PR lands.
- **OutrightRef + Supabase adapter.** N/A for this repo — local Prophet
  hits Polymarket gamma directly. This is integration-repo work.
- **Kalshi outright ingest.** No Kalshi WC26 event identified; new
  `Source` registration is a multi-PR effort with auth + discovery.
- **More outright markets** (UCL, EPL, golden boot). Needs market
  discovery and product input on which to prioritise.
- **In-tournament re-conditioning.** Tournament hasn't started — nothing
  to condition on. Revisit once live results data lands (Phase 1b spine).
- **Live Elo (Phase 1b).** Owned by the parallel agent. They shipped
  `fad936e desk/B.1: form-residual hook + api-football data path
  (Shadow)` to staging tonight — Shadow-mode behind
  `DESK_FORM_RANK_RESIDUAL=0` by default. Their changes touch
  `desk/cli.py`, `config.py`, `sports/football/model.py`, `runner.py`,
  `features_builder.py`, `sport.py`, `verdict/forward_validation.py`,
  `desk/data/` (new dir for api_football + openweathermap clients),
  `desk_refresh_loop.py`, `frontend/src/desk/ops/util.js`, and
  `.env.example`. **Not touched by me.** Read their commit message
  for the activation plan.

## Things to verify in the morning

1. **Eyeball the staging URL** — confirm the outright page at `/o/fb-wc26-winner`
   still renders. The publisher contract is unchanged; the new
   `model.hard_signal_adjustments` field is additive.
2. **Run the backtest yourself**: `cd desk && PYTHONPATH=. python -m
   desk.outrights.backtest`. Argentina should land in the top 3.
3. **Run the live outright pipeline locally** to confirm the new bracket
   + pens model produces Argentina ~18% (your top contender). Then merge
   `staging` → `init/project-setup` when happy.
4. **The German/Croatian/Saudi country-tag fix in Phase 1 also affects
   the match path.** Worth eyeballing the next post-deploy match tick to
   see if citations / hard-signal adjustments appear for those nations
   for the first time.

## Files touched (only mine — other agent's work untouched)

```
desk/desk/outrights/hard_signals.py          NEW
desk/desk/outrights/signals_glue.py          NEW
desk/desk/outrights/backtest/__init__.py     NEW
desk/desk/outrights/backtest/__main__.py     NEW
desk/desk/outrights/backtest/wc22_data.py    NEW
desk/desk/outrights/backtest/scoring.py      NEW
desk/desk/outrights/backtest/runner.py       NEW
desk/desk/outrights/backtest/writers.py      NEW
desk/tests/test_outrights_signals.py         NEW
desk/tests/test_outrights_backtest.py        NEW
desk/tests/test_outrights_knockout.py        NEW
desk/desk/outrights/model.py                 EDITED (structure refactor + 3-stage KO + assign_constrained_thirds)
desk/desk/outrights/run.py                   EDITED (wire SignalsRuntime in)
desk/desk/outrights/publish.py               EDITED (surface hard_signal_adjustments)
desk/desk/outrights/wc26_data.py             EDITED (FIFA bracket + wc26_structure())
desk/desk/sports/football/signals_glue.py    EDITED (ISO3→ISO2 alias gap fix)
```

## Why I didn't do "all" of them

You asked to "do them all". I scoped down to four phases that were
defensibly shippable overnight on staging without breaking production
or stomping the parallel Phase B.1 agent's in-flight work. The
deferred items have clear reasons above — most are multi-day efforts
that need either external integrations, product decisions, or the
parallel agent's PR to land first. Happy to pick up any of them next
session.

— Claude
