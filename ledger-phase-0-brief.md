# Build: Oddsprimer Ledger — Phase 0 (revised)

## Context to read first (in this order)
1. `/Users/adi/Documents/Claude/Projects/prophet/CLAUDE.md` — project overview and stack
2. `/Users/adi/Documents/Claude/Projects/prophet/Odds Primer Design System/` — read every file. Palette, typography, voice, components. Use design tokens; do not invent new colors, type sizes, or spacing values.
3. `/Users/adi/Documents/Claude/Projects/prophet/Odds Primer Design System/mockups/ledger-command-center-v3-wc.html` — **the locked v3 visual reference**. Match this layout, type, color, and density. The four-source panel ("Polymarket / Manual / Kalshi / CSV") is the new headline section, not optional.
4. `/Users/adi/Documents/Claude/Projects/prophet/branding/bars-locked-v2.html` — locked logo (4-bar glyph + Source Serif 4 wordmark, 11px gap, no live dot)
5. `/Users/adi/Documents/Claude/Projects/prophet/branding/wc-edition-brief.md` — masthead/issue framing context
6. Existing patterns in `frontend/src/App.jsx`, `main.py`, `core/`, `server.py`

## What you're building
Oddsprimer Ledger is a connected portfolio tracker — sister product under the Odds Primer masthead. **Phase 0** is the multi-source command-center: any user can feed positions in via a Polymarket wallet, by hand, or by uploading a CSV / EdgeGridStudio spreadsheet. Free, full server-side history, accounts required (magic-link).

This phase ships in ~2–3 weeks (expanded from the original wallet-only scope). Use the existing FastAPI + React stack and the locked design system.

## Why the scope grew
EdgeGridStudio is the launch audience. Those buyers paid $10–20 for a tracker spreadsheet — they expect the connected version to do everything the spreadsheet did, including supporting positions on sportsbooks and venues that don't expose APIs. Manual entry isn't a Phase 1 nice-to-have; it's table stakes for the wedge to land.

## Phase 0 scope

### Auth (new — required)
- Magic-link email auth, no passwords. POST `/api/auth/request` sends a signed link; GET `/api/auth/callback?token=…` exchanges for a session cookie.
- One user → many sources → many positions. All persistence is per-user.
- For demo / press / preview: a public read-only `/ledger/demo` route renders a seeded sample wallet (no auth). Anyone we DM the link to lands here first.

### Backend — `/api/ledger/*` router
- `POST /api/ledger/sources/wallet` — body `{address}`. Adds a Polymarket wallet source to the current user. Triggers initial sync.
- `POST /api/ledger/sources/wallet/refresh` — manual refresh of an existing wallet source.
- `POST /api/ledger/sources/manual/positions` — body `{market_question, outcome, shares, avg_entry_price, current_price, venue, opened_at, closed_at?, notes?}`. Insert a manual position.
- `PATCH /api/ledger/sources/manual/positions/{id}` — edit any field on a manual position.
- `DELETE /api/ledger/sources/manual/positions/{id}` — remove a manual position.
- `POST /api/ledger/sources/csv` — multipart upload. Detects EdgeGridStudio K1–K6 / P1–P6 column structure and maps automatically. Returns a preview; user confirms; server inserts.
- `GET /api/ledger/portfolio` — combined view across all of the user's sources.
- `GET /api/ledger/portfolio/history` — time-series snapshots.

**Polymarket Data API (public, no auth):**
- `https://data-api.polymarket.com/positions?user={address}`
- `https://data-api.polymarket.com/activity?user={address}`
- `https://data-api.polymarket.com/value?user={address}`

Probe the endpoints with a real active wallet from the Polymarket leaderboard and build parsers against what they return.

### Data model (SQLite for Phase 0)
- `users`: `id`, `email`, `created_at`, `last_login_at`
- `auth_tokens`: `token` (pk), `user_id`, `expires_at`, `consumed_at`
- `sources`: `id`, `user_id`, `kind` (`wallet` | `manual` | `kalshi` | `csv`), `label`, `external_id` (e.g. wallet address), `created_at`, `last_synced_at`
- `positions`: `id`, `source_id`, `user_id`, `market_question`, `market_id` (nullable for manual), `venue` (`polymarket` | `kalshi` | `manual:draftkings` | `manual:fanduel` | `manual:bet365` | `manual:other`), `outcome`, `shares`, `avg_entry_price`, `current_price`, `value_usd`, `unrealized_pnl_usd`, `opened_at`, `closed_at` (nullable), `notes` (nullable), `entered_at`, `entered_by` (`auto` | `user`)
- `snapshots`: `id`, `user_id`, `snapshot_at`, `total_value_usd`, `realized_pnl_usd`, `unrealized_pnl_usd`, `raw_payload_json`

Snapshot the **portfolio** (not per-source) on every change — this drives the cumulative P&L chart cleanly across sources.

**Storage policy: we store everything.** Every snapshot preserved indefinitely. Manual entries are user-edited records; we keep an `audit_log` table tracking inserts/updates/deletes for any future undo or dispute.

DB file: `data/ledger.db`.

### Frontend — `/ledger`

Match the locked v3 mockup. The page in order:

