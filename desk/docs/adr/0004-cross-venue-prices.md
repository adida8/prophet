# ADR 0004 — Cross-venue prices on `MatchOutput` (non-US pivot)

- Date: 2026-05-30
- Status: Accepted
- Driver: Non-US sportsbook + exchange comparison surface
- Authority: `THE_DESK_SPEC.md` §6 (contract changes require an ADR),
  `THE_DESK_NONUS_SPORTSBOOK_SCOPING.md` §4

## Context

The site re-orients to non-US traffic. The comparison surface stops
being Polymarket-vs-Kalshi and becomes **Polymarket vs sportsbooks /
exchanges**.

Pre-pivot, the contract carried one venue per fixture: the verdict's
`market_venue` / `market_url` / `price`, populated only on a Pick.
That's the **single** venue whose price the Pick rode on. Everything
else the engine knows about the market — that William Hill's line is
the cheapest place to act, that Pinnacle is the sharp anchor's fair
opinion, that Betfair's price is best on the exchange — is dropped at
publish time.

The product story explicitly requires it on the page (see
`desk-comparison-mockup.html`): one row per side per venue, with the
**true price** (`e`) marked, the venue's de-vigged opinion (`fair_p`)
in a column, and a "best place to act" badge.

That requires a contract extension.

## Decision

Two additive top-level additions to `MatchOutput`:

```python
class MarketPriceVenue(BaseModel):
    venue:        str                                    # "pinnacle", etc.
    name:         str                                    # display name
    venue_type:   Literal["sportsbook","exchange","prediction_market"]
    region:       Optional[str]                          # "uk", "eu", "global"
    decimal_odds: Optional[float]                        # raw quote, books only
    implied_p:    float                                  # naive implied
    true_price:   Optional[float]                        # `e` per scope §2
    fair_p:       Optional[float]                        # multiplicative de-vig
    overround:    Optional[float]                        # per-venue margin
    is_best:      bool = False                           # cheapest by true_price

class MarketPriceRow(BaseModel):
    side:   Literal["a","draw","b"]
    venues: list[MarketPriceVenue]

class MatchOutput(BaseModel):
    ...
    market_prices:  list[MarketPriceRow] = []   # one row per side
    consensus_fair: Optional[dict[Literal["a","draw","b"], float]] = None
    region:         Literal["us","non-us"] = "non-us"
```

Plus an **additive** extension of `MarketVenue` to include the launch
non-US venues — `pinnacle`, `betfair_ex_uk`, `betfair_ex_eu`,
`williamhill`, `skybet`. Existing consumers that pattern-match the
enum will see new values; they can ignore unknown keys.

### Placement: top-level, parallel to `market_sources`

`market_sources` (ADR 0003) describes which venues we surface a CTA
for. `market_prices` describes the actual numbers each of those
venues quoted into the calculation. The split keeps the CTA row
renderable independent of whether we ingest prices from a venue
(some venues are link-only).

### `is_best` is computed by the publisher

`is_best` is derived: for each side, the venue with the lowest
`true_price` (or lowest `implied_p` when `true_price` is None
everywhere) is flagged. At most one `is_best=true` per side.

### `consensus_fair` is the narrative number

A sharp-weighted blend of per-venue `fair_p` (see
`desk/pricing/consensus.py`). Drives the "market consensus" line in
the blurb. Empty when fewer than two venues priced the same side, or
when `fair_p` is missing on every row (e.g. legacy Polymarket-only
fixtures).

### `region` is a publisher-level tag

`us | non-us`. Lets the front-end serve a different venue row per
geography without re-deriving from the URL list. Defaults to `non-us`
because that's the launch bucket.

## Detection / production

`desk/desk/publish/market_prices.py:build_market_prices(snapshot)`
emits the rows. `FootballSport.decide_and_explain` returns the list
as a 6th tuple element; the runner threads it onto
`MatchOutput.market_prices`. The publisher backfills `is_best` per
side from the row.

Flag-gated: with `DESK_CROSS_VENUE_EDGE=0` (the default and the
backtest-byte-identical path), the runner emits `market_prices=[]`
and `consensus_fair=None`. The contract field stays optional, so
unenriched fixtures don't regress.

## Invariants

1. Each side appears at most once in `market_prices`.
2. At most one `is_best=true` venue per side; `is_best=false` on every
   venue when `true_price` is None across the side.
3. `consensus_fair`'s keys are a subset of `market_outcomes`.
4. `market_prices=[]` is a legal payload (legacy + flag-off).

## Consumer migration

- Purely additive. Consumers that ignore unknown fields need no
  change.
- Pydantic / Zod validators with `extra="forbid"` / `.strict()` must
  add the four optional fields (`market_prices`, `consensus_fair`,
  `region`) before they'll accept new payloads. `market_prices` and
  `consensus_fair` may be `[]` / `null` on legacy payloads.
- The `MarketVenue` enum grows by five values. Consumers that
  pattern-match the enum can either:
  - Treat unknown enum values as opaque (preferred) and rely on
    `market_sources[].name` for display.
  - Map the new values to display labels themselves; the engine
    publishes `MarketPriceVenue.name` to make this a one-line lookup.
- The JSON Schema at `desk/contract.schema.json` is regenerated as
  part of this change; the in-sync test
  (`tests/test_contract.py::test_schema_file_in_sync`) enforces it.

## Alternatives considered

- **Per-venue prices inside `verdict`**. Rejected: `verdict` is the
  call; the venue-by-venue numbers are inputs to the call and must
  survive pass/avoid/withdrawn where `verdict` carries no venue.
- **Wider `MarketSource` carrying prices**. Rejected for v1:
  `MarketSource` is the CTA row (designed to render a button); mixing
  per-side prices into the same shape muddles "render this button"
  with "render this comparison cell". Keeping them parallel lets each
  evolve independently.
- **Free-form `venue: str` instead of growing the enum**. Rejected:
  the enum still gates `verdict.market_venue`, and silently allowing
  any string there opens the door to publish-time typos that we'd
  rather catch at validation.
- **Region encoded into `market_id`**. Rejected: the same match has
  the same id on both buckets; the bucket changes only what we
  surface, not what we identify.

## References

- `desk/desk/publish/contract.py` — `MarketPriceVenue` +
  `MarketPriceRow` + `MatchOutput.market_prices` / `consensus_fair` /
  `region`
- `desk/desk/publish/market_prices.py` — `build_market_prices`
- `desk/desk/sports/football/oddsapi_prices.py` —
  `venue_prices_from_oddsapi` + `enrich_polymarket_venue_prices`
- `desk/desk/sports/football/sport.py` — returns it from
  `decide_and_explain`
- `desk/desk/runner.py` — threads it onto the published `MatchOutput`
- `desk/CONTRACT_CHANGELOG.md` — public changelog entry
- `desk/contract.schema.json` — regenerated schema
- `THE_DESK_NONUS_SPORTSBOOK_SCOPING.md` — methodology + worked example
