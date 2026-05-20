# The Desk — Position-Waist Refactor

**Status:** v0.2 build spec, 2026-05-18. Incorporates Faktor's engineering review — event-context fields added to `PositionSet`; PR 1 acceptance wording corrected.
**Target consumer:** Claude Code (agentic CLI).
**Owner:** Adi (desk dev).
**Scope:** internal refactor only — no behaviour change, no new market shapes.
**Predecessor doc:** `docs/how-the-desk-model-works.md` (the 7-stage pipeline this refactors).

---

## 0. Why

The desk pipeline is built around one shape: a football match — two teams, a
3-way market. The types hard-code that shape: `Side = Literal["a","draw","b"]`,
`ModelOutput(p_a, p_draw, p_b)`, a `MarketSnapshot` of `a`/`draw`/`b`
`VenuePrice`s. The verdict, explainer, and publish stages — which the original
spec promised would be *sport- and shape-agnostic* — all depend on those
football-shaped types. So they aren't actually agnostic.

This refactor introduces the **narrow waist**: a generic `PositionSet` that the
verdict / explain / publish stages speak instead of the football types.
Everything *above* the waist (ingest → features → model) stays
football-match-specific and is barely touched. Everything *below* the waist
becomes genuinely generic.

This is the **prerequisite** for winner markets and other sports. It is *only*
the refactor — no winner ingest, no winner model, no behaviour change. The hard
acceptance bar: **every match produces byte-identical output before and after.**

## 1. The waist — `Position` and `PositionSet`

A **position** is one binary thing you can buy: it pays out or it doesn't. A
football match feeds the waist 3 positions (the `a` / `draw` / `b` sides). A
winner market will later feed it ~2N positions (a YES and a NO per team) — that
is out of scope here; the type just has to *admit* it.

