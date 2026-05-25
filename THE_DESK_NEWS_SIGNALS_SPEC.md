# The Desk — News & Editorial Signals Spec (v0.1 draft)

**Status:** draft, for build by Claude Code.
**Engine owner:** Adi — built in the `prophet` repo with Claude Code. **Source seeding:** Adi / Claude (separate research task — see §15).
**Date:** 2026-05-21.

**Relationship to existing specs**

- Extends the **Features** and **Explainer** steps of the pipeline in `THE_DESK_SPEC.md`.
- The hard-signal track (§9) is the injuries/form lever already named as **Phase B** in `THE_DESK_OPTIMIZATION_SPEC.md` — biggest Brier lever.
- The extraction + copy work (§7–8) is the natural job for **PR 5** (Haiku explainer, needs `ANTHROPIC_API_KEY`). Build them together.
- Honours the late-binding rule: lineups/injuries enter the model only in the final ~5 days.
- Also folds in **live Elo ingest** (§9.5) — the ratings base the hard-signal track adjusts. This overlaps **Phase 1b** of `THE_DESK_DATA_LAYER_SPEC.md`; ownership to settle in §16 so it's built once, not twice.

---

## 0. The one principle

**Map sources to entities, then resolve per fixture — never to a tournament.**

If we curate "100 World Cup sources" we throw the work away when we add Série A or tennis. Instead, each source is tagged by *what it covers*; a fixture resolves its own source set at runtime. The World Cup is just the first set of tags we populate. Local leagues, other sports = new tags on the same registry, **no engine change**.

A second principle gates everything: **a source's trust decides which track it can feed.** High-trust factual outlets can move the model number; everything else only enriches the editorial prose.

---

## 1. Goals / non-goals

**Goals**

- A sport- and league-agnostic source registry + resolver.
- Two clearly separated tracks: hard signals (model) and editorial signals (copy).
- Attributed editorial colour in the published blurb ("according to the Argentine press…") with a real, fetchable citation behind every claim.
- Generalises to local leagues and other sports by adding registry rows only.

**Non-goals**

- No change to the verdict thresholds or the market-reading logic.
- No raw article text in the output contract — only structured, attributed signals and citations.
- Source discovery / curation is **not** in this spec (see §15).

---

## 2. Two-track model

The single most important design decision. Every signal extracted from a source flows down exactly one of these tracks, decided by the source's trust gate.

| | **Hard signals** | **Editorial signals** |
|---|---|---|
| Examples | confirmed injury, suspension, confirmed starting XI | pundit takes, "pressure on the manager", form narrative, local mood |
| Source trust | high only (`can_feed_model`) | any trusted-enough source, incl. homer press |
| Flows to | **Features → Model** (adjusts probabilities) | **Explainer** (blurb + `copy.citations`) |
| Moves the number? | **Yes** | **No, ever** |
| Phase | Phase 2 (= Phase B) | Phase 1 (ship first) |

Mixing these up is the classic failure mode. A biased local column can be *quoted*; it must never shift the model's probability.

---

## 3. Where it sits in the pipeline

```
Ingest → Features → Model → Verdict → Explainer → Publish
            ▲                              ▲
            │ hard signals                 │ editorial signals
            └────────── desk/signals/ ─────┘
```

New **sport-agnostic** subsystem:

```
desk/signals/
├── registry.py     # Source model + seed loader
├── resolve.py      # fixture → [Source]  (tag intersection)
├── fetch.py        # RSS / sitemap / aggregator readers + cache + dedupe
├── extract.py      # source item → [Signal]  (LLM; ties PR 5)
├── consensus.py    # plural-attribution detection (§8)
└── models.py       # Source, SourceItem, Signal dataclasses/Pydantic
```

**Sport-boundary compliance (non-negotiable, per CLAUDE.md):** `desk/signals/` is sport-agnostic and never imports from a sport package. The mapping of *hard* signals → `FootballFeatures` lives in `desk/sports/football/` (the features builder consumes `Signal[]`). The signal **taxonomy** (what an "injury" or "lineup" signal is) is shared/agnostic; only the feature *mapping* is sport-specific. Adding tennis later = a new mapping in `desk/sports/tennis/`, not a refactor.

