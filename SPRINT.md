# Sprint — Private Beta MVP (post-pivot, trimmed v2)

**Dates:** Mon Apr 20 → Sun Apr 26, 2026
**Deliverable:** Private-beta launch of a decision-support workspace on top of Kalshi + Polymarket, powered by the Prophet paper-trading stack. Invite-only; no public launch, no billing, no rebrand this week.
**Supersedes:** the previous public-launch aggregator sprint (retired per REVISED_SCOPE.md) and the first draft of this sprint (overscoped — paper portfolio and full Telegram bot cut per cross-review feedback).

---

## The only thing that must work Sunday

**Signals + Kelly-sized stakes + rationale, rendered on top of 10 hand-verified matched markets.**

If by Sunday evening an invited trader can land on the site, read a Prophet signal with a clear rationale and a suggested size on a market they recognize, and trust that the polarity is correct, the sprint succeeded. Everything else is secondary.

---

## Must-have (definition of done)

1. **10–12 hand-verified matched pairs** across 2–3 non-sports categories (politics, macro/economy, crypto). Every polarity manually verified against the live platform pages.
2. Live prices from both venues, resolved polarity, dislocation % per pair.
3. **One Prophet signal per matched market** — action, edge %, Kelly-sized suggested stake, human-readable rationale. `hold` is an acceptable action.
4. `MatchedMarketsTable` rendering the above in the dark-mode aesthetic.
5. Detail drawer on row click: title, prices, dislocation, signal, rationale, suggested stake, outbound UTM-tagged links. No sparkline, no P&L history.
6. Watchlist (localStorage star toggle).
7. Dead-simple beta password gate (shared password, session-based).

## Stretch (only if must-have is done by Thursday evening)

- **Telegram alerts**, stripped-down: one bot, one channel, hardcoded 3% dislocation threshold, one alert per market per user per 30 min. No threshold UI, no unsubscribe flow.

## Cut from this sprint

- Paper portfolio / 7-day P&L / historical snapshots / seed script / sparkline
- Threshold slider UI for alerts
- HMAC cookie middleware for beta auth (plain password check is enough)
- Multi-channel alerts (Discord, email)
- Sports markets in the mapping (regulatory overhang)
- Billing, accounts, rebrand, SEO, arbitrage scanner, DraftKings, WebSocket, Product Hunt

---

## Assets we leverage (do not rebuild)

- `core/auth.py` — Kalshi RSA-PSS (works)
- `core/kalshi_client.py` — Kalshi client (prices broken; fix T1.1)
- `core/polymarket_client.py` — Polymarket client (works)
- `core/market_normalizer.py` — normalization (patch in T1.2–T1.4)
- `services/odds_comparator.py` — extend in T2.2, don't replace
- `strategies/` — Prophet strategies (wire into signal engine in T3.1; do not rewrite)
- `risk_manager.py` — Kelly sizing (called from signal engine)
- FastAPI + Vite/React 19 + Railway deploy (all stay)

---

## Day 1 — Mon Apr 20 — Backend repair + Prophet smoke test

**Goal:** `/api/compare` returns live Kalshi + Polymarket prices with readable titles and no expired markets. Prove a Prophet strategy can ingest a matched-market snapshot end-to-end (logs-only, no UI).

### T1.1 — Fix Kalshi pricing

**File:** `core/kalshi_client.py`

- `yes_price = (yes_bid + yes_ask) / 2` when both exist; fall back to `last_price`
- `no_price = 1.0 - yes_price`
- Pull `volume` or `volume_24h` from market response
- Skip markets where both `yes_bid` and `yes_ask` are missing or zero

**Acceptance:** `curl <deploy>/api/compare` returns Kalshi markets with non-zero prices + volume.

### T1.2 — Filter to active markets

**File:** `core/market_normalizer.py`

- Kalshi: `status in ("active","open")` AND `close_time > now`
- Polymarket: `active == true`, `closed == false`, `end_date_iso > now`

**Acceptance:** No market in response has `resolution_date` before today.

### T1.3 — Readable titles

**File:** `core/market_normalizer.py`

- Kalshi: prefer `yes_sub_title` or `title`; fallback to `event.title + ": " + yes_sub_title`. Never emit raw ticker strings.
- Polymarket: use `question`.

**Acceptance:** Spot-check 20 random rows — every title reads as an English sentence.

### T1.4 — UTM params on per-market URLs