Define in a sport-agnostic module (`desk/desk/positions.py`, or alongside
`FixtureRef` in `desk/desk/sport.py` — implementer's call):

```python
@dataclass(frozen=True)
class Position:
    key:           str           # stable within the set, e.g. "a" / "draw" / "b"
    label:         str           # becomes verdict.side — team name or "draw"
    model_p:       float         # model's INDEPENDENT probability this pays out, [0,1]
    model_p_lower: float         # bootstrap 5th percentile
    model_p_upper: float         # bootstrap 95th percentile
    market_price:  float         # price to buy this position, [0,1]
    market_venue:  str           # "polymarket" / "kalshi"
    market_url:    str | None    # per-position deep link for the Pick CTA

@dataclass(frozen=True)
class PositionSet:
    event_id:          str
    asof:              datetime
    positions:         tuple[Position, ...]
    competition_label: str                 # e.g. "FIFA World Cup 2026" — consumed by the copy builder
    competition_stage: str | None = None   # e.g. "group_d" — consumed when meaningful
    market_url:        str | None = None   # set-level deep link; used on Pass/Avoid verdicts
    abstain_reason:    str | None = None   # sport layer says "don't trust me" → verdict step Passes
```

`competition_label` and `competition_stage` exist because the copy builder
needs them. Without them on the `PositionSet`, the copy builder leaks back into
`FixtureRef` (which §6 forbids) or silently loses competition context in
published copy. Adding them keeps the waist self-contained without touching the
published JSON contract.

Three invariants the rest of the engine relies on:

- **`model_p` is independent.** It is the model's own probability that the
  position pays out, produced *without ever reading market prices*. The verdict
  step's entire meaning is "model vs market" — a model that has read the market
  produces a meaningless edge. Every future model (winner, tennis) consumes this
  contract.
- **`market_price` is read directly** from the position's own market — never
  derived as `1 − something`. (Matters for NO positions later: the YES/NO spread
  is real money.)
- **`abstain_reason`** is how the sport layer says "don't trust me on this set."
  Non-None → the verdict step returns Pass. This is where football's stub-Elo and
  incomplete-market gates move to (see §2, Stage 5).

## 2. What changes, stage by stage

Stages refer to `docs/how-the-desk-model-works.md` §1.

### Stages 1–3 (anon read, adapter, features) — UNCHANGED

The Supabase read, `supabase_fixtures.py`, and `features_builder.py` are
untouched. They still produce `FixtureRef`, `MarketSnapshot`, `FootballFeatures`.

### Stage 4 (model) — UNCHANGED

`model.py` and `ModelOutput` are **not modified.** The football match model —
Elo, the host/home/altitude bonuses, the bootstrap band, `_probs_from_elos` —
stays exactly as it is, with its existing tests. `ModelOutput`, `Side`,
`MarketSnapshot`, `VenuePrice` are hereby understood as *football-match-internal*
types, not pipeline types. Keeping the tested maths frozen keeps the blast radius
small.

### Stage 4.5 (NEW) — `build_position_set` in the football package

A new converter, football-specific (it knows `a`/`draw`/`b` map to team names):

```python
def build_position_set(
    fixture: FixtureRef,
    model_output: ModelOutput,
    snapshot: MarketSnapshot,
) -> PositionSet: ...
```

It:
- emits exactly 3 `Position`s in order **`[a, draw, b]`** (order matters — §3);
- `label` = `team_a` / `"draw"` / `team_b`;
- `model_p` / `model_p_lower` / `model_p_upper` from `ModelOutput`;
- `market_price` / `market_venue` from `snapshot.best_for(side)` (unchanged
  "lowest implied across venues" rule);
- `market_url` (per-position and set-level) = the fixture's Polymarket event URL,
  same for all 3 — exactly as `_market_url_for_fixture` resolves it today;
- `competition_label` / `competition_stage` copied directly from the
  `FixtureRef` — populated for every set so the copy builder never reaches
  back into `FixtureRef`;
- sets `abstain_reason = "stub_elo"` when either team's `elo_source == "stub"`;
- sets `abstain_reason = "incomplete_market"` when any side has no `best_for`.

This is the seam a `Sport` protocol method will eventually expose. For this
refactor it is a direct call — football is the only sport — and the protocol
change is deferred to sport #2.

### Stage 5 (decide) — REWRITTEN, behaviour preserved

`decide.py` is rewritten to `decide(positions: PositionSet, thresholds=None) ->
Verdict`. It no longer imports `Side`, `MarketSnapshot`, or `VenuePrice` from
`desk/verdict/compare.py` — those football types stay football-internal. Gate
order — must reproduce today's effect exactly:

1. **Abstain** — `if positions.abstain_reason: return Pass(market_url=positions.market_url)`.
   Replaces *both* the stub-Elo gate and the market-coverage gate (both now
   expressed as `abstain_reason`, set in `build_position_set`).
2. **Liquidity** — if any position's `market_price ≤ 0.02` or `≥ 0.98` →
   `Pass(market_url=positions.market_url)`. Same rule as `liquidity.py` today,
   now iterating the position list. (Whole-set Pass — byte-identical to today. A
   per-position version is a winner-spec concern; out of scope, flagged.)
3. **Edges** — `edge_pp = (model_p − market_price) × 100` per position.
4. **Pick** — candidates = positions where
   `(model_p_lower − market_price) × 100 ≥ pick_pp`. Among candidates, the one
   with the highest point-estimate `edge_pp` wins (`max` returns first on ties —
   hence the `[a, draw, b]` order requirement). If the winning position's
   `market_url` is None → `return Pass()` **with no market_url** (preserve this
   exact asymmetry — see §3).
5. **Avoid** — if every position's `edge_pp ≤ avoid_pp` → Avoid, `edge_pp` set to
   the most-negative position's edge.
6. else → `Pass(market_url=positions.market_url)`.

`Verdict` is **unchanged** — same fields, same rounding (`round(edge_pp, 2)`,
`round(model_p, 4)`), `_to_american_odds` unchanged, `verdict.side =
winning_position.label`, `market_venue` / `price` / `model_p` / `market_p` all
from the winning `Position`.

### Stage 6 (explain) — interface generalized

`build_copy` takes `(PositionSet, Verdict)` instead of the loose football dict.
The football templated-copy builder reconstructs its current context (team_a /
team_b, per-side `model_p` / `market_p`, plus `competition_label` and
`competition_stage`) **entirely from the `PositionSet` — never reaching back
into `FixtureRef`**. Output `Copy` must be **byte-identical** for matches. The
explainer stays template-driven; the Haiku swap (TASK-276) is unrelated and
untouched.

### Stage 7 (publish) — UNCHANGED

`_build_publish_payload` consumes the (unchanged) `Verdict` + `Copy` +
`FixtureRef`. No change.

## 3. The byte-identical contract

The single hard requirement: for every match event, the `DeskContentPublish`
payload is **byte-identical before and after.** Checklist that makes this hold:

- positions emitted in `[a, draw, b]` order → `max()` tie-breaking unchanged;
- gate order preserved: abstain → liquidity → edges → Pick → Avoid → Pass;
- all rounding preserved (`edge_pp` 2dp, `model_p` / `market_p` 4dp);
- `_to_american_odds`, the `best_for` venue selection, and `market_url`
  resolution all unchanged;
- stub-Elo and incomplete-market still force Pass — just via `abstain_reason`;
- the **"Pick with no `market_url`" branch returns Pass with no `market_url`** —
  every other Pass/Avoid carries `positions.market_url`. Preserve that asymmetry
  exactly (it is in `decide.py` today).

**Regression gate:** `desk backtest --tournament wc-2022` output
(`desk_backtest.xlsx` + dashboard) must be **diff-clean** against a pre-refactor
run. Plus every existing `decide` and `explainer` test ported to the new
signatures and green.

## 4. Out of scope — do not build

- Winner / outright ingest, identity, or model. This refactor is their
  prerequisite, nothing more.
- NO positions on matches. Matches stay at 3 YES-side positions; behaviour
  identical.
- Per-position liquidity (vs whole-set Pass). Winner-spec concern.
- `Sport` protocol changes. `build_position_set` is a direct call until sport #2.
- Any change to `model.py`, `features_builder.py`, `supabase_fixtures.py`.
- Devig. A 3-way match's overround is negligible and is not devigged today —
  keep it that way. (Winner markets will need a per-binary-market devig — out of
  scope.)
- The Haiku explainer swap (TASK-276).

## 5. PR plan

Each PR ships green tests and merges in a working state. Branch per the repo's
normal flow.

### PR 1 — the waist + decide rewrite

- New sport-agnostic module for `Position` / `PositionSet`.
- `build_position_set` in the football package (Stage 4.5).
- Rewrite `decide.py` to consume `PositionSet`; move stub-Elo + market-coverage
  into `build_position_set` as `abstain_reason`.
- Wire the orchestration (`process_event.py`, and `FootballSport.decide_and_explain`
  if still used) to: adapter → features → model → `build_position_set` →
  `decide(position_set)` → … .

**Acceptance.** WC-2022 backtest byte-identical. All `decide` tests ported and
green. `decide.py` no longer imports from `desk/verdict/compare.py` (`Side`,
`MarketSnapshot`, `VenuePrice`) — those types stay football-internal.
*(v0.1 listed `ModelOutput` in this set; corrected per Faktor's review —
`decide.py` never imported `ModelOutput` directly, it takes a `Mapping`
parameter.)*

### PR 2 — explainer interface + cleanup

- `build_copy` takes `(PositionSet, Verdict)`; football copy builder reconstructs
  its context.
- Demote the `Side` / `ModelOutput` / `MarketSnapshot` / `VenuePrice` docstrings
  to "football-match internal."
- Update `docs/how-the-desk-model-works.md`: the waist, the new Stage 4.5, and
  the `model_p` independence invariant.

**Acceptance.** Match `Copy` byte-identical. Backtest still diff-clean.

## 6. Notes for the implementer

- The waist is deliberately a **flat list of binary positions**, not "a market
  with N sides." That is exactly what lets a 3-position match and a ~96-position
  winner market run the *identical* verdict step later.
- Everything the verdict step needs must be **on the `Position`**. If you find
  `decide.py` reaching back into `FixtureRef`, `ModelOutput`, or `MarketSnapshot`,
  the waist is leaking — stop and put the field on `Position` / `PositionSet`.
- `model_p` independence is not optional. It is the load-bearing invariant of
  the whole engine; the verdict step is meaningless without it.

## 7. References

- `docs/how-the-desk-model-works.md` — the 7-stage pipeline, the types, the gate
  logic this refactor preserves.
- `THE_DESK_SPEC.md` §3 — the original "verdict/explain/publish are
  sport-agnostic" promise this refactor finally makes true.
- `tasks/research/TASK-311-desk-outrights-plan.md` — the winner-market proposal
  that sits on top of this waist (and should be re-cut against it: generalize
  the waist, don't build a parallel pipeline).