---

## 4. Source registry (schema)

```
Source
  id              olé, bbc-sport, globo-esporte, gdelt-longtail
  name            "Olé"
  feed_type       rss | sitemap | api | aggregator
  feed_ref        URL, or a query template for aggregators
  language        es | en | pt | …
  coverage_tags   ["sport:football", "country:ar", "club:boca"]
                  # flat strings; "global" / "league:wc26" also valid
  reliability     0.0–1.0     # editorial trust + factual accuracy
  bias_flag       none | national | club    # homer alignment — SEPARATE from reliability
  tier            trusted_core | long_tail
  enabled         bool
  last_fetched    timestamp
```

**Derived gates (computed, not stored):**

```
can_feed_model = reliability >= 0.8 AND bias_flag == none AND tier == trusted_core
editorial_only = NOT can_feed_model      # still valid for blurb + citation
```

`reliability` and `bias_flag` stay separate: a biased outlet can still be factually accurate, so it can be quoted at high reliability while being barred from the model.

**Storage:** seed ships as a checked-in, reviewable file (CSV/xlsx → loaded at startup), so the registry is versioned and diffable. Runtime state (`last_fetched`) lives in a small table in `data/signals.db` (gitignored, like the other `.db` files). `coverage_tags` are plain strings precisely so a new league never requires a schema migration.

---

## 5. The resolver

```python
def sources_for(fixture) -> list[Source]:
    want = {
        "global",
        f"sport:{fixture.sport}",
        f"country:{fixture.country_a}", f"country:{fixture.country_b}",
        f"league:{fixture.competition}",
        f"club:{fixture.team_a}", f"club:{fixture.team_b}",
    }
    return sorted(
        (s for s in registry if s.enabled and set(s.coverage_tags) & want),
        key=lambda s: s.reliability, reverse=True,
    )
```

A national-team fixture pulls `country:` + `global`; a Série A match pulls `league:` + `club:` + `country:br`. Same code, no World Cup special-casing.

---

## 6. Source acquisition

Hybrid by design:

- **Trusted core** — tier-1 outlets with clean RSS/sitemaps (BBC Sport, Guardian, ESPN, Reuters, plus the top 3–6 outlets per nation). Hand-weighted reliability + bias_flag. This is the only manual set, and it's small (tens of rows).
- **Long tail** — one `aggregator` row (GDELT proposed: free, global, multilingual, query-by-entity). Provides breadth across every country/language; gated harder because we trust it less (`tier = long_tail` ⇒ `editorial_only`).

Fetch mechanics: respect robots/ToS; per-source polite rate; cache raw items; dedupe by canonical URL then content hash. Only un-seen/changed items proceed to extraction (cost control, §12).

---

## 7. Extraction (LLM)

Each fetched item → zero or more structured `Signal`s. **This is where PR 5's Haiku/Anthropic SDK does double duty** — the same model that writes copy reads sources into signals.

```
Signal
  type            injury | suspension | lineup | morale | manager_quote | form | other
  team            <team id this signal is about>
  claim           short normalised statement (engine-side)
  quote           VERBATIM sentence from the source (load-bearing — see §8)
  quote_original  verbatim in source language (if translated)
  quote_lang      pt | es | …
  source_id       → Source
  url             deep link to the article
  published_at    timestamp
  confidence      0.0–1.0 (model's extraction confidence)
```

Track assignment is mechanical: `type ∈ {injury, suspension, lineup}` **and** the source's `can_feed_model` ⇒ hard track; everything else ⇒ editorial track. The LLM never decides the track — the source gate does.

---

## 8. Editorial track → copy

Editorial signals become attributed colour in `copy.blurb`/`copy.summary` and entries in `copy.citations`. Voice rules in `explainer/voice.py` still apply (no banned phrases, no exclamation, no emoji).

**Three guardrails — bake these in:**

1. **The citation is load-bearing.** "According to local press…" must point to a real, fetchable line. Every editorial claim in the prose maps to a citation carrying the actual `url` **and** the verbatim `quote`. If a claim has no citation, it cannot be written.

