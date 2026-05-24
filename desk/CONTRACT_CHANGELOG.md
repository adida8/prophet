# The Desk — output contract changelog

This file logs every change to the **public output contract** —
`desk/desk/publish/contract.py` + the generated JSON Schema at
`desk/contract.schema.json`. External consumers subscribe to this file
(GitHub watch on the path) for breaking-change notifications.

**Compatibility policy.** All changes are additive-optional by default.
Renames or removes require a ≥ 30-day deprecation window, announced
here with a date. Breaking changes need an ADR under `desk/docs/adr/`
and explicit sign-off from each registered consumer.

Each entry includes: date, contract version (semver), change type
(`add` / `deprecate` / `remove` / `breaking`), what changed, why, and
the migration notes consumers need.

---

## 2026-05-24 — v1.1.0 · `add`

**Add `VerdictState.WITHDRAWN = "withdrawn"`**

`verdict.state` now accepts a fourth value `"withdrawn"`, signalling
that a previously-published `match_id` has left the live universe
(cancelled, postponed past slug date, de-listed by the source venue,
renamed). Field semantics match `pass` / `avoid` — `side`,
`market_venue`, `price`, `model_p`, `market_p` all null; `edge_pp`
and `market_url` optional.

- **Driver:** external-consumer wire (Market Tips AI) needs an explicit
  deletion signal so the receiver can distinguish "engine is offline"
  from "we no longer track this fixture".
- **ADR:** `desk/docs/adr/0001-withdrawn-verdict-state.md`
- **Detection:** `desk/desk/distribute/withdrawn.py` — diffs each
  per-sport `index.json` against the current run's published match_ids
  and emits one final withdrawn payload per disappeared fixture.
  Single-shot per fixture; subsequent runs no longer carry the
  match_id in the prior index.
- **Schema delta:** `MatchOutput.verdict.state` enum gains the
  `"withdrawn"` value. No new fields. No removed fields.
- **Migration:** consumers that switch on `verdict.state` MUST add a
  branch for `"withdrawn"`. Pydantic / Zod validators with `strict`
  on unknown enum values will reject withdrawn payloads until
  updated. Consumers that pass `verdict.state` through opaquely
  (string passthrough) need no change.

---

## 2026-04-XX — v1.0.0 · baseline

First documented contract baseline — `MatchOutput`, `OutputIndex`,
`Verdict { pick | pass | avoid }`, `Copy { title, summary, blurb,
citations, editorial_citations, drivers }`, `Venue { city, stadium,
country (ISO-2) }`, top-level `hard_signal_adjustments`. See
`desk/contract.schema.json` at this version for the canonical shape.