**Files:** `config.py`, `core/market_normalizer.py`

```python
KALSHI_UTM = "?utm_source=predictionedge&utm_medium=beta&utm_campaign=signal"
POLYMARKET_UTM = "?utm_source=predictionedge&utm_medium=beta&utm_campaign=signal"
```

Append to every per-market URL.

**Acceptance:** Every `url` in `/api/compare` includes UTM.

### T1.5 — Prophet strategy smoke test (this is the sprint's biggest risk)

**File:** `scripts/signal_smoke.py` (new)

- Import one strategy class from `strategies/` and `risk_manager.py`
- Manually construct a matched-market snapshot (hardcode two mapped markets for today)
- Call `strategy.evaluate(snapshot)` and `risk_manager.kelly_size(edge, bankroll=1000)`
- Print signal + suggested size to stdout

**Acceptance:** Script runs, prints a coherent signal + size without stacktraces. If the strategy needs an adapter to accept matched-market input (vs the original Kalshi-demo format), write the adapter today in `services/signal_engine.py` — we'll build on it Day 3. This is the single biggest risk to the week; surface it tonight.

### Claude Code prompt for Day 1

```
Work through tasks T1.1–T1.5 in SPRINT.md in order. Do not touch frontend code. Do not refactor beyond what's needed. After each task, run the acceptance check and paste the output. T1.5 is the critical item — if the existing Prophet strategies cannot accept matched-market snapshots without a rewrite, stop and tell me exactly what's blocking. Do not modify strategies/ code; write an adapter in services/signal_engine.py instead.
```

---

## Day 2 — Tue Apr 21 — Matched-market mapping + engine

**Goal:** `/api/compare` returns 10–12 matched pairs with both venues populated, polarity resolved, dislocation computed.

### T2.1 — Build `data/market_mappings.json`

**Categories:** politics (non-sports), macro/economy, crypto, geopolitics. **No sports.**

Schema:
```json
[
  {
    "slug": "fed-hold-may-2026",
    "display_title": "Fed holds rates at May 2026 meeting",
    "category": "economy",
    "resolution_date": "2026-05-07",
    "kalshi": { "ticker": "KXFEDDECISION-26MAY-HOLD", "yes_means": "Fed holds" },
    "polymarket": { "condition_id": "0x...", "yes_means": "Fed cuts" },
    "polarity_note": "Invert Polymarket YES before side-by-side"
  }
]
```

The `yes_means` field is load-bearing. A single polarity error is the bug that kills credibility with this audience. Manually verify every entry against the live platform pages.

**Acceptance:** 10–12 entries minimum, every polarity verified on the live venue pages. If you can only get 8 clean pairs today, ship with 8. Never fake a pair.

### T2.2 — Extend `services/odds_comparator.py`

- Load `market_mappings.json` at startup
- For each mapped pair, fetch current prices from both clients
- If `yes_means` differs between venues, invert Polymarket's YES (`1 - yes_price`)
- Compute `dislocation = |kalshi_yes - polymarket_yes|`
- Emit `MatchedMarket` with `kalshi`, `polymarket`, `dislocation`, `best_yes_platform`

**Acceptance:** `/api/compare` returns the mapped pairs sorted by `dislocation` desc, both venues populated.

### Claude Code prompt for Day 2

```
Build T2.1 and T2.2. For T2.1, first query the live Kalshi and Polymarket APIs to propose candidate pairs in politics/economy/crypto/geopolitics — NO sports. Show me the candidates with their yes_means framing before writing them to market_mappings.json. Target 10–12 pairs; 8 clean is better than 15 shaky. After T2.2, run /api/compare and paste the top 5 matched markets with dislocation values.
```

---

## Day 3 — Wed Apr 22 — Signal engine (the wedge)

**Goal:** Every mapped market returns a coherent signal via `/api/signal`. No paper portfolio this sprint.

### T3.1 — Signal engine

**File:** `services/signal_engine.py` (extending Day 1 smoke)

- Public function: `compute_signal(matched_market, bankroll=1000) -> Signal`
- `Signal` dataclass: `action` (`buy_yes_kalshi` / `buy_yes_polymarket` / `hold`), `edge_pct`, `suggested_stake`, `rationale` (one sentence, human-legible)
- Internally: call a Prophet strategy's `evaluate` on the snapshot; if an edge emerges, pass it to `risk_manager.kelly_size(edge, bankroll, max_fraction=0.25)`; if no edge, return `action="hold"`, `suggested_stake=0`
- Cache signals in-memory for 30s

