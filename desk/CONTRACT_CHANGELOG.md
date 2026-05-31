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

## 2026-05-30 — v1.3.0 · `add`

**Add `MatchOutput.market_prices`, `consensus_fair`, `region` (non-US pivot)**

Three new optional top-level fields driving the cross-venue
comparison surface. See ADR
[0004-cross-venue-prices](docs/adr/0004-cross-venue-prices.md) for
the full motivation; in short, the site re-orients to non-US traffic
and the comparison stops being Polymarket-vs-Kalshi and becomes
Polymarket-vs-sportsbooks-vs-exchanges. The contract now carries one
row per side, per venue, with the **true price** (`e`) the consumer
actually pays + each venue's de-vigged opinion + a per-side
`is_best` flag (cheapest venue by `true_price`).

```jsonc
"market_prices": [
  { "side": "a",
    "venues": [
      {"venue":"pinnacle",     "name":"Pinnacle",          "venue_type":"sportsbook",
       "region":"eu","decimal_odds":5.40,"implied_p":0.1852,
       "true_price":0.1852,"fair_p":0.168,"overround":1.10,"is_best":false},
      {"venue":"betfair_ex_uk","name":"Betfair Exchange (UK)","venue_type":"exchange",
       "region":"uk","decimal_odds":5.00,"implied_p":0.2000,
       "true_price":0.2033,"fair_p":0.187,"overround":1.07,"is_best":false},
      {"venue":"williamhill",  "name":"William Hill",      "venue_type":"sportsbook",
       "region":"uk","decimal_odds":5.50,"implied_p":0.1818,
       "true_price":0.1818,"fair_p":0.146,"overround":1.35,"is_best":true}
    ]}
],
"consensus_fair": {"a": 0.158, "draw": 0.255, "b": 0.587},
"region": "non-us"
```

- **Driver:** non-US sportsbook integration
  (`THE_DESK_NONUS_SPORTSBOOK_SCOPING.md`). Edge runs against
  `true_price` (`= ask + fee + half_spread` on Polymarket,
  `1/(1+(b-1)(1-c))` on Betfair Exchange, `1/decimal` on sportsbooks)
  — the all-in cost of acting on a side at a venue. Comparing
  `model_p` to a de-vigged `fair_p` instead is the classic mistake
  the doc calls out.
- **`market_prices`** is the per-venue, per-side detail.
  `consensus_fair` is the sharp-weighted blend of `fair_p` across
  venues (Pinnacle weight 3, William Hill 1) — narrative only,
  **never used for edge**. `region` (`us` | `non-us`) tags the
  audience bucket so the front-end can render the correct venue set.
- **Flag-gated.** With `DESK_CROSS_VENUE_EDGE=0` (default) the engine
  emits `market_prices=[]` and `consensus_fair=null`; pre-pivot
  payloads remain byte-identical. WC-2022 backtest verified
  byte-identical: Brier 0.5806 (model) / 0.5794 (market),
  30 pick / 34 pass / 0 avoid.

**Also extends the `MarketVenue` enum** with the non-US launch set:
`pinnacle`, `betfair_ex_uk`, `betfair_ex_eu`, `williamhill`,
`skybet`. Existing consumers that pattern-match the enum should
treat new values as opaque and use `MarketPriceVenue.name` for
display.

- **Migration:** purely additive on the JSON wire. Pydantic / Zod
  validators with `extra="forbid"` add the three optional fields.
  Schema regenerated; the in-sync test enforces it.

## 2026-05-30 — v1.2.0 · `add`

**Add `MatchOutput.market_sources`**

A new top-level list of the prediction-market / sportsbook venues we
link a trade CTA for on a fixture — so a consumer can render the full
row of outgoing buttons from the contract alone, not just the single
venue the Pick rode on.

```jsonc
"market_sources": [
  { "venue": "polymarket", "name": "Polymarket",
    "url": "https://polymarket.com/sports/fifa-world-cup/fifwc-fra-mex-2026-06-12",
    "picked": true,  "priced_sides": ["a","draw","b"] },
  { "venue": "kalshi", "name": "Kalshi",
    "url": "https://kalshi.com/category/sports/soccer/fifa-world-cup",
    "picked": false, "priced_sides": [] }
]
```

- **Driver:** front-of-house outgoing trade buttons + external-consumer
  wire (Market Tips AI) needs every venue + its deep link, with a flag
  for which one the Pick is on — not only the chosen venue.
- **ADR:** `desk/docs/adr/0003-market-sources.md`
- **Fields:** `venue` (`polymarket` | `kalshi`, matches
  `verdict.market_venue`'s enum), `name` (display string), `url` (https
  deep link to the fixture's page on the venue, or the venue's nearest
  landing page when no per-event deep link exists yet), `picked`
  (boolean — `true` only on the Pick's venue, `false` on every venue for
  pass/avoid/withdrawn), `priced_sides` (list of `a` / `draw` / `b` the
  venue actually quoted into the calculation; **empty ⇒ linked for
  convenience but did not feed the model**, e.g. a venue we don't yet
  ingest).
- **Schema delta:** `MatchOutput` gains `market_sources`
  (array, max 8, default `[]`) and a new `$defs/MarketSource`. No removed
  fields. No changed fields.
- **Migration:** purely additive. Consumers that ignore unknown fields
  need no change. `extra="forbid"` / strict validators must add the
  optional `market_sources` array before accepting new payloads; absent
  ⇒ treat as `[]`. To render the button row, iterate the list, draw a
  button per entry from `name` + `url`, and badge the `picked: true`
  one. Note: today only Polymarket feeds the model, so the Kalshi entry
  carries the WC landing page and `priced_sides: []`; that upgrades to a
  per-event Kalshi deep link + populated sides when Kalshi ingest lands,
  with no further contract change.

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
