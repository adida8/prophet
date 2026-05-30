# ADR 0003 — `MatchOutput.market_sources`

- Date: 2026-05-30
- Status: Accepted
- Driver: Front-of-house outgoing trade buttons + external-consumer wire (Market Tips AI)
- Authority: `THE_DESK_SPEC.md` §6 (contract changes require an ADR)

## Context

The published `MatchOutput` exposed exactly one venue: the verdict's
`market_venue` / `market_url` / `price`, and only on a Pick. That's the
single venue whose price the Pick rode on — fine for the headline CTA,
but it throws away everything else the engine knows.

The engine already computes **multi-venue** prices internally:
`MarketSnapshot.prices` is a tuple of `VenuePrice(venue, side,
implied_p)`, one row per venue per side, and `best_for(side)` picks the
cheapest venue per side. The published contract simply dropped that
detail at publish time.

The consumer ask: render the **full row of outgoing trade buttons** for a
fixture — every prediction-market / sportsbook venue we link out to, each
with a deep link to *that fixture's page on that site*, and a flag marking
which one the Pick is on. Today the static site reconstructs those links
ad-hoc at build time (`site/generate.py` rebuilds a Polymarket pill and a
Kalshi pill, the latter via a build-time Kalshi event-index lookup).
External consumers (Market Tips AI) have no equivalent and can't render the
button row at all.

## Decision

Add an additive, **top-level** list on `MatchOutput`:

```python
class MarketSource(BaseModel):
    venue:        MarketVenue                       # "polymarket" | "kalshi"
    name:         str                               # display name, e.g. "Polymarket"
    url:          str                               # https deep link to this fixture's page
    picked:       bool = False                      # true on the Pick's venue only
    priced_sides: list[Literal["a","b","draw"]] = []  # which sides this venue quoted

class MatchOutput(BaseModel):
    ...
    market_sources: list[MarketSource] = []         # max_length 8
```

### Placement: top-level, not inside `verdict`

`market_sources` describes the **inputs** to the call (which venues we
read, what they priced), not the call itself. It stays meaningful on
`pass` / `avoid` / `withdrawn`, where there is no picked side — the buttons
are still useful. `verdict` stays the single-venue headline; the inputs
live alongside it.

### Semantics

- The list carries **every venue we surface a CTA for**, not only the
  picked one. For football WC26 that's Polymarket + Kalshi.
- `picked` is `true` for exactly the venue whose price backs the Pick
  side (`verdict.market_venue`), and `false` on every venue when the
  verdict is not a Pick.
- `priced_sides` is the honest "used in the calculation?" signal. It
  comes straight off `MarketSnapshot`, so a venue that fed the model has
  a non-empty list; a venue we link for convenience but don't yet ingest
  has `[]`. Today Kalshi is a stub → `priced_sides: []`; Polymarket →
  `["a","draw","b"]`. When Kalshi ingest lands its prices flow into the
  snapshot and `priced_sides` fills in automatically — no contract change.

### URL fallbacks

`url` is the deep link to the fixture's page on the venue, or the
venue's nearest landing page when no per-event deep link exists yet:

- **Polymarket** — real per-event deep link from the source slug
  (`market_url_for_fixture`). Falls back to `https://polymarket.com/`
  only if the slug is missing.
- **Kalshi** — the World Cup category landing page today. The engine has
  no per-event Kalshi deep link (ingest is a stub); the richer
  build-time event-ticker resolution lives in `site/generate.py` and can
  override the contract value when the site is wired to consume
  `market_sources` (deferred follow-on). The empty `priced_sides`
  already tells a consumer this link is convenience-only.

## Detection / production

`desk/sports/football/market_links.py:build_market_sources(fx, snapshot,
verdict)` assembles the list. `FootballSport.decide_and_explain` returns
it as a 5th tuple element; the runner threads it onto
`MatchOutput.market_sources`. The runner's tuple-arity handling already
tolerates 2/3/4-tuples from older sport adapters — 5 is added without
breaking them. Backtest replay is unaffected (it doesn't build
`market_sources`; the field defaults to `[]`).

## Invariants

1. **At most one `picked: true`** per list, and only when
   `verdict.state == "pick"`. The picked venue equals
   `verdict.market_venue`.
2. **A picked venue always has non-empty `priced_sides`.** You can't pick
   a price off a venue that quoted nothing.
3. **Order is stable** — render order (Polymarket, then Kalshi);
   `priced_sides` normalised to `a / draw / b`.

## Consumer migration

- Purely additive. Consumers that ignore unknown fields need no change.
- Pydantic / Zod validators with `extra="forbid"` / `.strict()` on
  `MatchOutput` must add the optional `market_sources` field (a list of
  `{venue, name, url, picked, priced_sides}`) before they'll accept new
  payloads. Absent in a payload ⇒ treat as `[]`.
- To render the button row: iterate `market_sources`, draw a button per
  entry using `name` + `url`, and badge the one with `picked: true`.
  Treat `priced_sides: []` as "we link this venue but it didn't feed our
  number" if you want to distinguish a live-priced venue from a
  convenience link.
- The JSON Schema at `desk/contract.schema.json` is regenerated as part
  of this change; the in-sync test
  (`tests/test_contract.py::test_schema_file_in_sync`) enforces it.

## Alternatives considered

- **Per-side venue prices in the contract** (`implied_p` per venue per
  side). Rejected for v1: raw market probabilities have deliberately
  stayed internal (the verdict already exposes the picked side's
  `model_p` / `market_p`). `priced_sides` answers "which venue moved the
  number?" without publishing the full price matrix. Can be added later,
  additively, if a consumer needs it.
- **Extend `verdict` with a venue list.** Rejected: `verdict` is the
  call; the venue inputs are a separate concern and must survive
  pass/avoid where `verdict` carries no venue.
- **Leave it to the site to reconstruct.** Rejected: that's the status
  quo, and it doesn't help external consumers (Market Tips AI) who have
  no build-time link logic. The contract should carry what the buttons
  need.

## References

- `desk/desk/publish/contract.py` — `MarketSource` + `MatchOutput.market_sources`
- `desk/desk/sports/football/market_links.py` — `build_market_sources`
- `desk/desk/sports/football/sport.py` — returns it from `decide_and_explain`
- `desk/desk/runner.py` — threads it onto the published `MatchOutput`
- `desk/CONTRACT_CHANGELOG.md` — public changelog entry
- `desk/contract.schema.json` — regenerated schema
