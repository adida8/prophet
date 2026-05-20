# The Desk — Engineering Hand-Off

**For:** Faktor (engineering)
**From:** Adi (product)
**Date:** 2026-05-15
**Status:** ready to code.

This is the spec package for building the next desk iteration. Read the three
files in §"Read order" below; don't re-read the older specs except as
cross-reference. Two of the three are new this week; the parent spec and the
optimisation spec are unchanged and still authoritative.

## What's in this package

1. **`THE_DESK_HANDOFF.md`** *(this file)* — package overview + scope.
2. **`THE_DESK_POSITION_WAIST_SPEC.md`** *(new — refactor below the model)* —
   generalises verdict / explain / publish to a flat list of positions, so the
   engine stops being structurally match-only. Prerequisite for outright
   support without a parallel pipeline. Matches stay **byte-identical** through
   the refactor — WC-2022 backtest is the regression gate. Two PRs.
3. **`THE_DESK_DATA_LAYER_SPEC.md` v0.4** *(new — sourcing above the model)* —
   source abstraction, fetch-keying, canonical team registry, freshness / cache,
   late-binding ladder, five phases:
   1. Elo (live national + club)
   2. Rank + form (API-Football)
   3. Weather (OpenWeatherMap)
   4. Injuries + lineups (API-Football)
   5. **Expert signal** — local journalism + ex-player punditry (free-content
      extraction + paywalled citations, two-tier: factual corroborates Phase 4,
      editorial cites only; never a direct model input)
   Budget ~$19/month. Three rounds of adversarial review incorporated.

The waist and the data layer are **independent workstreams** — opposite sides
of the model. They can be built in parallel.

## Read order

1. This file (~3 min).
2. `THE_DESK_DATA_LAYER_SPEC.md` — heavier (~20 min).
3. `THE_DESK_POSITION_WAIST_SPEC.md` — lighter (~10 min).

Existing cross-references already in the repo, **do not re-read unless flagged
by the new specs:**
- `docs/how-the-desk-model-works.md` — current 7-stage pipeline.
- `THE_DESK_SPEC.md` — original parent build spec.
- `THE_DESK_OPTIMIZATION_SPEC.md` — Phase A trustability work.

## What's NOT in this package

- **Outright / winner-market support.** Sits on top of the position-waist;
  needs its own spec, which Adi is writing next. Don't pre-empt it from the
  prototype (see below).
- **The model-hook designs** that consume each new data type (form/rank
  residual on top of Elo, weather adjustment, injury → Elo penalty). Named
  *per phase* in the data layer spec, but the **design** of each hook is a
  separate model document. The data layer requires the hooks *land coupled*
  with their phase, but their internals are out of scope here.
- **Published JSON contract changes.** Any new contract field needs an ADR
  + Adi sign-off (data layer §7). The data layer ships with provenance and
  freshness *desk-internal* by default; surfacing them on the website is a
  separate decision.

## Non-negotiables (the five guardrails from data-layer §0)

1. **Phase 1 only** may affect live verdicts immediately.
2. **Phases 2–4 run in Shadow** (collecting data, logging predictions) until
   their paired model hook clears forward-validation per data-layer §5.
3. **Missing critical features widen confidence or force Pass** per the fixed
   criticality table (data-layer §3.6) — never a silent confident Pick.
4. **Vendor terms** (API-Football, OpenWeather, Railway) are **verified against
   current vendor docs before any code is written.** §8 of the data-layer spec
   names the specific verifications.
5. **No published JSON contract changes without an ADR + Adi sign-off.**

Plus the waist's regression gate: **matches stay byte-identical** through the
refactor; the WC-2022 backtest output must diff-clean.

Plus a Phase 5 specific: extraction is **free-content only**; paywalled
publications are **citation targets, never scrape targets**. The registry
rejects "tier-1 paywalled" as a contradiction. A separate legal / attribution
review is a load-bearing gate before Phase 5 goes Live.

## Sanity-check artifact

A prototype lives in the repo root: `desk_prototype.py` +
`desk_prototype_output.txt`. It produces the WC 2026 outright table using the
static Elo seed + the existing pairwise model + the current Polymarket prices.

It is **not a build target.** Specifically:
- It is a one-off script, not integrated with the engine, the data layer, or
  the contract.
- The numbers are *directionally* useful — they tell you what shape of
  outright calls the real engine will eventually produce — but the
  *magnitudes* carry every weakness we've been speccing fixes for (static
  Elo, no host bonus per fixture, simplified bracket, no bands, no live data).
- The market prices in the output are a snapshot; they move.

Use it to sanity-check your work, **never** to implement against.

## Open threads (Adi owns these)

- **Outright / winner-model spec** — Adi writing next. Don't start outright
  work until it lands.
- **Output-contract ADRs** — citation visibility, outright JSON shape.
  Adi drafts, Faktor reviews, both sign off.
- **Vendor verification (guardrail 4)** — API-Football coverage / cap;
  Railway persistent volume availability; OpenWeather One Call 3.0 endpoint
  + pricing. Adi sourcing before Faktor starts Phase 2.
- **Phase 5 legal / attribution review** — Adi to schedule; required before
  Phase 5 goes Live.

When you start coding, ping Adi on the guardrail-4 verifications so nothing
gets built on stale vendor assumptions.