2. **Plural attribution requires consensus.** "Local press" / "the Argentine press" implies agreement and may only be used when **≥2 independent sources** carry the same claim (`consensus.py` clusters signals by claim + team). A single source is named explicitly — *Olé*, *Globo* — never generalised.

3. **Translation honesty.** Non-English quotes are translated faithfully for the blurb, but the citation keeps `quote_original` + `quote_lang` + the source link so a reader can verify.

---

## 9. Hard-signal track → model features (Phase 2 / Phase B)

High-trust signals only (`can_feed_model`). The football features builder consumes `Signal[]` and maps confirmed facts to **bounded** feature adjustments — e.g. a confirmed key-player-out applies a capped Elo penalty; a confirmed XI refines it. Rules:

- **Late-binding:** these adjustments only apply inside the final ~5 days before kickoff (per the locked rule). Pre-window runs ignore them.
- **Bounded + auditable:** an adjustment can nudge, never override, and each one logs the `Signal` (source + quote) that caused it.
- The model still **never reads markets**. Hard signals are feature inputs, not market data.

Exact mapping (Elo penalty vs a dedicated feature) is an open decision, to be settled during build to align with Phase B (§16).

---

## 9.5 Live Elo ingest — the base the hard-signal track adjusts

§9's "capped Elo penalty for a confirmed absence" only means something if the Elo it adjusts is itself current. Today it isn't: `desk/sports/football/ingest/elo_intl.py` and `elo_club.py` are stubs that read a hand-typed frozen table (`data/elo_seed.py`, audited mid-2026). Any team missing from that table falls back to a 1500 stub, and the verdict step force-Passes the match (the stub-Elo gate). Live Elo replaces the frozen reads with current, cited ratings. **It is the prerequisite for §9, not an optional extra** — the penalty in §9 nudges a number that has to be real first.

**Overlap — settle ownership before build (§16).** This is **Phase 1b** of `THE_DESK_DATA_LAYER_SPEC.md`. It is specced here because the hard-signal track is dead weight without it; if the data-layer spec owns the build, this section collapses to a cross-reference. Pick one owner.

**Not a news source.** Elo does not enter the §4 registry — it carries no `reliability` / `bias_flag` and is never quoted in copy. It is a structured ratings feed, and the readers stay under `desk/sports/football/ingest/` — **not** in `desk/signals/`. Sport-boundary holds (eloratings is national, ClubElo is club-specific — both legitimately sport-scoped).

**Sources**

| Scope | tier-1 source | Mechanics | Cost |
|---|---|---|---|
| National (WC26 field) | eloratings.net | No clean API — parse the published ratings table; map name → ISO3 via the existing `iso3_for_name` registry | free |
| Club (later leagues) | ClubElo (`api.clubelo.com`) | Clean per-club CSV endpoint; carries point-in-time history | free |

The asymmetry is real: ClubElo is a tidy fetch; eloratings.net is a scrape and the more fragile dependency of the two — treat it as higher-maintenance, and give national Elo a tier-2 corroborator (FIFA rank) so a broken scrape degrades rather than blanks the WC field.

**Binding & cadence.** Always-bound (not late-binding) — refreshed **weekly**, after international windows. A run uses the most recent rating inside its TTL; outside TTL the rating is *absent*, never a silently-stale number.

