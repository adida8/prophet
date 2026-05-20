# Phase 5 — Legal / Attribution Review Brief

**Status:** prep document for a media / IP / copyright counsel review.
**Owner:** Adi.
**Required before:** Phase 5 of the data layer goes **Live** (per
`THE_DESK_DATA_LAYER_SPEC.md` §5 Phase 5 + §8 open questions). Phases 1–4
ship independently of this; review timing is "before Live", not "before
build."
**Hand this to:** media-law / IP counsel familiar with content licensing,
fair-use / fair-dealing, and the legal posture of LLM-based fact extraction.

---

## 1. What Phase 5 does (and doesn't)

The desk's "data layer" is a pipeline that ingests external data and feeds it
to a probabilistic football betting model. **Phase 5 — expert signal** adds
one specific kind of data: editorial commentary and reporting from sports
journalists and ex-player pundits.

It has **two tiers, kept deliberately apart:**

- **Factual tier.** Concrete claims from the source (player doubtful for
  Sunday; manager confirmed formation change; clinic confirmed injury) are
  extracted by an LLM (Claude Haiku) from the source text. The extracted
  claims are used internally to corroborate a separate, structured injury /
  lineup feed — they are **not** themselves a direct input to the
  probabilistic model.
- **Editorial tier.** Qualitative context (a manager's tactical read; a
  season narrative; a "team morale" note) is summarised and attributed.
  These summaries appear in the user-facing verdict's `copy.citations`
  ("L'Équipe's correspondent flags the same midfield gap") and in the
  driver bullets explaining *why* the model rates a team a certain way.
  They are **not** an input to the probabilistic model's maths.

Crucially, Phase 5 is split by **access type**:

- **Free-content extraction.** Where a publication's content is served
  freely (no paywall, no login wall, no metered access), Haiku may extract
  factual claims and editorial summaries.
- **Paywalled = citation-only.** Where the publication is behind a paywall,
  the desk **may link to the article (as a citation target)** but **does
  NOT extract content from it**. Bypassing paywalls is explicitly forbidden
  in the spec. A paywalled L'Équipe / Marca / Bild article is a citation
  target, not a scrape target.

The architecture rejects "tier-1 paywalled" as a configuration contradiction.

## 2. Attribution rules baked into the spec

Every extracted item carries:

- The named publication or named pundit.
- A dated URL to the source article / post / transcript.
- The original publication date.

Hard rules:

- Only what a source actually said is extracted — **never** a paraphrase
  that becomes a fabricated quote.
- Voice + banned-phrase tests run on every extracted item.
- An automated test asserts no source flagged `paywalled` ever produces an
  extracted body; only a citation link.
- A failed attribution test marks the item **absent**; it never publishes.

## 3. Curated source list (representative — not final)

Per-competition, the operator (Adi) curates a list of `(publication-or-pundit,
access_kind)` registered as a `Source(data_type=EXPERT)`. Starting set for the
WC 2026 launch:

| Source | Country / language | Access kind | Use |
|---|---|---|---|
| ESPN soccer | EN | free | extraction + citation |
| BBC Sport | EN | free | extraction + citation |
| Globo Esporte (free sections) | PT (Brazil) | mixed | extraction on free; citation on premium |
| L'Équipe (free sections) | FR | mixed | extraction on free; citation on premium |
| Marca (free sections) | ES | mixed | extraction on free; citation on premium |
| Bild (free sections) | DE | mixed | extraction on free; citation on premium |
| Süddeutsche Zeitung | DE | paywalled | citation-only |
| Named-pundit public posts (X/social, broadcaster sites) | various | free | extraction + citation, attributed to pundit |
| Broadcaster post-match transcripts (BBC, ESPN, etc.) | EN | free | extraction + citation |

The list is reviewable, operator-curated, not scraped wholesale. Counsel
should flag any specific source whose terms-of-service prohibit even fact
extraction from freely-served content; those would be downgraded to
citation-only.

## 4. Specific questions for counsel

In rough priority order — these are the load-bearing legal questions Phase 5
relies on.

### 4.1 Fair use / fair dealing for LLM extraction of facts

- **Question.** When Haiku reads a freely-accessible article and extracts a
  factual claim ("Manchester United's Casemiro is doubtful for Sunday"),
  attributing that fact to the publication, what's the legal posture? Facts
  themselves are generally not copyrightable, but the *expression* is.
- **Specific worry.** If the extracted fact closely tracks the article's
  phrasing, does that risk crossing from fair use into copyright
  infringement? At what length of extracted text does the risk become
  meaningful?
- **Mitigation in design.** Extraction is *fact-focused*, not text-copying.
  Haiku is prompted to *report* what the source *says*, with attribution —
  not to reproduce passages.