**Acceptance:** For every mapped market, `compute_signal` returns a coherent `Signal` object. `hold` is a valid outcome. Rationale is legible to a human (not raw numbers). **Do not tune the strategy to force `buy_*` actions — a product full of honest `hold`s is better than one with manufactured signals.**

### T3.2 — API endpoint

**File:** `api/signals.py` (new)

- `GET /api/signal` → list of signals keyed by mapped-market slug
- `GET /api/signal/<slug>` → single signal with full rationale

**Acceptance:** Both endpoints return valid JSON with expected shape. Every signal includes `action`, `edge_pct`, `suggested_stake`, `rationale`.

### Claude Code prompt for Day 3

```
Build T3.1 and T3.2. Prophet strategies are the product differentiator — do not rewrite them, only adapt inputs/outputs in the services/signal_engine.py adapter we started on Day 1. DO NOT tune the strategy to force more buy signals. If most mapped markets come back as 'hold', that is the correct behavior. After T3.2, hit /api/signal and paste all signals with their action + edge_pct + suggested_stake + rationale.
```

---

## Day 4 — Thu Apr 23 — Frontend rebuild (must-have UI)

**Goal:** Working MatchedMarketsTable + detail drawer + watchlist in the dark-mode aesthetic.

### T4.1 — MatchedMarketsTable

**File:** `frontend/src/components/MatchedMarketsTable.jsx`

Columns: Market | Kalshi | Polymarket | Dislocation | **Signal** | **Stake** | Watch

- `Signal`: "BUY YES Kalshi — 2.4% edge" in green, or "Hold" in muted
- `Stake`: `$24.00` in JetBrains Mono when action != hold; `—` when hold
- `Watch`: star icon toggles localStorage `watchlist`

Sources: `/api/compare` for prices, `/api/signal` for signals. Poll both every 30s.

**Acceptance:** 10+ rows render with signal column populated (mix of buy and hold is expected). Watchlist star persists across reload.

### T4.2 — Detail drawer

**File:** `frontend/src/components/MarketDetailDrawer.jsx`

Right-side slide-over on row click. No sparkline. Shows:

- Market title, resolution date, category
- Both prices + dislocation
- Signal action + edge + suggested stake
- Full rationale (may be longer than the cell version)
- Two buttons: "Open on Kalshi" / "Open on Polymarket" (UTM-tagged outbound)

**Acceptance:** Opens on row click, closes on X/backdrop, shows real data from the two endpoints.

### T4.3 — Stats row (trimmed)

Replace existing stats with three metrics:

- Matched markets count
- Avg dislocation %
- Active signals count (where `action != hold`)

No P&L stat.

### T4.4 — Hide pre-pivot surfaces

Remove from nav: Arbitrage, Movers, category tabs. Single "All Markets" view for beta.

### Claude Code prompt for Day 4

```
Build T4.1–T4.4. Delete the previous OddsTable component. Do not preserve category tabs. Keep the dark-mode / JetBrains Mono / DM Sans aesthetic from the existing mockup — rebuild structure, do not restyle. No sparkline, no P&L chart — cut from this sprint. After each component, take a screenshot at 1440x900 and include in your summary. If anything slips, stop before T4.4 and tell me — T4.1 and T4.2 are the priority.
```

---

## Day 5 — Fri Apr 24 — Buffer + simple beta gate + (stretch) Telegram

**Goal:** Ship the password gate. If everything else is clean, do the stripped-down Telegram bot as a stretch.

### T5.1 — Simple beta password gate (MUST)

**File:** `frontend/src/components/BetaGate.jsx` + `api/beta.py`

- Single password field; `POST /api/beta/verify` compares plaintext against `BETA_PASSWORD` env var
- On success, set `sessionStorage.beta_unlocked = "true"` on the frontend; backend returns simple 200
- All routes in-app check `sessionStorage.beta_unlocked` before rendering; otherwise show gate
- No HMAC, no server-side session store. This is a private beta, not a bank.

**Acceptance:** Site shows gate without session flag; correct password grants access; incorrect password shows error.

### T5.2 — Telegram bot (STRETCH — only if T1.1–T4.4 are all green by Thursday night)

**File:** `services/telegram_bot.py`

