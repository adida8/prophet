# Oddsprimer Ledger — Phase 0

Connected portfolio tracker. Phase 0 ships a paste-a-wallet viewer for
Polymarket wallets. Free, no auth, server-side history storage.

## Architecture

```
ledger/
├── __init__.py        # exports router + run_refresh_loop
├── db.py              # aiosqlite schema + helpers (data/ledger.db)
├── polymarket.py      # async httpx client for data-api.polymarket.com
├── service.py         # refresh, view-model build, history
├── router.py          # FastAPI router mounted at /api/ledger
└── refresh_loop.py    # 15-min background refresh of recently-viewed wallets

frontend/src/ledger/
├── LedgerApp.jsx      # entry — path-based routing for /ledger and /ledger/{addr}
├── Masthead.jsx       # Odds Primer wordmark + "Ledger · Vol. 1 · Polymarket"
├── Wordmark.jsx       # locked bars glyph + Source Serif 4 wordmark
├── WalletInput.jsx    # empty-state paste-a-wallet form
├── StatStrip.jsx      # totals header (value, realized, unrealized, win rate, count)
├── PositionsTable.jsx # open / closed positions
├── PnLChart.jsx       # cumulative P&L (Recharts)
├── Filters.jsx        # stub controls — wired UI, no-ops in Phase 0
├── format.js          # number/string formatters
├── op-tokens.css      # copy of Odds Primer Design System/colors_and_type.css
└── ledger.css         # page styles, all values resolve to design tokens
```

The Ledger reuses the existing `prophet/` FastAPI process: `main.py` adds
the refresh loop alongside the scheduler and uvicorn server, and
`server.py` includes the ledger router and adds an SPA fallback so
`/ledger` and `/ledger/0x…` both serve the React build.

## Data flow

```
[user pastes 0x…]                                       (browser)
        │
        ▼
[GET /api/ledger/wallet/{addr}]                         (router.py)
        │
        ├─ if cached, return view model
        │  if older than 5 min OR never seen → refresh
        ▼
[refresh_wallet(addr)]                                  (service.py)
        │
        ├─ GET data-api.polymarket.com/positions
        ├─ GET data-api.polymarket.com/value
        └─ GET data-api.polymarket.com/activity
        │
        ▼
[insert snapshot, upsert positions, close-missing diff] (db.py)
        │
        ▼
[view model: totals + open + closed positions]          (service.py)
```

A separate task (`refresh_loop.py`) runs every 15 min and refreshes
every wallet viewed in the last 24 h. Cheap because Polymarket's data
API is public and unauthenticated.

## Storage policy

Every snapshot is preserved indefinitely. `snapshots` is the source of
truth for the cumulative P&L chart and any future analytics. The
`positions` table holds the current state per wallet — closed positions
are detected by diffing each refresh against what we last saw.

```
sqlite> .tables
positions  snapshots  wallets

sqlite> .schema snapshots
CREATE TABLE snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address      TEXT NOT NULL,
    snapshot_at         TEXT NOT NULL,
    total_value_usd     REAL NOT NULL,
    realized_pnl_usd    REAL NOT NULL,
    unrealized_pnl_usd  REAL NOT NULL,
    raw_positions_json  TEXT NOT NULL,
    raw_activity_json   TEXT NOT NULL
);
```

DB lives at `data/ledger.db`, a sibling of the legacy `data/portfolio.csv`.

## API

| Method | Path                                       | Returns                    |
|--------|--------------------------------------------|----------------------------|
| POST   | `/api/ledger/wallet/refresh`               | view model (forced refresh) |
| GET    | `/api/ledger/wallet/{address}`             | view model (cached < 5 min)|
| GET    | `/api/ledger/wallet/{address}/history`     | snapshot time series       |

The view model:

```json
{
  "address": "0x…",
  "snapshot_at": "2026-…Z",
  "last_refreshed_at": "2026-…Z",
  "totals": {
    "total_value_usd": 313359.37,
    "realized_pnl_usd": 91.75,
    "unrealized_pnl_usd": -21401.92,
    "open_position_count": 500,
    "closed_position_count": 6,
    "win_rate": null
  },
  "open_positions":   [ /* { market_question, outcome, shares, avg_entry_price, current_price, value_usd, unrealized_pnl_usd, … } */ ],
  "closed_positions": [ /* same shape, plus closed_at */ ]
}
```

## Design system enforcement

Every value in `ledger.css` resolves to a token from `op-tokens.css` —
that file is a verbatim copy of `Odds Primer Design System/colors_and_type.css`.
P&L green/red derive from the system's existing `--venue-kalshi` /
`--flame-deep` family, never hardcoded. The masthead embeds the locked
v2 logo per `branding/bars-locked-v2.html`. No off-system fonts are
used — Source Serif 4, Inter Tight, JetBrains Mono throughout, served
from Google Fonts via the import in `op-tokens.css`.

The Ledger is reachable at `/ledger` only — no nav linking from the
main Odds Primer pages in Phase 0 (per scope brief).

## Known limitations of Phase 0

- **Win rate is null until we have closed positions with non-zero
  realized P&L.** Polymarket's `positions` endpoint returns
  `realizedPnl: 0` for redeemed/expired markets — to compute lifetime
  realized P&L correctly we need to walk the activity feed
  (`type=TRADE` and `type=REDEEM`) and net it. Phase 1 work.
- **Closed-position discovery is diff-based.** We only learn a
  position closed when we observe it disappear from a refresh. Wallets
  refreshed for the first time will show 0 closed positions even if
  many have been resolved historically.
- **The chart shows total P&L (realized + unrealized) per snapshot.**
  History begins at first snapshot; there is no backfill from
  Polymarket activity (Phase 1 work).
- **Filter row is a stub.** Venue / category / market type pills are
  rendered but inert until Phase 1.

## Path to Kalshi (Phase 1)

The architecture is ready for a venue-pluggable model. To add Kalshi:

1. Drop a `ledger/kalshi.py` client analogous to `polymarket.py`. It
   needs the existing RSA signing path from `core/auth.py` because
   Kalshi position data is authenticated.
2. Refactor `service.refresh_wallet(address)` to accept a
   `venue: Literal["polymarket", "kalshi"]` argument and dispatch to
   the right client. Persist the venue on `wallets` and on
   `positions` rows.
3. Extend the view model so totals can be either per-venue or
   blended; surface a venue toggle in `Filters.jsx` (the chrome is
   already there, currently inert).
4. `WalletInput` becomes a venue picker + email/key input for Kalshi
   accounts (since Kalshi accounts aren't keyed by 0x addresses).

The Phase 0 schema (`wallets`, `snapshots`, `positions`) holds
without modification — just add a `venue` column.

CSV import (Phase 1) lands as a separate `POST /api/ledger/import`
endpoint that materialises a synthetic snapshot from the uploaded
file using the same `insert_snapshot` / `upsert_positions` helpers.

## Running locally

```bash
cd prophet/
python3 -m pip install -r requirements.txt

cd frontend/
npm install
npm run build

cd ..
python3 main.py
```

Then open http://localhost:8000/ledger and paste any active Polymarket
wallet (grab one from
https://polymarket.com/leaderboard).