- **Jurisdictions of concern.** UK (Adi t/a sole trader; market_tips_ai
  is UK-based per memory; pre-incorporation status). US (where many users
  will read). EU (GDPR-adjacent — though this is content-rights, not
  personal-data). Brazil + Spain + France + Germany for the per-country
  sources.

### 4.2 Database rights / sui generis (EU)

- **Question.** The EU's sui generis database right may apply to
  systematically extracting content from a single publication's free site
  at scale. Where's the line?
- **Specific worry.** If the desk's Haiku extraction systematically pulls
  factual claims from, say, L'Équipe's free articles every few hours, does
  that qualify as "substantial extraction" under the database right, even
  if individual extractions look like fair use?
- **Mitigation in design.** Rate-limited; per-source caps; not a
  systematic mirror — only the editorial layer per fixture.

### 4.3 Terms-of-service compliance

- **Question.** Many publications' terms-of-service prohibit automated
  access, scraping, or commercial reuse of content (even freely-served).
  How binding are these terms against an unauthenticated reader (no login,
  no contract), and what risk does the desk take by extracting?
- **Specific need.** Per-source review of ToS for the curated list in §3.
  Sources whose ToS clearly prohibit the use case get downgraded to
  citation-only in the registry.

### 4.4 Robots.txt and technical access controls

- **Question.** What's the legal weight of `robots.txt`? The spec already
  says "respect robots.txt" — but if a publication's robots.txt allows
  reading but their ToS prohibits automation, how should we resolve the
  conflict?
- **Mitigation in design.** Conservative: ANY explicit prohibition (ToS or
  robots) downgrades the source to citation-only.

### 4.5 Attribution sufficiency

- **Question.** Is the spec's attribution model ("named publication or
  pundit + dated URL + original publication date") sufficient under the
  applicable jurisdictions' moral-rights and attribution requirements?
- **Specific need.** Confirm or recommend additional fields (author name?
  publication city? a specific attribution format).

### 4.6 Named-pundit content

- **Question.** Extracting from a pundit's public X/Twitter posts or
  Substack — is the legal posture different from extracting from a
  publication? Both are publicly readable but the rights-holder is
  different (the platform vs the individual).
- **Mitigation in design.** Extraction is attributed to the *pundit by
  name*, not the platform. Treated as a citation of the named individual.

### 4.7 Operating entity status

- **Note for counsel.** Per memory, the desk operates pre-incorporation as
  Adi Dagan trading as Odds Primer (UK sole trader). Phase 5 review should
  factor this status — small-trader scale may shift the practical risk
  posture vs a corporate one, and any required incorporation step before
  Phase 5 Live should be flagged.

## 5. What we're NOT asking counsel to do

- Approve the product strategy. The desk's overall posture (read-only;
  no real-money flows; verdict-as-content) is settled.
- Review Phases 1–4 (Elo, weather, structural API data). Those use vendor
  APIs under their own terms; no editorial content extraction.
- Approve specific blurbs. Voice + banned-phrase + attribution checks are
  automated; counsel reviews the *methodology*, not the per-output.

## 6. Output we'd ideally take from the review

In rough order:

1. **A green / yellow / red flag per source** on the curated §3 list. Green
   = safe to extract from free content. Yellow = extract with specific
   constraints (e.g. attribution format, rate limit). Red = citation-only
   regardless of paywall status.
2. **Recommended attribution format**, if anything beyond what §2 already
   has.
3. **Per-jurisdiction risk summary** for the major sources' home countries.
4. **A reusable rule** for adding new sources to the registry without
   requiring a full review each time (a checklist counsel signs off on,
   the operator applies).

## 7. Timing

Phase 5 is the **last** of the data layer's five phases. Phases 1–4 ship
ahead of it; conservative estimate puts Phase 5 build readiness at 2–3
months out from now (2026-08-ish), gated on Phases 1–4 stabilising.

The legal review should land **before** the Phase 5 model-side wiring
goes Live (i.e. before the editorial tier's outputs reach `copy.citations`
in published verdicts). Build can proceed in Shadow mode without the
review — Shadow means the extraction runs internally for QA but doesn't
reach published copy. Going Live without the review would put attributed
extractions in front of real users, which is the legal-exposure surface.

Suggested calendar: **schedule the review for ~6 weeks before Phase 5
target Live date**, so any required changes (source list pruning, attribution
format) have time to land before publish.

## 8. References

- `THE_DESK_DATA_LAYER_SPEC.md` v0.5 — Phase 5 spec (extraction methodology,
  attribution rules, paywall constraint).
- `THE_DESK_SPEC.md` §5 — the original "respect robots.txt and per-source
  rate limits" constraint.
- (For counsel) the curated source list in §3 above — operator will provide
  the full per-source ToS texts on request.
