"""
Prophet-MVP-v1 — Configuration
Loads credentials and constants from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Kalshi API Environment ────────────────────────────────────────────
# Production (real markets, real prices — bot only paper-trades, never places orders)
BASE_URL = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")
WS_URL = os.getenv("KALSHI_WS_URL", "wss://api.elections.kalshi.com/trade-api/ws/v2")

API_KEY = os.getenv("KALSHI_API_KEY", "")
PRIVATE_KEY_PATH = Path(os.getenv("KALSHI_PRIVATE_KEY_PATH", "./kalshi_private_key.pem"))

# ── Paper-Trading Parameters ─────────────────────────────────────────
STARTING_BALANCE = float(os.getenv("STARTING_BALANCE", "10000"))
MAX_BET_PCT = float(os.getenv("MAX_BET_PCT", "0.02"))        # Kelly cap: 2%
TRADING_FEE_PCT = float(os.getenv("TRADING_FEE_PCT", "0.008"))  # 0.8%

# ── Tickers to Watch ─────────────────────────────────────────────────
WATCH_TICKERS = ["KXBTC", "KXETH", "KXFED", "KXCPI", "KXGDP"]

# ── Data Paths ────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
PORTFOLIO_CSV = DATA_DIR / "portfolio.csv"
