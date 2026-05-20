**Subject:** Desk hand-off — waist refactor + data layer (v0.4)

---

Hey,

Sending over the spec package for the next desk build. Two new specs (waist
refactor + data layer) plus a short cover doc to orient you, plus the prototype
as a reference attachment.

**TL;DR — two independent workstreams either of us can start in parallel:**

- **Position-waist refactor** — generalises verdict / explain / publish to a
  flat list of positions, so the engine stops being structurally match-only.
  Matches stay **byte-identical**; the WC-2022 backtest is the regression gate.
- **Data layer (v0.4)** — sourcing above the model. Five phases:
  Elo → rank + form → weather → injuries → **expert signal** (local journalism
  + ex-player punditry, free-content extraction with paywalled publications
  carried as citations only). Budget ~$19/mo. Three rounds of adversarial
  review folded in.

**Read in this order:**

1. `THE_DESK_HANDOFF.md` — package cover, scope, guardrails (~3 min)
2. `THE_DESK_DATA_LAYER_SPEC.md` v0.4 — the heavier (~20 min)
3. `THE_DESK_POSITION_WAIST_SPEC.md` (~10 min)

Don't re-read the older specs (parent build, optimisation, how-the-model-works)
unless the new ones flag them — they're unchanged.

**Non-negotiables** (all in the hand-off doc):

1. Phase 1 only may affect live verdicts immediately.
2. Phases 2–4 run in **Shadow** (collect + log, no verdict impact) until
   forward-validation passes.
3. Missing critical features widen confidence or force Pass per the §3.6
   criticality table — never a silent confident Pick.
4. Vendor terms (API-Football, OpenWeather, Railway) **verified against current
   docs** before code.
5. **No JSON contract changes without an ADR + my sign-off.**

Plus: matches stay byte-identical through the waist refactor. Plus, for
Phase 5: extraction is free-content only; paywalled publications are citation
targets, never scrape targets — a legal/attribution review is a gate before it
goes Live.

**Out of scope here** (so you don't pre-empt me):

- Outright / winner-market support — I'm writing that spec next, sits on top
  of the waist.
- Model-hook *designs* — separate model docs, named per phase in the data
  layer spec but specced separately.
- Contract changes — ADR'd separately.

**Open items I'm closing this week**, before you need them:

- Outright / winner-model spec.
- Output-contract ADRs (citation visibility, outright JSON shape).
- Vendor verifications (API-Football coverage + cap, Railway persistent
  volume, OpenWeather One Call endpoint + pricing).
- Phase 5 legal / attribution review.

**Reference attachment** — `desk_prototype.py` + `desk_prototype_output.txt`.
A throwaway script that uses static Elo + the existing pairwise model to
produce a WC 2026 outright table. Directionally useful for what shape of
calls to expect — **not a build target**. Magnitudes carry every weakness the
new specs are designed to fix.

You can start the waist refactor and Phase 1 of the data layer in parallel —
neither blocks on my open items. Phases 2+ wait on the guardrail-4
verifications; I'll have those done before you get there.

Ping me when you've read through. Happy to walk through anything.

the operator

---

**Attachments**

- `THE_DESK_HANDOFF.md`
- `THE_DESK_DATA_LAYER_SPEC.md` (v0.4)
- `THE_DESK_POSITION_WAIST_SPEC.md`
- `desk_prototype.py`
- `desk_prototype_output.txt`
