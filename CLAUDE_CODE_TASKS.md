# Claude Code Task Prompts — Prophet Private Beta Sprint

One self-contained prompt per task. Feed them to Claude Code in order. Each prompt assumes Claude Code is running in the Prophet repo root.

---

## DAY 1 — Mon Apr 20 — Backend repair + Prophet smoke test

### Task 1.1 — Fix Kalshi pricing

```
Fix Kalshi pricing in core/kalshi_client.py.

Currently yes_price returns 0.0 — wrong field. Change it to:
- yes_price = (yes_bid + yes_ask) / 2 when both exist
- Fall back to last_price if bid/ask missing
- no_price = 1.0 - yes_price
- Pull `volume` or `volume_24h` from the market response and surface it
- Skip any market where both yes_bid and yes_ask are missing or zero

Do not touch any other file. After the change, run the live deploy's /api/compare (or local server) and paste 3 sample Kalshi market entries showing non-zero prices + volume. If you cannot hit the deploy, run a local curl. Acceptance: zero markets with price 0.0.
```

### Task 1.2 — Filter to active markets

```
In core/market_normalizer.py, filter out expired and inactive markets.

- Kalshi: keep only markets where status in ("active","open") AND close_time > now (UTC)
- Polymarket: keep only where active == true AND closed == false AND end_date_iso > now (UTC)

Use timezone-aware datetimes. After the change, hit /api/compare and confirm: no entry has resolution_date before today. Paste the count before vs after the filter.
```

### Task 1.3 — Readable titles

```
In core/market_normalizer.py, replace raw ticker output with human-readable titles.

- Kalshi: prefer yes_sub_title or title; fallback to event.title + ": " + yes_sub_title. Never emit raw ticker strings like "KXFEDDECISION-26MAY-HOLD".
- Polymarket: use the `question` field.

After the change, hit /api/compare, sample 20 random rows, and paste their titles. Every one should read as an English sentence. Flag any that don't.
```

### Task 1.4 — UTM params on per-market URLs

```
Add UTM tagging to every per-market outbound URL.

In config.py add:
KALSHI_UTM = "?utm_source=predictionedge&utm_medium=beta&utm_campaign=signal"
POLYMARKET_UTM = "?utm_source=predictionedge&utm_medium=beta&utm_campaign=signal"

In core/market_normalizer.py, append the matching UTM string to every per-market URL emitted (Kalshi → KALSHI_UTM, Polymarket → POLYMARKET_UTM). Handle URLs that already have query params (use & not ?).

Acceptance: every `url` field in /api/compare response includes utm_source=predictionedge. Paste 3 examples (one Kalshi, one Polymarket, one with a pre-existing query string).
```

### Task 1.5 — Prophet strategy smoke test (CRITICAL — biggest sprint risk)

```
This is the most important task of Day 1. Goal: prove a Prophet strategy from strategies/ can produce a signal from a matched-market snapshot.

Create scripts/signal_smoke.py that:
1. Imports one strategy class from strategies/ and risk_manager.py
2. Manually constructs a matched-market snapshot (hardcode two mapped markets — pick any two real ones from the live /api/compare output)
3. Calls strategy.evaluate(snapshot)
4. Calls risk_manager.kelly_size(edge, bankroll=1000)
5. Prints the signal + suggested size to stdout

DO NOT modify anything in strategies/. If the existing Prophet strategies cannot accept matched-market snapshots without changes, write an adapter in services/signal_engine.py (new file) that translates between matched-market format and whatever the strategy expects. We'll build on this adapter on Day 3.

Run the script. Paste full stdout.

If you hit a wall — strategy needs a rewrite, signature is fundamentally incompatible, etc. — STOP and tell me exactly what's blocking. Do not improvise around it. This task surfaces the sprint's biggest risk; honest failure here is more useful than fake success.
```

---

## DAY 2 — Tue Apr 21 — Matched-market mapping + engine

### Task 2.1a — Propose candidate matched pairs (REVIEW BEFORE WRITING)

```
Before writing data/market_mappings.json, propose candidate pairs for me to review.

Query the live Kalshi and Polymarket APIs and propose 12–15 candidate matched pairs across these categories ONLY:
- Politics (non-sports — elections, appointments, legislation)
- Macro / economy (Fed decisions, CPI, GDP, jobs reports)
- Crypto (BTC/ETH price targets, ETF approvals)
- Geopolitics (treaties, conflict outcomes)

NO sports markets. NO entertainment.

For each candidate, output as a markdown table:
| slug | display_title | category | resolution_date | kalshi_ticker | kalshi_yes_means | polymarket_condition_id | polymarket_yes_means | polarity_match (yes/inverted) | confidence (high/med/low) |

Stop after the table. Do not write the file. I will review and tell you which to commit.
```

### Task 2.1b — Write market_mappings.json

