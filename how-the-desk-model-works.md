# How the desk model works

A pipeline-level walkthrough of the Python service under `desk/` — every stage, every transform, every constant, the order they run in, what happens when each gate fires. Read this when you need to reason about *why* the engine produced (or didn't produce) a particular verdict.

This doc is the model-internals counterpart to [docs/desk-integration.md](./desk-integration.md) (which covers the Vercel ↔ Railway wire-level seam). It is reference, not plan — for new-shape proposals (outrights, tennis), see `tasks/research/`.

---

## 1. The pipeline in one diagram

```
                  Vercel cron tick (every 30 min)
                              │
                              ▼
   POST /api/notify-tick { schema_version: 1, kind: 'tick', ... }
                              │
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ Railway (Python)                                              │
   │                                                              │
   │  /api/notify-tick handler  →  enqueue process_event per      │
   │                                event that changed since      │
   │                                Railway's own watermark        │
   │                                                              │
   │  process_event(event_id):                                    │
   │   ┌── Stage 1: anon REST read ─────────────────────────┐     │
   │   │  GET /rest/v1/events?id=eq.<uuid>&select=          │     │
   │   │      *,markets(*,outcomes(*))                       │     │
   │   │  → row | None                                       │     │
   │   └─────────────────────────────────────────────────────┘     │
   │                       │                                       │
   │   ┌── Stage 2: shape  ▼ ────────────────────────────────┐    │
   │   │  fixture_and_snapshot_from_row(row)                  │    │
   │   │   → (FixtureRef, MarketSnapshot) | None              │    │
   │   └──────────────────────────────────────────────────────┘    │
   │                       │                                       │
   │   ┌── Stage 3: feature build ▼ ─────────────────────────┐    │
   │   │  build_features(fx)                                  │    │
   │   │   → FootballFeatures (Elo, venue, altitude, ...)     │    │
   │   └──────────────────────────────────────────────────────┘    │
   │                       │                                       │
   │   ┌── Stage 4: model  ▼ ─────────────────────────────────┐   │
   │   │  compute(features)                                    │   │
   │   │   → ModelOutput (p_a, p_draw, p_b + 90% band)        │   │
   │   └───────────────────────────────────────────────────────┘   │
   │                       │                                       │
   │   ┌── Stage 5: decide ▼ ─────────────────────────────────┐   │
   │   │  decide(model_p, market, sides, ...)                  │   │
   │   │   → Verdict { state, side, price, edge_pp, ... }     │   │
   │   └───────────────────────────────────────────────────────┘   │
   │                       │                                       │
   │   ┌── Stage 6: explain ▼ ────────────────────────────────┐   │
   │   │  build_copy(...)                                      │   │
   │   │   → Copy { title, summary, blurb, drivers, citations }│  │
   │   └───────────────────────────────────────────────────────┘   │
   │                       │                                       │
   │   ┌── Stage 7: publish ▼ ────────────────────────────────┐   │
   │   │  HttpPublisher.publish(DeskContentPublish)            │   │
   │   │   POST <vercel>/api/desk/publish (Bearer)             │   │
   │   └───────────────────────────────────────────────────────┘   │
   └──────────────────────────────────────────────────────────────┘
```

Per-event failure isolation: any exception inside Stage 2–7 returns None and is logged — never re-raised to the FastAPI handler. The notify-tick is a fire-and-forget heartbeat; the next tick gets a fresh chance.

---

## 2. Stage 1 — anon REST read

[desk/desk/ingest/market_tips_ai.py:95-120](../desk/desk/ingest/market_tips_ai.py#L95-L120)

The Python service holds the Supabase **anon key only** — by contract, never a service-role key. The read is one HTTPS GET against PostgREST:

```
GET /rest/v1/events
    ?id=eq.<uuid>
    &select=*,markets(*,outcomes(*))
    &limit=1
```

The nested `select` pulls the event row, every child `markets` row, and every grandchild `outcomes` row in one round trip. Filtering deleted children is done **client-side** in Stage 2 — PostgREST embedded filtering is awkward via raw query strings.

RLS gates this read: anon callers see rows where `status IN ('active', 'closed') AND deleted_at IS NULL` (per `0011_events_markets.sql:494-497`). Drafts and resolved events return as `None`. The handler treats `None` as "nothing to publish" and short-circuits — same posture as a soft error.

---

## 3. Stage 2 — adapter (Supabase row → FixtureRef + MarketSnapshot)

[desk/desk/sports/football/supabase_fixtures.py](../desk/desk/sports/football/supabase_fixtures.py)

Two transforms in one entry point: `fixture_and_snapshot_from_row(row)`. Returns `None` whenever the row can't be cleanly shaped.

### 3.1 Title parsing (matchup identity)

`parse_title()` (from `desk/desk/ingest/polymarket.py`) splits `events.title` on `" vs. "` — designed for Polymarket-shaped questions like `"France vs. Mexico"`. If the split doesn't yield exactly two non-empty halves, the adapter returns `None`. **This is why the desk is structurally match-only today** — the regex bakes in the two-team assumption.

### 3.2 Kickoff resolution

`kickoff_utc = end_time OR start_time`. PostgREST renders `timestamptz` as `YYYY-MM-DDTHH:MM:SS+00:00`; the adapter also tolerates the `Z` suffix. Missing kickoff → `None`. The model and verdict steps require a kickoff for ordering / staleness, so this is a hard gate.

### 3.3 Competition resolution

[supabase_fixtures.py:110-144](../desk/desk/sports/football/supabase_fixtures.py#L110-L144). Three-step ladder:

1. **Slug regex** — `parse_slug()` matches Polymarket's `<prefix>-<homeshort>-<awayshort>-<yyyy-mm-dd>` shape. If the prefix maps via `teams.py:_COMPETITION_MAP`, return `(spec_code, label)` (e.g. `"fifwc"` → `("wc26", "FIFA World Cup 2026")`).
2. **Tag scan** — fall through `events.tags` looking for any tag that maps.
3. **Fallback** — `("unknown", "Unknown")`. The model degrades gracefully because the verdict step's stub-Elo guard kicks in (§7.1).

`teams.py` carries the alias dictionary — Polymarket's `kr` → spec `kor` for South Korea, etc.

### 3.4 match_id construction

[desk/desk/sports/football/fixtures.py:make_match_id]. Format `{sport_short}-{competition}-{home_short}-{away_short}-{yyyymmdd}`. Regex enforced at the contract layer: `^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$`.

The short-form for each team comes from `normalize_team(<hint>, is_national=international)`. The hint is the Polymarket slug fragment when available; falls back to the lowercased display name with spaces stripped. This is why the same fixture from two different sources can produce two different `match_id`s — the desk treats them as separate matches and dedupes on `event_id` at publish time, not on `match_id`.

### 3.5 Price extraction → MarketSnapshot

[supabase_fixtures.py:234-273](../desk/desk/sports/football/supabase_fixtures.py#L234-L273). For each non-deleted child market under the event:

1. **Classify the market by question.** The market's `question` text is accent-stripped + lowercased, then matched against the two team names (also accent-stripped):
   - Contains `"draw"` or `"end in a draw"` → side `'draw'`.
   - Contains team A's name but not team B's → side `'a'`.
   - Contains team B's name but not team A's → side `'b'`.
   - Otherwise skip.
2. **Find the YES outcome.** Prefer `outcomes.side = 'yes'`, fall back to `position_index = 0`. Read `last_price_cents` (int in [0, 100]); skip if missing.
3. **Compute implied probability.** `implied_p = cents / 100.0`. Reject anything outside [0, 1].
4. **Emit `VenuePrice(venue, side, implied_p)`** where `venue` is the market's `provider` field (`"polymarket"` / `"kalshi"`).

The final `MarketSnapshot` carries an `asof` timestamp (parsed from `events.last_synced_at` or `updated_at`) used by the staleness gate downstream.

---

## 4. Stage 3 — feature builder

[desk/desk/sports/football/features_builder.py](../desk/desk/sports/football/features_builder.py)

`build_features(fx)` turns a `FixtureRef` into a `FootballFeatures` row by joining four side tables.

### 4.1 Competition kind → Elo source

[features_builder.py:57-75](../desk/desk/sports/football/features_builder.py#L57-L75). `is_international_competition()` is a hard-coded allowlist of national-team competitions: `wc26, wc22, wc18, euro, copa, afcon, asian-cup, wwc, olympics-football`. Everything else (EPL, La Liga, UCL, MLS, …) is a club competition.

For international fixtures, both teams' ISO3 codes are pulled from the `match_id` (positions -3 and -2). `national_elo(iso3)` returns the team's Elo, defaulting to **1500.0** when the ISO3 is unknown. `national_elo_source(iso3)` returns `"wiki"` (a real source) or `"stub"` (the 1500 default).

For club fixtures, `_club_id_from_match_id()` currently **always returns None** (TODO: PR 4.5 — `features_builder.py:54`). That means every club fixture's Elo is 1500-vs-1500, source `"stub"`, and the verdict step's stub-Elo guard forces Pass. **Today, the engine produces actionable Picks only on international fixtures with mapped ISO3 codes.**

### 4.2 Venue / host / altitude

[features_builder.py:77-101](../desk/desk/sports/football/features_builder.py#L77-L101). Only fires for international fixtures (the host-bonus is a tournament concept). Looks up `host_iso3_for_competition(comp_code)` against a static FIFA table; resolves `venue_for_match(comp_code, stadium)` for altitude.

**In practice this rarely fires** — Polymarket's gamma payload doesn't carry per-fixture stadium data, so `fx.venue_stadium` is almost always `None` for live ingest. The host bonus only fires when the venue country resolves via `WC26_VENUES` (which is the only populated venue table today). Backtest-replay paths populate venue from a separate FIFA fixture-map table.

### 4.3 Home-ground / altitude-acclimatised

Home-ground bonus is a club concept (`features_builder.py:104-115`). Because `_club_id_from_match_id` returns None, `team_*_home_ground` is always `None` today and the home bonus never fires.

`is_altitude_acclimatised(iso3)` is a small allowlist (Bolivia, Ecuador, Peru, Mexico, Colombia, …) — fires when the venue altitude exceeds 1000m. In practice the WC 2026 venues that exceed 1000m are Mexico City and a couple of US cities; otherwise inert.

### 4.4 Resulting feature row

```python
FootballFeatures(
  team_a_name, team_b_name,
  team_a_elo, team_b_elo,                    # 1500 stub-default if no source
  is_international,
  team_a_iso3, team_b_iso3,                  # national-only
  venue_host_iso3,                           # ISO3 when stadium resolves
  team_a_home_ground, team_b_home_ground,    # club-only, always None today
  venue_stadium, venue_altitude_m,
  team_a_altitude_acclimatised, team_b_altitude_acclimatised,
  team_a_elo_source, team_b_elo_source,      # "wiki" | "clubelo" | "stub"
)
```

---

## 5. Stage 4 — the model

[desk/desk/sports/football/model.py](../desk/desk/sports/football/model.py)

The math is **deliberately small**. Per the file header: "The engine's edge comes from clean data plumbing and the late-binding feature ladder, not from a clever model."

### 5.1 Tunable constants

[model.py:42-71](../desk/desk/sports/football/model.py#L42-L71). Hard-coded at v1 defaults:

| Constant | Value | Meaning |
|---|---|---|
| `HOST_BONUS_ELO` | 75.0 | Elo uplift for a national side playing in the host country (international only). |
| `HOME_GROUND_BONUS_ELO` | 60.0 | Elo uplift for a club at its registered home stadium (club only). |
| `ALTITUDE_BONUS_ELO_PER_1000` | 50.0 | Per-1000m above threshold, applied to the side flagged altitude-acclimatised. |
| `ALTITUDE_THRESHOLD_M` | 1000.0 | Altitude bonus only fires above this. |
| `DRAW_PEAK` | 0.30 | Draw share when |Elo diff| = 0. |
| `DRAW_FLOOR` | 0.10 | Floor on draw share even at large Elo gaps. |
| `DRAW_DECAY_PER_ELO` | 0.0006 | 100 Elo diff → -0.06 to draw share. |
| Bootstrap: `BOOTSTRAP_N` | 100 | Samples for the 90% confidence band. |
| Bootstrap: `ELO_PERTURBATION` | 50.0 | ± uniform half-width on each team's Elo per sample. |
| Bootstrap: `HOST_BONUS_PERTURBATION` | 15.0 | ± half-width on host bonus. |
| Bootstrap: `HOME_BONUS_PERTURBATION` | 15.0 | ± half-width on home-ground bonus. |
| Bootstrap: `ALTITUDE_BONUS_PERTURBATION` | 10.0 | ± half-width on altitude bonus per 1000m. |

`ELO_PERTURBATION = 50` was raised from 20 after WC 2022 backtest showed a 77% Pick rate at ±20 — too aggressive. ±50 brought selection back inside the 5–20% editorial target.

### 5.2 Point-estimate computation

`compute(features)` in 4 steps:

**Step 1 — Adjusted Elo** (`_adjusted_elos`, [model.py:171-224](../desk/desk/sports/football/model.py#L171-L224))

Start from `base_elo_a`, `base_elo_b`. Then:

- If `is_international` and `venue_host_iso3` is set, add `HOST_BONUS_ELO` to whichever side's `iso3` matches the host. Either side, both sides, or neither can fire — the bonus is asymmetric by design (only the actual host country gets it).
- Else (clubs), apply `HOME_GROUND_BONUS_ELO` to whichever side's `home_ground` matches `venue_stadium` (case-insensitive trim).
- Altitude: if `venue_altitude_m > 1000`, compute `bonus = ALTITUDE_BONUS_ELO_PER_1000 * (alt - 1000) / 1000`. Apply to either or both sides depending on `altitude_acclimatised` flag.

Host and home-ground are mutually exclusive (international XOR club). Altitude is independent.

Each fired bonus appends a `Driver` row that the explainer reads to populate the "Why this call?" bullets.

**Step 2 — Probability triplet** (`_probs_from_elos`, [model.py:227-236](../desk/desk/sports/football/model.py#L227-L236))

The classic Elo logistic plus a draw-decay curve:

```python
diff       = elo_a - elo_b
expected_a = 1.0 / (1.0 + 10 ** (-diff / 400))      # Elo expected score
p_draw     = max(DRAW_FLOOR, DRAW_PEAK - DRAW_DECAY_PER_ELO * abs(diff))
win_share  = 1.0 - p_draw
p_a        = expected_a * win_share
p_b        = (1.0 - expected_a) * win_share
# Then re-normalise: divide each by (p_a + p_draw + p_b) for floating-point safety.
```

In plain English: Elo gives the pairwise win-share (ignoring draws); the draw share is carved out of that 100% pool with a function that peaks at 30% when the teams are equal and decays to a 10% floor as the Elo gap widens.

A 100-Elo gap reduces draw share by 6pp (`DRAW_DECAY_PER_ELO = 0.0006`). A 500-Elo gap drops draw share by 30pp, hitting the 10% floor.

**Step 3 — Confidence band (Phase A.1)** (`_confidence_band`, [model.py:276-334](../desk/desk/sports/football/model.py#L276-L334))

A 100-sample bootstrap. Each sample independently perturbs:

- Each team's Elo by `uniform(±50)`.
- The host bonus by `uniform(±15)`.
- The home-ground bonus by `uniform(±15)`.
- The altitude bonus rate by `uniform(±10)`.

For each sample, re-run `_adjusted_elos` then `_probs_from_elos`. Collect 100 triplets, sort, take the 5th and 95th percentiles per side → `p_a_lower, p_a_upper, p_draw_lower, p_draw_upper, p_b_lower, p_b_upper`.

Per-match seed is deterministic (MD5 of feature fields), so the band is reproducible — two runs of the same fixture produce identical bounds. This matters for backtest diff stability and for downstream verdict determinism.

**Step 4 — Output**

`ModelOutput(p_a, p_draw, p_b, elo_a_adj, elo_b_adj, drivers, *_elo_source, p_*_lower, p_*_upper)`.

### 5.3 What's deliberately weak

- **Draw model is a one-parameter ad-hoc curve.** Not learned, not calibrated. The 30% peak / 10% floor / -0.06 per 100 Elo numbers are eyeball-fit. The match-result distribution of European leagues is closer to (45%, 25%, 30%); the model overstates draws in low-Elo-gap matches and understates them in mid-gap matches. This is a known cost in exchange for never going off the rails.
- **No form, no injuries, no rest, no h2h.** Only Elo + venue + altitude. The whole story.
- **Elo is from a static table.** No live update from match outcomes. The next-version data pipeline (Wiki / ClubElo live ingest) is the lever that unlocks the model — not the model maths.

---

## 6. Stage 5 — decide (Pick / Pass / Avoid)

[desk/desk/verdict/decide.py](../desk/desk/verdict/decide.py)

`decide(model_p, market, sides, team_a, team_b, ...)` runs the threshold ladder against a list of sanity gates.

### 6.1 Sanity gates (all force Pass)

Run in order:

1. **Stub-Elo gate** (`decide.py:102-104`): if either team's `elo_source == "stub"`, return Pass. This is why every club fixture today returns Pass — `_club_id_from_match_id` always returns None, so club Elo is always stub.

2. **Liquidity gate** ([liquidity.py:47-71](../desk/desk/verdict/liquidity.py#L47-L71)): reject when any side has best implied probability `≤ 0.02` or `≥ 0.98`. The rationale: Polymarket sometimes quotes a side at +9999 / -9999 (~1% / ~99%) when it's not willing to express a view; treating those as legitimate signals would issue confident Picks against prices the venue itself doesn't believe.

3. **Market coverage** (`decide.py:112-115`): every side needs at least one venue quote. If any side has no best-price across venues, return Pass.

4. **`market_url` must exist** (`decide.py:138-139`): a Pick without a venue deep-link is unusable for the CTA, so the engine downgrades to Pass rather than violate the contract.

### 6.2 Edge computation

For each side `s` in `("a", "draw", "b")`:

```python
best_for_s = market.best_for(s)              # min(implied_p across venues) — best for the bettor
edge_pp[s] = (model_p[s] - best_for_s.implied_p) * 100
```

"Best" for the bettor = **lowest implied probability** = highest payout. Multi-venue is the whole point: cross-comparison lets a Pick fire when one venue is offering odds the other isn't.

### 6.3 Pick — Phase A.3 lower-bound gate

[decide.py:117-149](../desk/desk/verdict/decide.py#L117-L149). When `model_p_lower` is supplied (it always is, from the bootstrap), a Pick fires **only when the lower bound of the model's probability** clears the threshold against the market:

```python
(model_p_lower[s] - market_p[s]) * 100 >= pick_pp   # pick_pp = 3.0 by default
```

Not the point estimate. This is the "honest about uncertainty" gate: a model with a wide band on a side fails the lower-bound test even when its point estimate looks attractive.

Among candidates that pass, the side with the **highest point-estimate edge** wins. Ties are resolved by max edge (`max(...)` is stable on lists). Pick wins all ties with Pass / Avoid — it's the only state with a CTA, so we take it whenever it's available.

The resulting `Verdict`:

```python
Verdict(
  state = PICK,
  side = "France" | "Mexico" | "draw",                  # team name, not "a"/"b"
  market_venue = "polymarket" | "kalshi",               # venue offering the best price
  price = "+220" | "-180",                              # American-odds string
  edge_pp = 4.2,                                        # point-estimate edge, rounded to 2dp
  market_url = "https://polymarket.com/event/<slug>",
  model_p = 0.34, market_p = 0.22,                      # raw probabilities for B2C render
)
```

### 6.4 Avoid

If **every** side's edge ≤ `avoid_pp` (-1.5 default), return Avoid with `edge_pp` set to the most-negative side's edge.

In practice the Avoid rule **never fires on single-venue data** — per side, `p_a + p_draw + p_b = 1` and `market_p_a + market_p_draw + market_p_b ≥ 1` (overround), so the per-side edges sum to ≤ 0, which means at least one side has positive edge. The rule is structural-impossible on a single-venue backtest. It only activates in multi-venue live where `sum(best_for(side)) < 1` (each side's best price is on a potentially different venue, the implicit overround disappears, and the per-side edges shift up).

The Avoid threshold was relaxed from -2.0 to -1.5 in Phase A.4 with this in mind. A proper redefinition (`max-side edge ≤ avoid_pp`, or a distortion metric) is tracked as a v1.2 ADR.

### 6.5 Pass

Default — anything that's not a Pick or Avoid. Includes the "all sides within ±pass_pp" case (`pass_pp = 1.0` default).

---

## 7. Stage 6 — explainer

[desk/desk/explainer/](../desk/desk/explainer/)

v1 is **template-driven, not LLM-driven**. `build_copy(ctx)` produces a `Copy` with:

- `title` (≤ 120 chars) — e.g. `"Edge on France at Polymarket"` for a Pick, `"No edge on France vs Mexico"` for a Pass.
- `summary` (≤ 400 chars) — one-paragraph rationale.
- `blurb` (≤ 1200 chars) — fuller body that lands in `event_contents.article_body`.
- `drivers` (≤ 6 bullets) — pulled from the model's driver-attribution list (host bonus, home-ground bonus, altitude bonus). Each bullet is a short sentence the B2C renders above the CTA.
- `citations` — empty in v1 (templated paths don't cite). The shape is reserved for the Haiku-driven replacement.

Voice rules ([explainer/voice.py](../desk/desk/explainer/voice.py)) enforce the editorial tone — short sentences, no jargon, no betting-handle clichés. PR 5 in the original roadmap was to swap templates for Anthropic Haiku output; that swap is still pending and is tracked under `tasks/research/TASK-276-desk-python-audit.md`.

---

## 8. Stage 7 — publish

[desk/desk/publish/http_publisher.py](../desk/desk/publish/http_publisher.py), [desk/desk/process_event.py:189-237](../desk/desk/process_event.py#L189-L237)

`_build_publish_payload` marshals the Verdict + Copy + Fixture into a `DeskContentPublish` Pydantic model. The wire fields:

| Wire field | Source |
|---|---|
| `event_id` | the Supabase UUID (canonical identity, NOT match_id) |
| `verdict` | one-line human render: `"Pick France (polymarket +220, edge +4.2pp) — France vs Mexico."` Fallback for B2C clients that don't read the structured columns. |
| `article_body` | `copy.blurb` when present, else `copy.summary`, else the templated verdict text. `min_length=1` is contract-enforced so a Pass with empty blurb still publishes. |
| `sources` | `copy.citations` mapped to `[{title, url}]` — interim shim derives `title` from URL netloc (per TASK-276 P1). |
| `confidence` | `None` in v1 (no calibrated value yet). |
| `model_id` | `"desk-football-v1"` — a static tag that lets the operator filter `event_contents` by engine version when v2 ships. |
| `generated_at` | UTC timestamp at publish time. |
| `verdict_state` | `"pick" \| "pass" \| "avoid"` |
| `verdict_side` | team name or `"draw"`; null on pass/avoid |
| `verdict_market_venue` | `"polymarket" \| "kalshi"`; null on pass/avoid |
| `verdict_price` | American-odds string; null on pass/avoid |
| `verdict_edge_pp` | numeric edge; populated on Pick (positive) and Avoid (negative) |
| `copy_title` / `copy_summary` | from `Copy` (empty strings → null at the seam) |

Then HTTP POST to `${DESK_PUBLISH_URL}` (`https://markettipsai.com/api/desk/publish` in prod), `Authorization: Bearer ${DESK_PUBLISH_TOKEN}`, body = the Pydantic model serialised. Vercel side re-validates with Zod ([lib/desk/contract.ts:deskContentPublishSchema](../lib/desk/contract.ts)), inserts into `event_contents` via the service-role admin client, and revalidates the B2C path.

Failure handling: 400 (Zod failure → contract drift, retry-after-fix), 401 (bad token), 429 (rate-limited), 500 (DB failure — sanitised error, full detail in logs). All paths log + return None at the Python side; nothing throws back to the FastAPI handler.

---

## 9. Worked example — France vs Mexico, WC 2026 group stage

Hypothetical, illustrative. Real numbers depend on live prices.

### 9.1 Adapter output

```python
FixtureRef(
  match_id          = "fb-wc26-fra-mex-20260612",
  sport             = "football",
  competition_code  = "wc26",
  competition_label = "FIFA World Cup 2026",
  team_a            = "France",
  team_b            = "Mexico",
  kickoff_utc       = 2026-06-12T20:00:00Z,
  market_outcomes   = ("a", "draw", "b"),
  source_event_slug = "fifwc-fra-mex-2026-06-12",
  source_venue      = "polymarket",
)

MarketSnapshot(
  asof = 2026-05-14T14:00:00Z,
  prices = (
    VenuePrice("polymarket", "a",    0.55),
    VenuePrice("polymarket", "draw", 0.25),
    VenuePrice("polymarket", "b",    0.20),
    VenuePrice("kalshi",     "a",    0.57),
    VenuePrice("kalshi",     "draw", 0.24),
    VenuePrice("kalshi",     "b",    0.21),
  ),
)
```

`best_for("a") = polymarket@0.55` (the bettor wants the lower implied price). Same logic for the other sides.

### 9.2 Feature row

```python
FootballFeatures(
  team_a_elo = 2050,  team_b_elo = 1820,        # from data/elo_seed.py — Wiki source
  team_a_elo_source = "wiki",  team_b_elo_source = "wiki",
  is_international = True,
  team_a_iso3 = "fra",  team_b_iso3 = "mex",
  venue_host_iso3 = None,                       # Polymarket payload has no stadium
  venue_altitude_m = None,
  team_a_altitude_acclimatised = False,
  team_b_altitude_acclimatised = True,          # Mexico — but no altitude flag fires
)
```

### 9.3 Adjusted Elo

No host bonus (no stadium known), no altitude bonus. Adjusted = base.

`diff = 2050 - 1820 = 230`.

### 9.4 Probability triplet

```
expected_a = 1 / (1 + 10^(-230/400)) ≈ 0.789
p_draw     = max(0.10, 0.30 - 0.0006 * 230) = 0.30 - 0.138 = 0.162
win_share  = 1 - 0.162 = 0.838
p_a        ≈ 0.789 * 0.838 ≈ 0.661
p_b        ≈ 0.211 * 0.838 ≈ 0.177
# After re-normalisation: p_a ≈ 0.661, p_draw ≈ 0.162, p_b ≈ 0.177.
```

### 9.5 Confidence band

Run 100 bootstrap samples with ±50 Elo perturbation per team. The Elo gap is wide (230), so:

- Low samples: `(2050-50) vs (1820+50)` → diff 130 → `p_a ≈ 0.535`.
- High samples: `(2050+50) vs (1820-50)` → diff 330 → `p_a ≈ 0.764`.

After sorting and taking the 5th percentile, `p_a_lower ≈ 0.57`.

### 9.6 Edges

```
edge_a    = (0.661 - 0.55) * 100 = +11.1pp
edge_draw = (0.162 - 0.24) * 100 = -7.8pp
edge_b    = (0.177 - 0.20) * 100 = -2.3pp
```

### 9.7 Lower-bound Pick check

For side `a`: `(p_a_lower - market_p_a) * 100 = (0.57 - 0.55) * 100 = +2.0pp`.

Threshold is `pick_pp = 3.0`. **Lower bound does NOT clear the threshold.** No Pick fires.

(If the Elo gap were narrower or the model's variance lower, the lower bound would lift over the threshold and a Pick would fire.)

### 9.8 Avoid check

Not every side ≤ -1.5pp (side `a` is +11.1pp). No Avoid.

### 9.9 Verdict

```python
Verdict(state=PASS, market_url="https://polymarket.com/event/fifwc-fra-mex-2026-06-12")
```

The point estimate said "huge edge on France"; the confidence band said "the model isn't that sure." Pass. This is the lower-bound gate doing exactly what it's designed to do.

---

## 10. What's deliberately small / weak

Calibration honesty list:

1. **Static Elo table.** No live update from match outcomes. Stale Elo is the largest known source of mis-calibration.
2. **No club Elo wired.** `_club_id_from_match_id` returns None. Every club fixture is stub-Elo → forced Pass at the verdict step. The desk produces zero club Picks today.
3. **Venue / stadium data is missing on live ingest.** Polymarket's payload doesn't carry stadium info, so host / home-ground / altitude bonuses almost never fire in prod. Backtest replays use a separate FIFA fixture-map.
4. **Draw model is ad-hoc.** Not learned, not calibrated. Overstates draws in low-gap matches.
5. **No form, no injuries, no rest, no h2h.** Only Elo + venue + altitude.
6. **Avoid rule is structurally impossible on single-venue snapshots.** It only fires when cross-venue best-price overround flips negative. v1.2 ADR will redefine.
7. **Explainer is templated.** Haiku swap pending (TASK-276).
8. **Confidence band is bootstrapped from a coarse perturbation, not a fitted variance.** Bounds are honest about "this Elo could be ±50 off" but not calibrated against actual prediction error.

The strategic bet: do the data plumbing right (clean ingest, well-typed adapter, deterministic seeds, lockstep contract), and the model becomes the lever you pull when you have a credible reason to pull it. Don't get cute with a weak model on dirty data.

---

## 11. Cross-references

- [docs/desk-integration.md](./desk-integration.md) — Vercel ↔ Railway wire seam, env vars, deploy ordering. Read first for operational context.
- [tasks/research/TASK-276-desk-python-audit.md](../tasks/research/TASK-276-desk-python-audit.md) — Python-side action list: HTTP publish (done), DB-read posture (done), Haiku explainer (pending), structured sources (pending).
- [tasks/research/TASK-311-desk-outrights-plan.md](../tasks/research/TASK-311-desk-outrights-plan.md) — proposal to extend the engine to N-way outright markets.
- [desk/THE_DESK_SPEC.md](../desk/THE_DESK_SPEC.md) — original engine spec; details on the threshold ladder rationale, the contract design, and the editorial voice.
- [desk/THE_DESK_OPTIMIZATION_SPEC.md](../desk/THE_DESK_OPTIMIZATION_SPEC.md) — Phase A.x optimization notes; the confidence-band gate, the Avoid-threshold relaxation, and the bootstrap parameter choices originate here.
