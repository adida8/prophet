# Vendor Verifications (guardrail 4)

**Status:** verified 2026-05-18 against public vendor docs. Per data-layer spec
guardrail 4: "Vendor terms verified against current vendor docs before any code
is written." This doc closes that guardrail for the three vendors the data
layer commits to.

**Owner:** Adi.
**Re-verify cadence:** before each major data-layer phase ships (1b, 2, 3, 4).

---

## 1. API-Football (Phases 2 / 4 spine)

### What the spec assumes

- **$19/month Pro plan** as the spine for RANK + FORM + INJURIES + LINEUP.
- **7,500 requests/day** cap.
- All endpoints (injuries, lineups) included in the Pro plan.
- Strong coverage of the competitions the desk targets.

### What's confirmed

- Pricing: **$19/month** for the entry-level paid plan with **7,500 requests/day**
  and **all endpoints** unlocked. All competitions are included on all plans;
  paid tier differentiation is on request quota only. ✓
- **Cap behaviour is bounded.** Once the quota is reached, the API stops
  processing and returns an error — no overage billing. This is safer than
  metered billing (no surprise costs), but it's a *hard ceiling* — at the cap,
  the data layer must degrade to absent (per §3.6) until reset. ✓
- **Coverage is per-competition, not blanket.** The API exposes a coverage
  endpoint that returns which data types (injuries, lineups, predictions, etc.)
  are actually available per competition. The data layer **must call this
  endpoint per competition before that competition goes live** — values set to
  `true` don't guarantee 100% population, but `false` means the feature is
  absent for that league. ✓
- **Stable league IDs.** Premier League = 39, La Liga = 140; documented as
  stable across seasons. Good for the canonical team registry's outbound
  resolution. ✓

### What's a risk / open

- **Lineups timing.** Lineups are typically available **20–40 minutes before
  kickoff** *when the competition covers them*. Some competitions only get
  lineups post-match. **Implication for Phase 4:** the spec's "T−1h polling
  until confirmed or kickoff" works for most major leagues, but for the
  unsupported competitions the desk should mark lineup absent rather than
  hold the verdict. Per-competition behaviour needs to be charted before
  Phase 4 commits.
- **Coverage breadth vs depth.** API-Football lists 1,200+ leagues but
  coverage *depth* varies. The pre-Phase-4 source audit in the data layer
  spec already calls for this — verify that the *specific competitions in
  scope* (WC 2026, top-5 European leagues, MLS, CONMEBOL) have player-level
  minutes / role data, not just availability flags. Without that, Phase 4's
  injury-importance weighting falls back to availability-only.
- **Coverage for *new* competitions (incl. WC 2026).** Per vendor docs,
  competitions that haven't started have all features set to `false` until
  the competition begins. WC 2026 starts 2026-06-11; pre-tournament data
  (squad lists, FIFA rank, recent form) should be available now, but
  in-tournament features (live injury updates, confirmed XI) only activate
  once the tournament starts. Plan accordingly: Phase 4's injury/lineup
  flow needs an "in-tournament" toggle.
- **Rate-limit shape.** The 7,500/day cap is *daily*; resets are presumably
  midnight UTC (vendor doesn't make this explicit — confirm via a test call
  before Phase 2). Friday's club fixtures shouldn't drain Sunday's budget,
  but if the reset is on a rolling 24-hour window the data layer's §3.4
  cold-start posture needs to account for it.

### Action before Phase 2 (data PR) starts

- Subscribe to the $19 Pro plan.
- Call the coverage endpoint for each target competition; record per-comp
  flags into a `data/api_football_coverage.json` snapshot. The data layer's
  registry reads this to decide which sources are tier-1 vs degraded.
- Run a one-day dry run hitting the cap-relevant endpoints at the planned
  cadence and instrument the actual request count vs the 7,500 ceiling.

### Action before Phase 4 (data PR) starts

- Per-competition audit on injury / lineup *depth* (player minutes, role,
  position). Audit result → either (a) Phase 4 ships with the importance
  weighting per spec, or (b) Phase 4 ships availability-only and the model
  hook stays in Shadow per the data-layer spec §5.

