# Prophet-MVP-v1

Autonomous paper-trading bot for the **Kalshi Demo** prediction-market API, with a live React dashboard.

## Quick Start

```bash
# Backend
cd prophet/
cp .env.example .env          # fill in KALSHI_API_KEY + KALSHI_PRIVATE_KEY_PATH
pip install -r requirements.txt

# Frontend
cd frontend/
npm install
npm run build                  # outputs to frontend/dist/

# Run (headless)
cd ..
python main.py

# Run with live dashboard on http://localhost:8000
python main.py --dashboard
```

For frontend dev with hot-reload, run `npm run dev` in `frontend/` (port 5173) while the backend runs on 8000.

## Architecture

```
prophet/
├── main.py              # Entry point — orchestrates everything
├── config.py            # Env vars, constants, ticker watch-list
├── server.py            # FastAPI dashboard server (REST + WS broadcast)
├── risk_manager.py      # Kelly Criterion position sizing (2% hard cap)
├── core/
│   ├── auth.py          # RSA-PSS / SHA-256 request signing
│   ├── client.py        # Async HTTP (httpx) + WebSocket (websockets) client
│   └── logger.py        # CSV trade logger + P&L summary
├── strategies/
│   ├── base.py          # Abstract Strategy class + Signal dataclass
│   └── simple_arb.py    # Yes/No imbalance detection strategy
├── frontend/            # Vite + React dashboard
│   └── src/App.jsx      # Single-file dashboard (recharts, lucide-react)
└── data/
    └── portfolio.csv    # Simulated trade log (auto-created)
```

## Key Design Decisions

- **No real trades.** The bot only records simulated trades to CSV. It never calls the Kalshi order API.
- **Demo environment only.** All URLs point to `demo-api.kalshi.co`.
- **0.8% fee** is applied on every entry. The strategy's edge calculation accounts for round-trip fees.
- **Half-Kelly sizing** with a hard 2% cap per trade keeps drawdowns small.
- **WebSocket reconnect** — the Kalshi stream auto-reconnects on disconnect with a 5s backoff.
- **Dashboard is optional** — `python main.py` runs headless; add `--dashboard` for the browser UI.

## Adding a New Strategy

1. Create a file in `strategies/`, e.g. `strategies/momentum.py`
2. Subclass `Strategy` from `strategies/base.py`
3. Implement `name` (property) and `evaluate(tick) -> Signal | None`
4. Import and wire it in `main.py` (swap or combine with `SimpleArbStrategy`)

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `KALSHI_API_KEY` | — | Your Kalshi API key |
| `KALSHI_PRIVATE_KEY_PATH` | `./kalshi_private_key.pem` | Path to RSA private key |
| `STARTING_BALANCE` | `10000` | Simulated starting capital |
| `MAX_BET_PCT` | `0.02` | Hard cap: max 2% of balance per trade |
| `TRADING_FEE_PCT` | `0.008` | 0.8% fee per trade |

## Tech Stack

**Backend:** Python 3.11+, httpx, websockets, cryptography, pandas, FastAPI, uvicorn
**Frontend:** React 19, Vite, Recharts, Lucide React
