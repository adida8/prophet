# Feature Spec: Live Order Execution (Paper → Live Toggle)

**Status:** Draft
**Priority:** P0 — primary monetization validation signal
**Spec version:** 1.0
**Date:** 2026-04-18

---

## Why this feature first

The single most important question for Prophet is: "Will users trust this system enough to let it trade real money?" Every other feature (backtesting, alerts, strategy marketplace) becomes irrelevant if the answer is no. A paper→live toggle directly measures willingness to pay by tracking how many users flip the switch, even before you charge for it.

---

## User story

> As a Prophet user, I want to switch my bot from paper trading to live trading on Kalshi Demo so I can validate my strategy with real (demo) dollars — and switch back to paper mode instantly if something feels wrong.

---

## Scope

**In scope:**
- Execution mode toggle: `paper` (current behavior) ↔ `live` (real Kalshi Demo API orders)
- Order placement via Kalshi REST API (`POST /markets/{ticker}/orders`)
- Order lifecycle tracking (placed → resting → filled/cancelled)
- Position tracking (open positions, unrealized P&L)
- Safety rails: per-trade cap, daily loss limit, kill switch
- Dashboard UI for the toggle + live order status

**Out of scope (future features):**
- Production Kalshi API (stays on demo-api.kalshi.co)
- Limit orders / advanced order types (market orders only for v1)
- Position exit / selling (manual close via Kalshi UI for now)
- Multi-account support
- Billing / paywall (that's feature #10)

---

## Architecture

### New files

```
prophet/
├── core/
│   └── executor.py          # NEW — Order execution engine
├── models/
│   └── order.py             # NEW — Order and Position dataclasses
├── strategies/
│   └── base.py              # MODIFY — Signal gets an `execute` flag
├── config.py                # MODIFY — New env vars
├── main.py                  # MODIFY — Execution mode routing
├── server.py                # MODIFY — New endpoints + WS messages
└── frontend/src/App.jsx     # MODIFY — Toggle UI + order status panel
```

### Data flow change

Current:
```
Signal → size_position() → deduct from in-memory balance → CSV log → broadcast
```

With live mode:
```
Signal → size_position() → Executor.execute(signal, contracts)
  ├─ paper mode: deduct from in-memory balance → CSV log → broadcast  (unchanged)
  └─ live mode:  POST /markets/{ticker}/orders → poll status → broadcast order update
```

---

## Implementation details

### 1. `models/order.py` — Data models

```python
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"

class OrderStatus(str, Enum):
    PENDING = "pending"       # Sent to API, awaiting response
    RESTING = "resting"       # On the book, not yet filled
    FILLED = "filled"         # Fully executed
    CANCELLED = "cancelled"   # Cancelled by user or system
    FAILED = "failed"         # API error

@dataclass
class Order:
    id: str                           # Internal UUID
    kalshi_order_id: str | None       # From API response (None for paper)
    ticker: str
    side: str                         # "yes" or "no"
    price: int                        # Cents (Kalshi native format)
    contracts: int
    status: OrderStatus
    mode: ExecutionMode
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None
    fill_price: int | None = None     # Actual fill price in cents
    error: str | None = None

@dataclass
class Position:
    ticker: str
    side: str
    contracts: int
    avg_entry_price: int              # Cents
    current_price: int | None = None  # From latest tick
    unrealized_pnl: float = 0.0
```

### 2. `core/executor.py` — Execution engine

This is the core new component. It wraps both paper and live execution behind a single interface.

```python
class Executor:
    def __init__(self, client: KalshiClient, mode: ExecutionMode, config: Config):
        self.client = client
        self.mode = mode
        self.config = config
        self.orders: list[Order] = []
        self.positions: dict[str, Position] = {}
        self._daily_loss = 0.0
        self._trade_count_today = 0

    async def execute(self, signal: Signal, contracts: int) -> Order:
        """Route to paper or live execution based on current mode."""
        self._check_safety_rails(signal, contracts)

        if self.mode == ExecutionMode.PAPER:
            return self._execute_paper(signal, contracts)
        else:
            return await self._execute_live(signal, contracts)

    def _check_safety_rails(self, signal, contracts):
        """Raise SafetyError if any limit is breached."""
        cost_cents = signal.price * 100 * contracts
        if cost_cents > self.config.max_trade_dollars * 100:
            raise SafetyError(f"Trade ${cost_cents/100:.2f} exceeds per-trade cap ${self.config.max_trade_dollars}")
        if self._daily_loss >= self.config.daily_loss_limit:
            raise SafetyError(f"Daily loss limit ${self.config.daily_loss_limit} reached")
        if self._trade_count_today >= self.config.max_trades_per_day:
            raise SafetyError(f"Daily trade limit {self.config.max_trades_per_day} reached")

    def _execute_paper(self, signal, contracts) -> Order:
        """Current CSV-logging behavior, wrapped in Order model."""
        # ... existing paper trade logic from main.py, returns Order

    async def _execute_live(self, signal, contracts) -> Order:
        """Place real order via Kalshi API."""
        # POST /trade-api/v2/portfolio/orders
        # Body: {ticker, action: "buy", side: "yes"|"no", type: "market",
        #        count: contracts, yes_price or no_price in cents}
        # Returns: {order_id, status, ...}

    def set_mode(self, mode: ExecutionMode):
        """Switch modes. Live→paper is always allowed. Paper→live requires confirmation."""
        self.mode = mode

    def kill(self):
        """Emergency stop. Switches to paper mode and cancels all resting orders."""
        self.mode = ExecutionMode.PAPER
        # Cancel resting orders via DELETE /portfolio/orders/{order_id}
```

### 3. Kalshi Order API integration

Add these methods to `core/client.py`:

```python
async def place_order(self, ticker: str, side: str, contracts: int, price_cents: int) -> dict:
    """POST /trade-api/v2/portfolio/orders"""
    body = {
        "ticker": ticker,
        "action": "buy",
        "side": side,           # "yes" or "no"
        "count": contracts,
        "type": "market",       # Market order for v1
    }
    return await self._post("/portfolio/orders", json=body)

async def get_order(self, order_id: str) -> dict:
    """GET /trade-api/v2/portfolio/orders/{order_id}"""
    return await self._get(f"/portfolio/orders/{order_id}")

async def cancel_order(self, order_id: str) -> dict:
    """DELETE /trade-api/v2/portfolio/orders/{order_id}"""
    return await self._delete(f"/portfolio/orders/{order_id}")

async def get_positions(self) -> list[dict]:
    """GET /trade-api/v2/portfolio/positions"""
    return await self._get("/portfolio/positions")

async def get_balance(self) -> dict:
    """GET /trade-api/v2/portfolio/balance"""
    return await self._get("/portfolio/balance")
```

### 4. Config changes (`config.py`)

```python
# Execution mode
EXECUTION_MODE = ExecutionMode(os.getenv("EXECUTION_MODE", "paper"))

# Safety rails
MAX_TRADE_DOLLARS = float(os.getenv("MAX_TRADE_DOLLARS", "50"))      # $50 per trade hard cap
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "200"))       # Stop after $200 daily loss
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "20"))      # Max 20 trades/day
```

### 5. Server changes (`server.py`)

New REST endpoints:

```
GET  /api/mode              → { "mode": "paper" | "live" }
POST /api/mode              → { "mode": "live" }  (switches mode)
POST /api/kill              → {}  (emergency stop → paper + cancel orders)
GET  /api/orders            → [Order, ...]  (recent orders)
GET  /api/positions         → [Position, ...]  (open positions, live mode only)
GET  /api/balance/live      → { "available": 9850, "portfolio": 150 }  (real Kalshi balance)
```

New WebSocket message types:

```json
{ "type": "mode_change", "data": { "mode": "live", "changed_at": "..." } }
{ "type": "order_update", "data": { "id": "...", "status": "filled", "fill_price": 42 } }
{ "type": "safety_alert", "data": { "rule": "daily_loss_limit", "message": "..." } }
```

### 6. Frontend changes (`App.jsx`)

**Mode toggle** — prominent switch in the header area:

- Visual states: green "PAPER" badge (default) ↔ red-outlined "LIVE" badge
- Switching paper→live shows a confirmation modal: "You are about to enable live trading on Kalshi Demo. Max $50 per trade, $200 daily loss limit. Continue?"
- Switching live→paper is instant, no confirmation needed

**Order status panel** — new section below the stats cards (visible in live mode only):

- Table: Order ID, Ticker, Side, Contracts, Status, Fill Price, Time
- Color-coded status pills: blue=pending, yellow=resting, green=filled, red=failed
- "Cancel" button on resting orders

**Kill switch** — red button in the header, always visible in live mode:

- Single click → confirmation → POST /api/kill
- Disables live mode and cancels all resting orders

**Balance display** — in live mode, show real Kalshi Demo balance alongside simulated balance:

- "Paper balance: $10,234" / "Live balance: $9,850 (available) + $150 (in positions)"

---

## Safety rails (non-negotiable)

These exist to prevent a bug or runaway strategy from draining a demo account:

| Rail | Default | Behavior when hit |
|------|---------|-------------------|
| Per-trade cap | $50 | Order rejected, logged as SafetyError |
| Daily loss limit | $200 | Auto-switch to paper mode, alert broadcast |
| Max trades/day | 20 | Orders rejected until midnight UTC reset |
| Kill switch | — | Immediate paper mode + cancel all resting |
| Mode confirmation | — | Paper→live requires explicit user confirmation |

All safety events are logged to a new `data/safety_log.csv` and broadcast via WebSocket as `safety_alert` messages.

---

## Validation metrics

Track these to determine if the feature validates the product:

1. **Toggle rate** — % of users who switch to live mode at least once
2. **Revert time** — How long users stay in live mode before switching back (or if they stay)
3. **Kill switch usage** — How often the emergency stop is hit (high = trust problem)
4. **Trade volume in live mode** — Are users letting real trades execute, or toggling back immediately?
5. **Safety rail hits** — Which limits are being hit? (Informs whether defaults are too tight or too loose)

---

## Implementation order

Build and test in this sequence — each step is independently demoable:

1. **`models/order.py`** — Data models (Order, Position, ExecutionMode)
2. **`core/client.py`** — Add order placement, cancellation, position, and balance methods
3. **`core/executor.py`** — Execution engine with paper/live routing + safety rails
4. **`main.py`** — Wire Executor into the trading loop (replacing inline paper logic)
5. **`server.py`** — New endpoints (mode, orders, positions, kill) + WS message types
6. **`config.py`** — New env vars for safety limits
7. **`frontend/src/App.jsx`** — Toggle UI, order panel, kill switch
8. **End-to-end test** — Run in live mode against Kalshi Demo, verify order placement and safety rails

---

## Risks and mitigations

**Risk:** Kalshi Demo API rate limits are stricter than expected.
**Mitigation:** Add request throttling in `client.py` (max 5 requests/second). Log 429 responses and back off exponentially.

**Risk:** WebSocket disconnect during live trading leaves orphaned orders.
**Mitigation:** On reconnect, poll `GET /portfolio/orders` to sync state. The kill switch cancels all resting orders regardless of local state.

**Risk:** User leaves live mode running overnight and strategy drains balance.
**Mitigation:** Daily loss limit auto-triggers paper mode. Consider an inactivity timeout (no dashboard connection for 30 min → auto-switch to paper).

**Risk:** Market order slippage — fill price differs significantly from signal price.
**Mitigation:** Log fill_price vs signal.price delta. For v2, consider limit orders.

---

## Out of scope but noted for future

- **Limit orders** — Kalshi supports them; market orders are a simplification for v1
- **Position exit** — Selling contracts to close positions (requires `action: "sell"`)
- **P&L reconciliation** — Comparing paper vs live performance on the same signals
- **Audit trail** — Immutable log of all live orders for compliance
- **Multi-strategy isolation** — Separate balance tracking per strategy in live mode
