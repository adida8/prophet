# ADR 0001 — Where `SeoCopy` lives on the contract

**Status:** Accepted, 2026-05-10.
**Owner:** Adi.
**Implements:** schema decision for SEO-1 in `THE_DESK_SEO_BRIEF.md`.
**Supersedes:** none. **Superseded by:** none.

---

## Context

`THE_DESK_SEO_BRIEF.md` introduces an `SeoCopy` block — title tag,
meta description, H1, blurb, FAQ pairs, primary query, entities
covered — on every published view (match / competition / team). The
brief deferred where `SeoCopy` lives on the published contract; the
SEO method is renderer-agnostic but the schema decision can't be.

Today's `MatchOutput` (in `desk/publish/contract.py`) carries a single
`copy: Copy` block with `title`, `summary`, `blurb`, `citations`, and
a structured `drivers` list (the "Why this call?" bullets the
front-of-house renders above the CTA). `Copy` is voice-rule-checked
in `desk/explainer/voice.py`. The SEO method adds additional gates
(length caps, query placement, entity coverage, density, readability)
and additional fields with a different lifecycle from the editorial
`Copy`.

Three placements are viable:

- **A — Nested under `Copy`.** Add SEO fields directly to the existing
  `Copy` model, or as a sub-attribute (`copy.seo: SeoFields`).
- **B — Sibling block on the output container.** Add
  `seo: Optional[SeoCopy] = None` as a top-level field on
  `MatchOutput`. New `CompetitionOutput` / `TeamOutput` containers
  (introduced in SEO-2 / SEO-3) carry the same sibling block.
- **C — Separate output document.** Publish a parallel
  `match-id.seo.json` per match, alongside the existing match JSON.

## Decision

**B — sibling block on the output container.** `MatchOutput` gains
`seo: Optional[SeoCopy] = None` — optional so existing snapshots and
SEO-skipped fixtures stay valid. The net-new rollup containers
(`CompetitionOutput`, `TeamOutput` — added in SEO-2 / SEO-3) carry
`seo: SeoCopy` non-optional, because SEO copy is the reason those
documents exist. `SeoCopy` is a new Pydantic v2 model in
`desk/publish/contract.py` with the fields specified in §5 of the
SEO brief.

## Consequences

- **Separation of concerns is clean.** `copy.drivers` is UX furniture
  (bullets above the CTA, lifecycle tied to verdict state).
  `seo.faq` is search-result furniture (lifecycle tied to query
  intent + indexable entities). They share a sport, a fixture, and a
  voice rule set — and nothing else. Keeping them sibling makes that
  obvious in the schema.
- **Validation surface co-locates with data.** Today's
  `assert_voice_clean()` runs on `Copy` strings. SEO adds length caps,
  query placement, entity coverage, density, readability — applied
  only to `SeoCopy` fields. With a sibling block, the gates live next
  to the data they validate; nesting under `Copy` would force voice
  rules and SEO rules to share a code path that doesn't fit either.
- **Renderer-friendly.** A consumer that doesn't care about SEO
  ignores the `seo` field; their validators stay green because the
  field is optional. A consumer that does care fetches one document,
  not two, and addresses fields at one level below the root.
- **Atomic-write semantics unchanged.** `desk/publish/writer.py`'s
  per-match atomic write covers `seo` too — there's no second-file
  coordination problem (which is the failure mode rejected with
  option C below).
- **Schema bump is backward-compatible.** `seo` is optional; any
  match JSON published before SEO-1 still validates against the new
  schema. The in-sync test on `desk/contract.schema.json` regenerates
  cleanly.
- **Establishes a pattern.** Future contract additions (the v1.2
  Avoid redefinition flagged in `THE_DESK_OPTIMIZATION_SPEC.md`,
  whatever sport-2 adds) follow the same sibling-block rule — the
  contract grows by accretion, not by retrofitting `Copy`.

## Alternatives considered

### A — Nested under `Copy`

Rejected. Two reasons.

First, lifecycle mismatch. `drivers` regenerate whenever the verdict
state changes; `SeoCopy.blurb` can be stable across many pipeline
runs (the entities and queries don't change minute-to-minute).
Putting them under one model implies a shared regeneration cadence
that isn't true.

Second, validation conflation. Today `voice.assert_voice_clean()` is
the single gate on `Copy`. SEO mode's gates are additive *and*
selectively applied (length caps differ per SEO field; query
placement only checks blurb / title_tag / h1). A nested model means
the gate function has to branch on which sub-field it's looking at,
or the gates fan out in the caller — both are uglier than a sibling
block with its own validator.

### C — Separate output document

Rejected. Two reasons.

First, atomic-write cost. `desk/publish/writer.py` does atomic
per-match writes plus an index update. A second JSON file per match
means a second coordination problem: if the SEO file fails to write
after the match file already wrote, downstream sees inconsistent
state. The brief's retry-and-fall-back-to-stub path inside the
explainer already handles SEO generation failure cleanly; we don't
need a second failure mode at the publish layer.

Second, consumer cost. Any renderer rendering one page would fetch
two documents. CDN cache keys, ETag invalidation, the
`MatchOutputIndexEntry` schema — all of those would gain a parallel
SEO track. Not worth it for a field set that lives natively
alongside the match data it describes.

## Implementation notes

For SEO-1:

- Add `SeoCopy(BaseModel)` to `desk/publish/contract.py` with fields
  per §5 of the SEO brief. `model_config = ConfigDict(extra="forbid")`
  matches the rest of the contract.
- Add `seo: Optional[SeoCopy] = None` to `MatchOutput`. Field-level
  default keeps existing fixtures valid.
- Regenerate `desk/contract.schema.json`; the in-sync test enforces
  the bump landed.
- `desk/explainer/seo/` builds the `SeoCopy`; `desk/runner.py`
  attaches it before the publish step calls `writer.py`.
- New tests: schema validation with and without `seo`; round-trip
  through `writer.py`; voice + SEO validation gate ordering.

For SEO-2 / SEO-3, `CompetitionOutput` and `TeamOutput` are net-new
contracts. Both carry `seo: SeoCopy` non-optional. No editorial
`Copy` block on hubs — `drivers` and `citations` belong to per-match
output, not to a rollup view.

## Open questions deferred to later ADRs

- **JSON-LD attachment.** SEO-4 emits FAQPage / SportsEvent JSON-LD
  strings. Likely as a `seo.jsonld: list[str]` field, but that's a
  decision for the SEO-4 ADR — depends on whether we ship JSON-LD as
  pre-rendered strings or as structured Python that the renderer
  serializes.
- **Per-state SEO blocks.** Today's `Copy` is generated for all three
  verdict states. The SEO brief leans toward generating SEO copy for
  Pass and Avoid at the match level too (so every published match
  page is indexable) and only surfacing Picks on competition / team
  hubs. That second half is a rollup decision — what a hub links to —
  and lives in the SEO-2 / SEO-3 implementation, not a contract ADR.
