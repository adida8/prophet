"""
Prophet-MVP-v1 — Order Execution Engine.

Wraps paper and live execution behind a single interface so the trading
loop does not need to know which mode is active. Owns the safety rails
(per-trade cap, daily loss limit, max trades/day, kill switch).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import Awaitable, Callable

import config
from core.client import KalshiClient
from core.logger import record_trade
from models.order import ExecutionMode, Order, OrderStatus, Position, SafetyError
from strategies.base import Signal

log = logging.getLogger("prophet.executor")


SafetyHandler = Callable[[SafetyError], Awaitable[None]]
OrderHandler = Callable[[Order], Awaitable[None]]


class Executor:
    """
    Routes trade signals to paper or live execution.

    Callers use `execute(signal, contracts)` and get back an Order whose
    `status` + `mode` reflect what actually happened. Live orders are
    placed through `KalshiClient`; paper orders update the in-memory
    balance and append a row to the portfolio CSV.
    """

    def __init__(
        self,
        client: KalshiClient,
        mode: ExecutionMode,
        starting_balance: float,
        on_order: OrderHandler | None = None,
        on_safety: SafetyHandler | None = None,
    ):
        self.client = client
        self.mode = mode
        self.paper_balance = starting_balance
        self.on_order = on_order
        self.on_safety = on_safety

        self.orders: list[Order] = []
        self.positions: dict[str, Position] = {}

        self._daily_loss: float = 0.0
        self._trade_count_today: int = 0
        self._today: date = date.today()

    # ── Public API ──────────────────────────────────────────────────

    async def execute(self, signal: Signal, contracts: int) -> Order:
        """Route to paper or live execution based on current mode."""
        self._roll_day_if_needed()
        try:
            self._check_safety_rails(signal, contracts)
        except SafetyError as err:
            await self._emit_safety(err)
            order = self._failed_order(signal, contracts, str(err))
            self.orders.append(order)
            await self._emit_order(order)
            return order

        if self.mode == ExecutionMode.PAPER:
            order = self._execute_paper(signal, contracts)
        else:
            order = await self._execute_live(signal, contracts)

        self.orders.append(order)
        if order.status == OrderStatus.FILLED:
            self._record_fill(order)
        await self._emit_order(order)
        return order

    def set_mode(self, mode: ExecutionMode) -> None:
        """Switch modes. Caller is responsible for confirming paper→live."""
        old = self.mode
        self.mode = mode
        log.info("Execution mode: %s → %s", old.value, mode.value)

    async def kill(self) -> list[Order]:
        """
        Emergency stop. Switch to paper and cancel every resting live order.
        Returns the list of orders we attempted to cancel.
        """
        log.warning("KILL SWITCH engaged — switching to paper and cancelling resting orders")
        self.mode = ExecutionMode.PAPER

        resting = [o for o in self.orders if o.status == OrderStatus.RESTING and o.kalshi_order_id]
        for order in resting:
            try:
                await self.client.cancel_order(order.kalshi_order_id)
                order.status = OrderStatus.CANCELLED
                log.info("Cancelled resting order %s (kalshi=%s)", order.id, order.kalshi_order_id)
            except Exception as e:
                order.error = f"cancel failed: {e}"
                log.exception("Failed to cancel order %s", order.id)
            await self._emit_order(order)
        return resting

    # ── Safety rails ────────────────────────────────────────────────

    def _check_safety_rails(self, signal: Signal, contracts: int) -> None:
        # Per-trade dollar cap (signal.price is 0-1 scale → dollars per contract)
        trade_dollars = signal.price * contracts
        if trade_dollars > config.MAX_TRADE_DOLLARS:
            raise SafetyError(
                rule="per_trade_cap",
                message=(
                    f"Trade ${trade_dollars:.2f} exceeds per-trade cap "
                    f"${config.MAX_TRADE_DOLLARS:.2f}"
                ),
            )
        if self._daily_loss >= config.DAILY_LOSS_LIMIT:
            raise SafetyError(
                rule="daily_loss_limit",
                message=(
                    f"Daily loss limit ${config.DAILY_LOSS_LIMIT:.2f} reached "
                    f"(current: ${self._daily_loss:.2f})"
                ),
            )
        if self._trade_count_today >= config.MAX_TRADES_PER_DAY:
            raise SafetyError(
                rule="max_trades_per_day",
                message=(
                    f"Daily trade limit {config.MAX_TRADES_PER_DAY} reached"
                ),
            )

    def _roll_day_if_needed(self) -> None:
        today = date.today()
        if today != self._today:
            self._today = today
            self._daily_loss = 0.0
            self._trade_count_today = 0
            log.info("Daily counters reset (%s)", today.isoformat())

    # ── Paper path ──────────────────────────────────────────────────

    def _execute_paper(self, signal: Signal, contracts: int) -> Order:
        price_cents = int(round(signal.price * 100))
        gross = signal.price * contracts
        fee = gross * config.TRADING_FEE_PCT
        net_cost = gross + fee
        self.paper_balance -= net_cost

        order = Order(
            id=str(uuid.uuid4()),
            ticker=signal.ticker,
            side=_signal_side_to_order_side(signal.side),
            price=price_cents,
            contracts=contracts,
            status=OrderStatus.FILLED,
            mode=ExecutionMode.PAPER,
            fill_price=price_cents,
            fee_cents=int(round(fee * 100)),
        )

        record_trade(
            ticker=signal.ticker,
            side=signal.side,
            entry_price=signal.price,
            contracts=contracts,
            fee=fee,
            net_cost=net_cost,
            balance_after=self.paper_balance,
        )
        return order

    # ── Live path ───────────────────────────────────────────────────

    async def _execute_live(self, signal: Signal, contracts: int) -> Order:
        side = _signal_side_to_order_side(signal.side)
        price_cents = int(round(signal.price * 100))
        internal_id = str(uuid.uuid4())

        order = Order(
            id=internal_id,
            ticker=signal.ticker,
            side=side,
            price=price_cents,
            contracts=contracts,
            status=OrderStatus.PENDING,
            mode=ExecutionMode.LIVE,
        )

        try:
            resp = await self.client.place_order(
                ticker=signal.ticker,
                side=side,
                contracts=contracts,
                price_cents=price_cents,
                client_order_id=internal_id,
            )
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error = str(e)
            log.exception("Live order placement failed for %s", signal.ticker)
            return order

        api_order = resp.get("order", resp) or {}
        order.kalshi_order_id = api_order.get("order_id")
        raw_status = (api_order.get("status") or "").lower()
        order.status = _map_kalshi_status(raw_status)

        fill_price = api_order.get("fill_price") or api_order.get("yes_price") or api_order.get("no_price")
        if fill_price is not None:
            order.fill_price = int(fill_price)

        log.info(
            "LIVE order placed %s (kalshi=%s) status=%s",
            signal.ticker, order.kalshi_order_id, order.status.value,
        )
        return order

    # ── Post-execution bookkeeping ──────────────────────────────────

    def _record_fill(self, order: Order) -> None:
        self._trade_count_today += 1

        # Position tracking — collapse multi-fill into average entry
        key = f"{order.ticker}:{order.side}"
        existing = self.positions.get(key)
        fill = order.fill_price if order.fill_price is not None else order.price
        if existing is None:
            self.positions[key] = Position(
                ticker=order.ticker,
                side=order.side,
                contracts=order.contracts,
                avg_entry_price=fill,
                current_price=fill,
            )
        else:
            total_qty = existing.contracts + order.contracts
            existing.avg_entry_price = int(round(
                (existing.avg_entry_price * existing.contracts + fill * order.contracts)
                / total_qty
            ))
            existing.contracts = total_qty
            existing.current_price = fill

    def mark_loss(self, dollars: float) -> None:
        """Report a realized loss so the daily-loss rail can trip."""
        self._daily_loss += max(dollars, 0.0)
        if self._daily_loss >= config.DAILY_LOSS_LIMIT:
            log.warning(
                "Daily loss limit hit ($%.2f ≥ $%.2f) — reverting to paper mode",
                self._daily_loss, config.DAILY_LOSS_LIMIT,
            )
            if self.mode == ExecutionMode.LIVE:
                self.mode = ExecutionMode.PAPER
                asyncio.create_task(self._emit_safety(SafetyError(
                    rule="daily_loss_limit",
                    message=f"Auto-switched to paper — daily loss ${self._daily_loss:.2f}",
                )))

    # ── Emitters ────────────────────────────────────────────────────

    async def _emit_order(self, order: Order) -> None:
        if self.on_order:
            try:
                await self.on_order(order)
            except Exception:
                log.exception("on_order handler failed")

    async def _emit_safety(self, err: SafetyError) -> None:
        if self.on_safety:
            try:
                await self.on_safety(err)
            except Exception:
                log.exception("on_safety handler failed")

    def _failed_order(self, signal: Signal, contracts: int, reason: str) -> Order:
        price_cents = int(round(signal.price * 100))
        return Order(
            id=str(uuid.uuid4()),
            ticker=signal.ticker,
            side=_signal_side_to_order_side(signal.side),
            price=price_cents,
            contracts=contracts,
            status=OrderStatus.FAILED,
            mode=self.mode,
            error=reason,
        )


def _signal_side_to_order_side(signal_side: str) -> str:
    """Map strategy-layer 'BUY_YES'/'BUY_NO' → Kalshi 'yes'/'no'."""
    return "no" if signal_side.upper().endswith("NO") else "yes"


def _map_kalshi_status(raw: str) -> OrderStatus:
    """Map Kalshi's status string to our OrderStatus enum."""
    mapping = {
        "executed": OrderStatus.FILLED,
        "filled": OrderStatus.FILLED,
        "resting": OrderStatus.RESTING,
        "canceled": OrderStatus.CANCELLED,
        "cancelled": OrderStatus.CANCELLED,
        "pending": OrderStatus.PENDING,
    }
    return mapping.get(raw, OrderStatus.PENDING)