```
From the candidate pairs I approved, write data/market_mappings.json.

Schema per entry:
{
  "slug": "fed-hold-may-2026",
  "display_title": "Fed holds rates at May 2026 meeting",
  "category": "economy",
  "resolution_date": "2026-05-07",
  "kalshi": { "ticker": "KXFEDDECISION-26MAY-HOLD", "yes_means": "Fed holds" },
  "polymarket": { "condition_id": "0x...", "yes_means": "Fed cuts" },
  "polarity_note": "Invert Polymarket YES before side-by-side"
}

The yes_means field is load-bearing. A single polarity error kills credibility with this audience.

Acceptance: file is valid JSON, every entry has yes_means populated on both sides, polarity_note present where polarities differ.
```

### Task 2.2 — Extend odds_comparator with matched markets

```
Extend services/odds_comparator.py to load and compute on the mappings file.

- Load data/market_mappings.json at startup (cache in memory; expose a reload function)
- For each mapped pair, fetch current prices from kalshi_client + polymarket_client
- If kalshi.yes_means != polymarket.yes_means → invert Polymarket YES (yes_price = 1 - yes_price)
- Compute dislocation = abs(kalshi_yes - polymarket_yes)
- Emit a MatchedMarket object: { slug, display_title, category, kalshi: {...}, polymarket: {...}, dislocation, best_yes_platform }

Wire it into /api/compare so the response is mapped pairs (sorted by dislocation desc), not raw single-venue markets.

After: hit /api/compare and paste the top 5 matched markets with dislocation values. Both venues must be populated on every entry.
```

---

## DAY 3 — Wed Apr 22 — Signal engine (the wedge)

### Task 3.1 — Signal engine

```
Build services/signal_engine.py (extending the Day 1 adapter).

Public function:
  compute_signal(matched_market, bankroll=1000) -> Signal

Signal dataclass:
  action: Literal["buy_yes_kalshi", "buy_yes_polymarket", "hold"]
  edge_pct: float
  suggested_stake: float
  rationale: str  # one sentence, human-legible

Internals:
- Call a Prophet strategy from strategies/ on the matched-market snapshot (use the Day 1 adapter)
- If an edge emerges → risk_manager.kelly_size(edge, bankroll, max_fraction=0.25) → suggested_stake
- If no edge → action="hold", suggested_stake=0
- Cache signals in-memory for 30s (per slug)

DO NOT TUNE THE STRATEGY TO FORCE buy_* OUTCOMES. A product full of honest holds is better than one with manufactured signals. If most markets come back as hold, that is correct behavior.

Rationale must be human-legible — "Polymarket YES underpriced 3.2% vs Kalshi after polarity adjustment" not "edge=0.032".

After build: run compute_signal on every market in /api/compare, paste the resulting Signal objects.
```

### Task 3.2 — Signal API endpoint

```
Add api/signals.py:

- GET /api/signal → { slug: Signal, ... } for all mapped markets
- GET /api/signal/<slug> → single Signal with full rationale

Wire into the FastAPI app. Reuse the 30s cache from compute_signal.

Acceptance: both endpoints return valid JSON. Every signal includes action, edge_pct, suggested_stake, rationale. Paste a sample of both responses.
```

---

## DAY 4 — Thu Apr 23 — Frontend rebuild

### Task 4.1 — MatchedMarketsTable

```
Build frontend/src/components/MatchedMarketsTable.jsx. Delete the previous OddsTable component if it exists.

Columns: Market | Kalshi | Polymarket | Dislocation | Signal | Stake | Watch

- Signal cell: "BUY YES Kalshi — 2.4% edge" in green when action != hold; "Hold" in muted gray when hold
- Stake cell: "$24.00" in JetBrains Mono when action != hold; "—" when hold
- Watch cell: star icon (lucide-react Star) toggles localStorage key "watchlist" (array of slugs)

Data sources: /api/compare (prices) + /api/signal (signals). Poll both every 30s.

Keep the dark-mode / JetBrains Mono / DM Sans aesthetic. Rebuild structure, do not restyle.

After: take a screenshot at 1440x900 and include in summary. Acceptance: 10+ rows render, signal column shows mix of buy/hold, watchlist star persists on reload.
```

### Task 4.2 — MarketDetailDrawer

```
Build frontend/src/components/MarketDetailDrawer.jsx — right-side slide-over, opens on row click in MatchedMarketsTable.

Contents:
- Market title, resolution date, category
- Both prices side-by-side + dislocation %
- Signal action + edge % + suggested stake
- Full rationale (longer than the table cell version)
- Two buttons: "Open on Kalshi" and "Open on Polymarket" — outbound to UTM-tagged URLs

NO sparkline. NO P&L history. NO price chart.

Closes on X button or backdrop click.

After: screenshot at 1440x900 with drawer open. Acceptance: opens on row click, shows real data from both endpoints, outbound buttons go to UTM-tagged URLs.
```