**Provenance + sanity (mirror the data-layer spec's pillars).** Every rating carries `(source_id, source_url, fetched_at)`. A range-sanity gate rejects out-of-band values; a value failing it is absent with a reason code and logged loudly — a frozen seed read is never silently dressed up as live.

**The payoff — the stub-gate deactivates itself.** The model already tags each Elo `"wiki"` / `"clubelo"` (real) or `"stub"` (default fallback), and the verdict step's stub-Elo gate fires only on `"stub"`. Once live ingest supplies real ratings for the WC26 field, the tag flips and the gate goes inert with no extra wiring — the fixtures the funnel drops each run for shaky ratings stop being dropped. Per CLAUDE.md, **match Picks are not real betting signals until this lands.**

**Backtestable — unlike the news tracks.** ClubElo and eloratings history are point-in-time, so the WC-2022 backtest stays valid (no future-knowledge leak). This is the one source in scope here that can be *historically* validated rather than forward-validated in Shadow.

---

## 10. Contract changes

`copy.citations` already exists in the output contract. Define the richer citation object:

```json
{ "outlet": "Olé", "url": "https://…", "quote": "…",
  "quote_original": "…", "quote_lang": "es", "published_at": "2026-06-10T08:00:00Z" }
```

Engine internals (`Signal.claim`, confidence, reliability weights, the registry itself) **stay inside The Desk** and never reach the contract. Any new top-level contract field requires an **ADR** (per CLAUDE.md). Enriching the existing `citations` shape should be confirmed against `publish/contract.py` (Pydantic v2, single source of truth) + `contract.schema.json`.

---

## 11. Scheduling / freshness

Ties to **PR 6** (scheduler). Suggested cadence:

- Editorial refresh: daily per priced fixture.
- Final window (≤5 days to kickoff): higher cadence, and hard-signal extraction switched on.
- TTL per tier; `last_fetched` gates re-fetch.

---

## 12. Cost & scale

Extraction is the cost driver. Controls: cache + dedupe before extraction so only new items hit the LLM; cap long-tail items per fixture; trusted core first; batch where possible. 100+ sources is mostly the single aggregator row — only the trusted core multiplies rows.

---

## 13. Testing

- Unit: resolver tag-intersection; `can_feed_model`/`editorial_only` gate logic; plural-attribution rule; translation passthrough.
- **Guard test (mirror the backtest import-guard discipline):** assert no editorial-only source can ever reach the model-feature path. Scan that `desk/sports/*/features` only consumes signals whose source `can_feed_model`.
- Golden test: a fixture + frozen source fixtures → expected `copy.citations`.
- No live network in tests — use recorded fixtures/cassettes.
- **Live Elo (§9.5):** range-sanity gate rejects out-of-band ratings → absent + reason code; assert the stub-Elo gate goes inert once a fixture's ratings resolve `"wiki"` / `"clubelo"` (provenance flips → no force-Pass); WC-2022 backtest stays valid on point-in-time Elo (no future leak).

---

## 14. Phasing / PR ladder

Each PR ships tests green.

- **PR 0 (foundation)** — live Elo ingest (§9.5): wire `elo_intl.py` / `elo_club.py` to live sources + provenance + range-sanity gate. Lands independently of the news track and **must precede PR F** (PR F's Elo penalties adjust this base). If the data-layer spec owns it instead, drop this and depend on Phase 1b.
- **PR A** — registry model + resolver + seed loader (no fetch).
- **PR B** — fetch + cache + dedupe for trusted-core RSS/sitemaps.
- **PR C** — extraction → `Signal[]` (Haiku; folds into PR 5).
- **PR D** — editorial track → `copy.citations` + three guardrails + voice integration. *(Track 1 ships here.)*
- **PR E** — GDELT long-tail aggregator row.
- **PR F** — hard-signal track → bounded model features. *(Track 2 / Phase B.)*

---

## 15. Owned elsewhere — source seeding

Filling the registry is a **separate research task**, not engine work. Adi/Claude produce the seed as an **xlsx** (one row per source, columns = the §4 schema), starting with WC26: global tier-1 + the top 3–4 outlets per qualified nation, bias-flagged. The engine just imports it. Local leagues / other sports get seeded the same way later.

---

## 16. Open decisions

- Registry storage: checked-in seed file (proposed) vs full DB table.
- Aggregator: GDELT (proposed) vs NewsAPI-style — licensing + cost + noise trade-off.
- Extraction model: confirm Haiku (PR 5).
- `can_feed_model` reliability threshold: proposed `0.8`.
- How hard-signal adjustments enter the model (capped Elo penalty vs dedicated feature) — align with Phase B.
- **Live Elo ownership (§9.5):** this spec's PR 0 vs `THE_DESK_DATA_LAYER_SPEC.md` Phase 1b — pick one owner so it's built once.
- **National Elo source:** eloratings.net scrape (proposed) vs a cleaner/paid feed — fragility vs cost; tier-2 corroborator (FIFA rank) assumed.
- **Elo TTL / refresh cadence:** weekly proposed — confirm against international-window timing.
