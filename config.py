"""
Prophet-MVP-v1 — Configuration
Loads credentials and constants from environment variables.
Falls back to .env file for local dev; Railway sets env vars directly.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required on Railway if env vars are set

from models.order import ExecutionMode

# ── Kalshi Demo Environment ──────────────────────────────────────────
BASE_URL = os.getenv("KALSHI_BASE_URL", "https://demo-api.kalshi.co/trade-api/v2")
WS_URL = os.getenv("KALSHI_WS_URL", "wss://demo-api.kalshi.co/trade-api/ws/v2")

API_KEY = os.getenv("KALSHI_API_KEY", "")
PRIVATE_KEY_PATH = Path(os.getenv("KALSHI_PRIVATE_KEY_PATH", "./kalshi_private_key.pem"))

# ── Paper-Trading Parameters ─────────────────────────────────────────
STARTING_BALANCE = float(os.getenv("STARTING_BALANCE", "10000"))
MAX_BET_PCT = float(os.getenv("MAX_BET_PCT", "0.02"))        # Kelly cap: 2%
TRADING_FEE_PCT = float(os.getenv("TRADING_FEE_PCT", "0.008"))  # 0.8%

# ── Execution Mode & Safety Rails (live trading) ─────────────────────
EXECUTION_MODE = ExecutionMode(os.getenv("EXECUTION_MODE", "paper").lower())
MAX_TRADE_DOLLARS = float(os.getenv("MAX_TRADE_DOLLARS", "50"))
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "200"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "20"))

# ── Tickers to Watch ─────────────────────────────────────────────────
WATCH_TICKERS = ["KXBTC", "KXETH", "KXFED", "KXCPI", "KXGDP"]

# ── Data Paths ────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
PORTFOLIO_CSV = DATA_DIR / "portfolio.csv"
SAFETY_LOG_CSV = DATA_DIR / "safety_log.csv"

# ── Server ────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "8000"))
