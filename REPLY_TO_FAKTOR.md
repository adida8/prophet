**Subject:** Re: Desk hand-off — answers in, you're unblocked

---

Thanks for the review — sharp catches across the board, every item taken.
Specs updated; all five points answered below in your numbering. The branch
`docs/desk-handoff-specs` now carries everything.

**§1 — predecessor docs (BLOCKING).** Done.

- `docs/how-the-desk-model-works.md` — committed.
- `tasks/research/THE_DESK_SPEC.md` — committed.
- `tasks/research/THE_DESK_OPTIMIZATION_SPEC.md` — committed. (The file never
  actually existed; I consolidated the trustability brief + STATUS.md + the
  merged `feat/desk-phaseA*` branches into one canonical roadmap. Phase A is
  retrospective; Phase B is now the model-side counterpart to data-layer
  Phases 2–4 — answers your §5.)
- `tasks/research/TASK-311-desk-outrights-plan.md` — committed.

Plus the new specs (handoff / waist v0.2 / data-layer v0.5 / outrights v0.2)
all in `tasks/research/`. Prototype + output in
`tasks/research/prototypes/`. Per your aside — agreed, `tasks/research/` is
the right home, not Downloads.

**§2 — `PositionSet` event context.** Ack. Waist spec **v0.2** adds
`competition_label: str` and `competition_stage: str | None` to `PositionSet`.
`build_position_set` copies them from `FixtureRef`; Stage 6 reads them off
`PositionSet`, never reaches back into `FixtureRef`. No contract change.

Also corrected the PR 1 acceptance wording — you're right, `decide.py` doesn't
import `ModelOutput` directly; the real coupling is to `desk/verdict/compare.py`.
Updated to name the real types (`Side` / `MarketSnapshot` / `VenuePrice`).

**§3 — Phase 1 split.** Ack. Data layer **v0.5** splits Phase 1 into:

- **1a — Foundation skeleton.** Keyed `Source` / `Datum` / `Citation` /
  registry, resolution-vs-assembly split, canonical team registry (both
  directions — see §4), pre-flight coverage gate, cache + freshness +
  cold-start posture, shared rate limiter, sanity gates, provenance
  scaffolding, **and the forward-validation harness** (your "net-new
  infrastructure, not just process" catch — well-flagged; folded in).
  Behaviour-neutral; WC-2022 backtest byte-identical to pre-1a.
- **1b — Elo wired through 1a.** Live national + club Elo, parser hardening,
  `_club_id_from_match_id` returns real ids.

Your two smaller flags also folded in:
- `Source.fetch` now declared async (matches the existing seam — was drift
  in v0.4).
- Secrets now reads `OPENWEATHERMAP_API_KEY` (the existing repo name).

**§4 — identity, inbound direction.** Ack — important catch. §3.3 now
*explicitly* owns both directions:

- **Inbound (slug → canonical)** — the half that closes the prototype's
  "26 unmapped" dead zone, includes `_club_id_from_match_id`.
- **Outbound (canonical → per-source alias)** — what was already specced.

A key that can't resolve in either direction marks the datum absent with
reason `unresolved_alias`. Phase 1a builds this; Phase 1b depends on it.

**§5 — Phase 2 model-hook owner.** Answered by the new optimization spec
(`tasks/research/THE_DESK_OPTIMIZATION_SPEC.md`). **§4 Phase B.1** of that
spec is the form / FIFA-rank residual hook design — the model-side
counterpart to data-layer Phase 2. The optimization spec defers Phase B's
*data side* to the data-layer spec (no duplication) and owns only the
*model side*. So: I just wrote it. The Phase 2 data PR and the Phase B.1
hook PR ship coupled per the calibration-gate rule.

Forward-validation harness: scoped into Phase 1a (per §3 above), so it's
built before any phase needs it.

**Sequencing — waist first, then 1a/b.** Ack. The
`abstain_reason = "stub_elo"` seam is the coupling you identified; waist
freezes that interface first, then 1a/1b narrow the trigger cleanly.

---

**My other open items — closed today as well, no longer on the critical path:**

- **Outright / winner-model spec** — landed, `tasks/research/THE_DESK_OUTRIGHTS_SPEC.md`
  v0.2. Sits on the waist + data-layer Phase 1b. Supersedes both the prophet
  v0.1 spec and TASK-311. Independent Monte Carlo model (never reads the
  market); YES + NO are first-class positions on the waist's position-list;
  the previous Avoid-rule structural problem dissolves naturally on this
  market shape. Not blocking your PRs.
- **Vendor verifications (guardrail 4)** — landed,
  `tasks/research/VENDOR_VERIFICATIONS.md`. API-Football, OpenWeather One Call
  3.0, Railway persistent volumes all verified against current vendor docs.
  All-in ~$19–20/month, within the ceiling. Three setup steps on me before
  Phase 1b (subscribe to API-Football + OpenWeather, **set the OpenWeather
  daily cap explicitly** — the default 2,000/day is too permissive against our
  $1/mo overage budget — confirm Railway plan tier supports volumes).
- **Phase 5 legal / attribution review brief** — landed,
  `tasks/research/PHASE_5_LEGAL_REVIEW_BRIEF.md`. Prep doc to hand a media/IP
  lawyer. I'll schedule the review for ~6 weeks before Phase 5 target Live —
  i.e. months out, after Phases 1–4 stabilise. Phase 5 can build in Shadow
  ahead of it.
- **Output-contract ADRs** — outright spec §7 flags one (whether to add an
  additive `verdict_participants[]` field for the outright B2C ladder).
  Recommendation: reuse the existing wire in v1, ADR the field once the
  website's outright UX is designed. Your call.

---

**What you can start on, today:**

- Waist PR1 — the `how-the-desk-model-works.md` doc you needed is in `docs/`
  on the branch above, and the `PositionSet` context slot is acked in v0.2.
- Data-layer Phase 1a — pure foundation work; needs none of my vendor
  verifications (those are 1b territory).

Phase 1b and beyond wait on me completing the three vendor setup steps from
the verification doc; that timing holds well before 1a completes.

Ping me when you've read v0.5 / v0.2 + the optimization spec. Happy to sync
if anything else surfaces.

Adi