### Task 4.3 — Stats row (trimmed)

```
Replace existing stats row with exactly three metrics:
1. Matched markets count
2. Avg dislocation %
3. Active signals count (where action != hold)

NO P&L stat. NO portfolio stat. NO 7-day stats.

Same dark-mode aesthetic. Screenshot after.
```

### Task 4.4 — Hide pre-pivot surfaces

```
Remove from the nav and routing:
- Arbitrage tab
- Movers tab
- Category tabs

Single "All Markets" view for beta. Delete the unused components or comment them out with a TODO referencing post-beta.

After: screenshot of the new nav. Acceptance: no broken routes, single-page beta view.
```

---

## DAY 5 — Fri Apr 24 — Buffer + beta gate + (stretch) Telegram

### Task 5.1 — Beta password gate (MUST)

```
Build the simple beta password gate.

Backend — api/beta.py:
- POST /api/beta/verify — body { password: str }; compare plaintext against env var BETA_PASSWORD; return 200 on match, 401 on mismatch. No session store.

Frontend — frontend/src/components/BetaGate.jsx:
- Single password field + submit button
- On success: sessionStorage.setItem("beta_unlocked", "true")
- On failure: show inline error
- Wrap App.jsx so all routes check sessionStorage.beta_unlocked before rendering — if missing, show BetaGate

NO HMAC, NO server-side session store. This is 10 invitees, not a bank.

Add BETA_PASSWORD to .env.example with a placeholder.

Acceptance: site shows gate without session flag; correct password grants access for the session; refresh keeps you in (sessionStorage persists per tab); incorrect password shows error.
```

### Task 5.2 — Telegram bot (STRETCH — only if all of T1.1–T4.4 are green)

```
ONLY proceed with this if every must-have task is green on the live deploy. If anything from T1.1–T4.4 is shaky, skip this entirely and use the time for QA.

Build services/telegram_bot.py:
- Token in env as TELEGRAM_BOT_TOKEN (created via @BotFather)
- /start <uuid> command links Telegram chat_id to a UUID
- Background job every 60s: for each mapped market where dislocation > 0.03, push alert to every linked subscriber
- Rate limit: one alert per market per subscriber per 30 min (in-memory dict is fine)
- NO threshold UI, NO unsubscribe flow

Frontend — frontend/src/components/AlertBotSetup.jsx:
- Button: "Connect Telegram alerts"
- On click: generate UUID, store in localStorage as "telegram_uuid", open https://t.me/YOUR_BOT?start=<uuid>

Acceptance: messaging the bot with /start <uuid> returns a welcome message; a real >3% dislocation triggers an alert within 10 min.

If anything fights back — webhook issues, chat_id state, rate limiting — ABANDON and tell me. Telegram is stretch, not must-have.
```

---

## DAY 6 — Sat Apr 25 — QA, invites, demo

### Task 6.1 — End-to-end smoke on live URL

```
Run end-to-end smoke on the Railway deploy. Report pass/fail per item:

1. Visiting site without sessionStorage flag shows beta gate
2. Wrong password shows error
3. Correct password grants access
4. Table renders 10+ matched markets, signal column populated (mix of buy + hold expected)
5. Click a row → drawer opens with full rationale
6. Star a market → reload → star persists
7. Inspect 3 outbound clicks (Kalshi + Polymarket + drawer button) — all destination URLs include utm_source=predictionedge
8. (If T5.2 shipped) Telegram alert fires for a real >3% dislocation within 10 min

For any failure, paste the exact error/screenshot.
```

### Task 6.2 — Plausible analytics

```
Add Plausible analytics to all pages.

Add the Plausible script tag to frontend/index.html (domain: the Railway URL).

Fire custom events:
- beta_unlocked — when password correct
- outbound_click — when any Kalshi/Polymarket button clicked (props: { platform, slug })
- signal_detail_opened — when drawer opens (props: { slug, action })
- watchlist_starred — when star toggled on (props: { slug })
- telegram_connected — when bot UUID generated (if T5.2 shipped)

Test each event by performing the action and checking the Plausible live view. Report which events were verified.
```

---

## DAY 7 — Sun Apr 26 — Launch (manual, no Claude Code task)

DM invitees with URL + password + Loom link. Stagger over 4 hours. Monitor Railway logs + Plausible live view. Be available on Telegram/Twitter DMs for feedback.

---

## Notes for using these prompts

- Feed one task at a time. Wait for output, verify acceptance, then move to the next.
- T1.5 (Prophet adapter) is the single biggest risk. If it fails, stop and decide whether to cut signals or push the whole sprint.
- T2.1 has a deliberate review checkpoint (T2.1a → T2.1b). Do not skip it. A polarity error kills credibility.
- Day 3 has a hard rule: do not tune the strategy to force buy signals. Honest holds are correct.
- Day 5: T5.2 is gated on T1–T4 being green. Hold the line.