1. **EdgeGridStudio welcome banner** — top of page, dismissable. "Welcome from EdgeGridStudio. Your tracker template is now a live web app. Free, forever, for our paid customers." Render only when the user arrived from an EdgeGridStudio link (UTM `?from=edgegridstudio` or referrer match) or explicitly identified themselves as a paid Etsy customer.
2. **Live ticker** — top movers across the user's open positions, scrolling.
3. **Masthead** — locked logo + "Oddsprimer · Ledger" wordmark.
4. **Cover strip** — edition framing ("World Cup 2026 Edition · 38 days to kickoff" — keep it dynamic; this strip is the cover treatment for whichever issue is current).
5. **Hero metrics** — large portfolio value with delta + 53d sparkline; four small stat cards (all-time return, edge realised, hot streak, Sharpe-like).
6. **Sources panel** — four cards: Polymarket wallet, Manual entries, Kalshi API key, CSV / spreadsheet. Each shows status (Connected / Active / Not connected / Ready), position count, and a primary action. Manual entries opens an inline spreadsheet-style editor; CSV opens an upload modal with auto field detection.
7. **Movers** — top 4 markets by 60-min P&L change.
8. **Main chart + heatmap** — cumulative P&L line chart with annotations + 9×6 daily heatmap.
9. **Quad metric grid** — win rate, open exposure, realised vs unrealised, by bet type.
10. **Open positions table** — bet-type-coloured rows; Polymarket positions show a venue dot, manual entries show a black "Manual" badge plus venue text (e.g. "DraftKings · entered Apr 14"). Editable inline for manual rows; read-only for auto-fetched rows.
11. **Closed teaser + activity feed + edge analysis** — as in the v3 mockup.

### Manual entry UX (this is the whole pitch — get it right)
- **Spreadsheet-style row editor**, not a modal form. The Etsy buyer's muscle memory is a sheet — match it.
- Tab/Enter to advance fields; Cmd-Enter saves; Cmd-V pastes a TSV/CSV block from Excel and adds rows.
- Autocomplete on `market_question` against the Polymarket + Kalshi market catalogues — if the user is entering a market that exists on a venue we support, offer to convert to an auto-tracked position with a single click.
- Required fields: market_question, outcome, shares, avg_entry_price, current_price (optional if venue is auto-tracked), opened_at. Everything else optional.
- "Add row" button always visible at the bottom of the manual section. Empty-state row pre-focused on first cell.

### CSV / spreadsheet import
- Accept `.csv`, `.xlsx`, `.xls`. Use `pandas` + `openpyxl`.
- Built-in parsers for EdgeGridStudio K1–K6 and P1–P6 templates — match by header signatures, not filename.
- Generic fallback: show a column-mapping UI ("Which column is the market? Which is the outcome?") if no template matches.
- Upload returns a **preview**: parsed rows in the same table format as the live positions table. User confirms or cancels before any rows hit the DB.

### Design system enforcement (non-negotiable)
- Use color tokens from the design system. No new hex values. P&L green/red is permitted only for delta indicators on charts and movement, never for static P&L cells.
- Use the typography scale: serif headlines, sans chrome, mono numerics.
- Editorial voice — no exclamation points, no emoji (footnote daggers `†` `‡`), no gambling-promo language ("bet now", "smart money", "lock", "boost"). The Etsy banner is the most marketing-leaning copy that can appear on the page; everything else stays editorial.
- Match the v3 mockup's component patterns exactly. If something isn't in the mockup or the design system, stop and ask.

### Out of scope for Phase 0
- **Nav linking from main Odds Primer pages** — `/ledger` reachable directly only.
- **Kalshi auto-sync** — leave the source card showing "Not connected" with a placeholder action. Phase 1.
- **Mobile-first layout** — responsive but desktop-led.
- **Tax export** — Phase 2.
- **Educational integration with Odds Primer market pages** — Phase 3.
- **Order placement / trading** — read-only, forever.
- **Payments / paid tier** — Ledger is free.
- **Real-time WebSocket updates** — 5-min refresh on view + 15-min background loop is enough.

### Acceptance criteria
1. `python main.py --dashboard` starts the server; `/ledger` renders the empty-source state for a new user; `/ledger/demo` renders a seeded sample portfolio for unauthenticated visitors.
2. Magic-link auth round-trip works end to end (email send is fine via console log in dev).
3. Adding a Polymarket wallet source and refreshing pulls real positions and writes a snapshot.
4. Manual row entry persists; pasting a TSV block from Excel adds multiple rows in one shot.
5. CSV upload of a real EdgeGridStudio K1 or P1 template auto-maps columns and previews correctly before commit.
6. Combined portfolio view sums across all sources — cumulative P&L chart spans Polymarket + manual + CSV trades on one timeline.
7. Visual review against the v3 mockup passes — no off-palette colors, no off-system fonts, masthead and source-panel layout matches.
8. `sqlite3 data/ledger.db ".tables"` shows `users`, `auth_tokens`, `sources`, `positions`, `snapshots`, `audit_log`.
9. New `ledger/README.md` explains architecture, the four-source model, and the path to add Kalshi auto-sync in Phase 1.

### Working notes
- The activation moment is the four-source panel. The Etsy customer needs to see, within five seconds of landing, that they have multiple ways in — and that "enter manually" is genuinely first-class.
- Probe the Polymarket Data API before writing parsers. Build to what's returned, not what's described here.
- Manual entry should be FAST. A user adding 20 positions by hand should not feel like they'd rather be in their old spreadsheet.
- Demo seed data should be a real WC 2026 portfolio (mirror what the mockup shows — Argentina, Mbappé top scorer, etc.) so the demo URL is genuinely shareable to Etsy customers.
- Keep the codebase consistent: same Python style as `core/`, same React patterns as `frontend/src/App.jsx`.