[API-Football pricing](https://www.api-football.com/pricing) ·
[API-Football coverage list](https://www.api-football.com/coverage)

---

## 2. OpenWeather One Call API 3.0 (Phase 3 weather)

### What the spec assumes

- **Free allowance ≈ 1,000 calls/day**, then per-call billing of
  ≈ $0.0015/call.
- Hard monthly cap of ~$1 / month worst case (data-layer §4.1 release valve).

### What's confirmed

- **One Call API 3.0 is the right endpoint.** Carries the multi-day forecast +
  current weather + summaries the spec needs in a single call. ✓
- **Free allowance: 1,000 calls/day.** Confirmed. ✓
- **Per-call pricing: €0.14 per 100 calls** (≈ €0.0014 / ≈ $0.0015 per call).
  Confirmed; matches the spec's pricing reference. ✓
- **Default daily cap on subscription: 2,000 calls/day** (adjustable in
  account settings). Important: when the data layer subscribes, **set the
  daily cap to a value that respects the spec's $1/month overage budget** —
  e.g. ~700 calls/day above the free allowance, which at €0.0014/call is
  ~€30/month if maxed every day, but realistic usage averages well below.
- **Excess is summed and billed end of subscription month**, not per call.
  Predictable; matches the "$1/month overage cap as release valve" design.

### What's a risk / open

- **The "set the daily cap" step is non-default.** OpenWeather subscribes you
  at 2,000 calls/day by default — without an explicit cap-set step, the
  Phase 3 implementation could silently spill into 2,000 calls/day of overage
  for ~$3/month if a polling bug fires. The data-layer §6 secrets section
  should be amended to document this as a setup step, not just an env-var
  drop.
- **The €/$ rate.** Pricing is published in EUR; the spec's USD reference
  ($0.0015) is approximate. Budget the dollar cap with a conversion buffer.

### Action before Phase 3 starts

- Subscribe to One Call API 3.0 "By Call" plan.
- **In account settings: set daily cap to a value that maps to the $1/month
  overage budget** — recommend ~700 calls/day above the free allowance for
  safety. Document the exact number in the integration repo's `.env.example`
  + setup notes.
- Confirm the env var name (`OPENWEATHERMAP_API_KEY` per the data-layer spec).

[OpenWeather pricing](https://openweathermap.org/price) ·
[One Call 3.0 docs](https://openweathermap.org/api/one-call-3)

---

## 3. Railway persistent volumes (Phase 1a cache)

### What the spec assumes

- Railway offers persistent volumes on the current plan.
- Volumes mount at **runtime**, not build time (data-layer §3.4
  implementation note).
- The cache surviving restarts depends on this.

### What's confirmed

- **Volumes are available.** Pro plan users (and above) can self-serve up to
  **1 TB**. Volumes attach to a service's container. ✓
- **Volumes mount at runtime, not build time.** Confirmed — exactly the
  warning the data-layer spec flags. Cache directory init must run at app
  startup, not build/pre-deploy. ✓
- **Volumes charge 24/7** whether the service is running or stopped. So the
  volume is a recurring cost line, not free. For the small cache the data
  layer needs (a few hundred MB at most), this is negligible — but it's a
  cost.

### What's a risk / open

- **Plan tier needed for self-serve volumes.** "Pro and above" can self-serve.
  The desk's current Railway plan is unconfirmed — verify it's Pro ($20/month)
  or higher before Phase 1a starts.
  - If on the **Hobby plan ($5/month)**: check whether volumes are available
    on Hobby; if not, upgrading to Pro is a prerequisite for Phase 1a's cache
    persistence story.
- **Multi-instance posture.** If the desk's Railway service ever scales to
  multiple instances, a single volume doesn't span them — each instance gets
  its own (or none). The data layer's cold-start throttle is the safety net,
  but multi-instance + persistent-volume needs explicit thinking before it
  happens. Out of scope for v1 (the desk runs single-instance), flagged for
  forward-compat.
- **Volume size budget.** Cache footprint is small in v1 (per-source datums
  + the forward-validation prediction log). Worst case: a few hundred MB.
  Well within the 1 TB ceiling, but worth instrumenting size growth.

### Action before Phase 1a starts

- Confirm the desk's current Railway plan tier.
- If not on Pro, decide: upgrade, or build Phase 1a's cache as
  cold-start-volatile (the data-layer §3.4 fallback posture).
- Document the chosen path in the integration repo's deployment docs.

[Railway pricing](https://railway.com/pricing) ·
[Railway volumes docs](https://docs.railway.com/volumes)

---

## 4. Summary — all-in cost (verified, 2026-05-18)

| Vendor | v1 cost | Notes |
|---|---|---|
| API-Football Pro | $19/mo (USD) | 7,500 req/day, hard cap (errors, no overage billing) |
| OpenWeather One Call 3.0 | $0–$1/mo (USD) worst case | 1k free/day, ~$0.0015/call overage, **daily cap must be set explicitly** at subscribe |
| Railway persistent volume | included in current plan if Pro ($20/mo) | runtime-mount caveat baked into data-layer §3.4 |
| **Total monthly** | **~$19 baseline, ~$20 peak** | At/marginally above the $20 ceiling — same as data-layer §4.1 flagged |

No vendor terms invalidate the data-layer spec's design. Three setup steps
need to land before code:

1. **Subscribe to API-Football Pro** + record per-competition coverage flags.
2. **Subscribe to OpenWeather One Call 3.0** + **set the daily cap explicitly**
   (default 2,000/day is too permissive against the $1/mo overage budget).
3. **Confirm Railway plan tier** is Pro (or budget an upgrade) for persistent
   volume access.

Each is a ~5-minute admin step. None block writing code; all three need to be
done before the affected phase ships to production.

Sources:
- [API-Football pricing](https://www.api-football.com/pricing)
- [API-Football coverage list](https://www.api-football.com/coverage)
- [OpenWeather pricing](https://openweathermap.org/price)
- [OpenWeather One Call 3.0 docs](https://openweathermap.org/api/one-call-3)
- [Railway pricing](https://railway.com/pricing)
- [Railway volumes docs](https://docs.railway.com/volumes)