- Bot via @BotFather, token in `.env` as `TELEGRAM_BOT_TOKEN`
- `/start <uuid>` links Telegram chat_id to a UUID the user generated in the UI
- Background job every 60s: for each mapped market where `dislocation > 0.03` (hardcoded), push alert to every subscriber
- Rate limit: one alert per market per subscriber per 30 min
- No threshold UI, no unsubscribe. Single channel, single threshold, done.

**Simple frontend piece:** `frontend/src/components/AlertBotSetup.jsx` — button that generates a UUID, stores in localStorage, opens Telegram with the UUID in the `start` param.

**Acceptance (stretch only):** Messaging the bot with `/start <uuid>` returns a welcome message; a real >3% dislocation triggers an alert within 10 min.

**If it slips:** Cut Telegram entirely. Beta still ships with the must-have set.

### Claude Code prompt for Day 5

```
Build T5.1 first — it is required. Only attempt T5.2 if everything from T1–T4 is green on the live deploy. If T5.2 gets hairy (webhook issues, chat_id state, rate limiting), abandon it and spend the remaining time on polish and QA. Telegram is a stretch goal, not a must-have.
```

---

## Day 6 — Sat Apr 25 — QA, invites, demo

### T6.1 — End-to-end smoke (live URL)

- Beta gate blocks without password
- Table renders 10+ matched markets with signal column populated
- Click row → drawer opens with full rationale
- Star a market → reload → star persists
- All UTM params intact on outbound clicks (inspect destination URLs)
- If T5.2 shipped: Telegram alert fires for a real >3% dislocation

### T6.2 — Invite list (20–30 names)

Curate from r/PredictionMarkets active posters, Kalshi Discord, PM Twitter (follow-ups from Oddpool's tweets, Polymarket top traders), personal network.

DM template:
> "Building a decision-support tool for Kalshi+Polymarket traders. Prophet strategy signals + Kelly-sized stakes on matched markets. Private beta this weekend — want early access? I'll send URL + password if yes."

### T6.3 — 30-second Loom

Gate → table → row click → drawer → (if shipped) Telegram connect → alert. For the DMs that ask "what does it look like."

### T6.4 — Analytics

Plausible on all pages. Events: `outbound_click`, `signal_detail_opened`, `watchlist_starred`, `telegram_connected` (if shipped), `beta_unlocked`.

---

## Day 7 — Sun Apr 26 — Private beta launch

- DM invitees with URL + password + Loom link. Stagger over 4 hours.
- Monitor Railway logs + Plausible live view.
- Be available on Telegram/Twitter DMs for feedback.

**Success metric for the week:** 10 invitees visit the site, 5 interact with at least one drawer, 2 reply with substantive feedback. That's it.

---

## Risks (in order of likelihood)

1. **Prophet adapter (T1.5).** Biggest risk of the week. If strategies can't ingest matched-market snapshots cleanly by Monday night, the wedge does not ship. Mitigation: surface the blocker tonight, not Wednesday.
2. **Polarity errors in the mapping file.** A single YES/NO mismatch on a market your invitees recognize is the bug that ends the beta's credibility. Verify every pair against live platform pages. If anything is ambiguous, drop it.
3. **Signal engine produces only `hold` actions.** Acceptable, but worth a sanity check — if literally every market is a hold and dislocations are >3%, the strategy is probably too conservative for this product. That is a Day 3 calibration question, not a "force more buys" question.
4. **Telegram plumbing eats Day 5.** This is why it's a stretch. Cut it if it fights back.

---

## What got cut from v1 of this sprint, and why

- **Paper portfolio + 7-day P&L + sparkline + seed script.** Cosmetic for beta; not required to validate the core loop. Revisit post-beta once 7+ days of real snapshots have accumulated naturally.
- **Full Telegram bot with threshold UI and unsubscribe flow.** Overscoped for one week. Stripped down to Day 5 stretch with hardcoded threshold.
- **15–20 matched pairs target.** Reduced to 10–12. Credibility beats breadth for a private beta.
- **HMAC cookie middleware for beta auth.** Replaced with a sessionStorage flag + plaintext password. It's 10 invitees, not a public launch.
- **Forced `buy_*` acceptance criterion on Day 3.** Removed. Honest `hold` signals are a feature, not a bug.

The trimmed sprint is ~25% less work than v1. If the Prophet adapter lands cleanly on Monday night, the rest of the week is not stressed. If it doesn't, Day 5's buffer absorbs the slip and Telegram gets cut without the beta being hurt.
