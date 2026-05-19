"""Simulated brokerage implementation for deterministic backtests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from qts.backtest.fill_model import DefaultBacktestFillModel, FillModel, snapshot_from_market_event
from qts.brokers.base import Broker
from qts.brokers.capabilities import BrokerCapabilities
from qts.core.enums import (
    AccountStatus,
    AssetClass,
    EventType,
    HealthState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
)
from qts.core.errors import BrokerError, UnsupportedOperationError
from qts.core.events import BaseEvent, FillEvent, OrderEvent
from qts.core.identifiers import new_id
from qts.core.models import (
    AccountSnapshot,
    Fill,
    FillResult,
    HealthStatus,
    Instrument,
    MarketSnapshot,
    Order,
    OrderFilters,
    OrderRequest,
    Position,
    ReconciliationReport,
    ReplaceOrderRequest,
)
from qts.core.time import ensure_timezone_aware, utc_now
from qts.execution.state_machine import (
    is_terminal_status,
    validate_order_transition,
)


class BacktestBroker(Broker):
    """Stateful simulated brokerage for historical event replay."""

    def __init__(
        self,
        *,
        account_id: str,
        initial_cash: Decimal,
        instruments: list[Instrument],
        current_time: datetime | None = None,
        fill_model: FillModel | None = None,
        capabilities: BrokerCapabilities | None = None,
        allow_short: bool = False,
        market_order_safety_buffer: Decimal = Decimal("1.05"),
    ) -> None:
        self.account_id = account_id
        self._cash = initial_cash
        self.current_time = ensure_timezone_aware(current_time or utc_now())
        self.fill_model = fill_model or DefaultBacktestFillModel()
        self.capabilities = capabilities or default_backtest_capabilities(allow_short=allow_short)
        self.allow_short = allow_short
        self.market_order_safety_buffer = market_order_safety_buffer

        self.instruments_by_symbol = {instrument.symbol: instrument for instrument in instruments}
        self.positions_by_symbol: dict[str, Position] = {}
        self.open_orders_by_id: dict[str, Order] = {}
        self.closed_orders_by_id: dict[str, Order] = {}
        self.rejected_orders_by_id: dict[str, Order] = {}
        self.fills_by_order_id: dict[str, list[Fill]] = {}
        self.reserved_buying_power_by_order_id: dict[str, Decimal] = {}
        self.reserved_sell_qty_by_order_id: dict[str, Decimal] = {}
        self.latest_market_snapshots: dict[str, MarketSnapshot] = {}
        self.client_order_ids: dict[str, str] = {}
        self._order_update_handlers: dict[str, Callable[[OrderEvent], None]] = {}
        self._fill_handlers: dict[str, Callable[[FillEvent], None]] = {}

    def get_account(self) -> AccountSnapshot:
        long_market_value = Decimal("0")
        short_market_value = Decimal("0")
        for position in self.positions_by_symbol.values():
            if position.qty > Decimal("0"):
                long_market_value += position.market_value or Decimal("0")
            elif position.qty < Decimal("0"):
                short_market_value += (position.market_value or Decimal("0")).copy_abs()
        equity = self._cash + long_market_value - short_market_value
        reserved = self._reserved_buying_power()
        return AccountSnapshot(
            account_id=self.account_id,
            timestamp=self.current_time,
            cash=self._cash,
            equity=equity,
            buying_power=max(self._cash - reserved, Decimal("0")),
            portfolio_value=equity,
            long_market_value=long_market_value,
            short_market_value=short_market_value,
            reserved_buying_power=reserved,
            status=AccountStatus.ACTIVE,
        )

    def get_positions(self) -> list[Position]:
        return list(self.positions_by_symbol.values())

    def get_position(self, symbol: str) -> Position:
        return self.positions_by_symbol.get(symbol, self._flat_position(symbol))

    def get_buying_power(self, symbol: str, side: OrderSide, order_type: OrderType) -> Decimal:
        account = self.get_account()
        return account.buying_power if side is OrderSide.BUY else Decimal("0")

    def submit_order(self, order_request: OrderRequest) -> Order:
        submitted_at = ensure_timezone_aware(order_request.submitted_at or self.current_time)
        self.current_time = max(self.current_time, submitted_at)
        rejection_reason = self._validate_order_request(order_request)
        if rejection_reason is not None:
            return self._reject_order_request(order_request, rejection_reason)

        requested_qty = self._request_qty(order_request)
        reservation = self._calculate_buying_power_reservation(order_request, requested_qty)
        reserved_sell_qty = self._calculate_sell_qty_reservation(order_request, requested_qty)
        order = Order(
            order_id=new_id("order"),
            broker_order_id=new_id("bt"),
            client_order_id=order_request.client_order_id,
            account_id=order_request.account_id,
            strategy_id=order_request.strategy_id,
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=requested_qty,
            notional=order_request.notional,
            filled_qty=Decimal("0"),
            remaining_qty=requested_qty,
            avg_fill_price=None,
            limit_price=order_request.limit_price,
            stop_price=order_request.stop_price,
            time_in_force=order_request.time_in_force,
            extended_hours=order_request.extended_hours,
            status=OrderStatus.CREATED,
            created_at=self.current_time,
            submitted_at=self.current_time,
            updated_at=self.current_time,
            metadata=dict(order_request.metadata),
        )
        order = self._transition_order(order, OrderStatus.SUBMITTED)
        order = self._transition_order(order, OrderStatus.ACCEPTED)
        order = self._transition_order(order, OrderStatus.NEW)
        self.open_orders_by_id[order.order_id] = order
        self.client_order_ids[order.client_order_id] = order.order_id
        if reservation > Decimal("0"):
            self.reserved_buying_power_by_order_id[order.order_id] = reservation
        if reserved_sell_qty > Decimal("0"):
            self.reserved_sell_qty_by_order_id[order.order_id] = reserved_sell_qty
        self._emit_order_event(order)
        return order

    def cancel_order(self, order_id_or_client_order_id: str) -> Order:
        order = self._get_open_order(order_id_or_client_order_id)
        order = self._transition_order(order, OrderStatus.PENDING_CANCEL)
        order = self._transition_order(order, OrderStatus.CANCELED, canceled_at=self.current_time)
        self._close_order(order)
        self._release_reservations(order.order_id)
        self._emit_order_event(order)
        return order

    def replace_order(self, order_id: str, replace_request: ReplaceOrderRequest) -> Order:
        if not self.capabilities.supports_order_replace:
            raise UnsupportedOperationError("backtest broker does not support order replacement")
        order = self._get_open_order(order_id)
        order = self._transition_order(order, OrderStatus.PENDING_REPLACE)
        self._release_reservations(order.order_id)
        order = order.model_copy(
            update={
                "qty": replace_request.qty if replace_request.qty is not None else order.qty,
                "notional": (
                    replace_request.notional
                    if replace_request.notional is not None
                    else order.notional
                ),
                "limit_price": (
                    replace_request.limit_price
                    if replace_request.limit_price is not None
                    else order.limit_price
                ),
                "stop_price": (
                    replace_request.stop_price
                    if replace_request.stop_price is not None
                    else order.stop_price
                ),
                "time_in_force": (
                    replace_request.time_in_force
                    if replace_request.time_in_force is not None
                    else order.time_in_force
                ),
                "updated_at": self.current_time,
            }
        )
        order = self._transition_order(order, OrderStatus.REPLACED)
        order = self._transition_order(order, OrderStatus.NEW)
        remaining_qty = (order.qty or Decimal("0")) - order.filled_qty
        order = order.model_copy(update={"remaining_qty": remaining_qty})
        synthetic_request = _order_to_request(order)
        self.reserved_buying_power_by_order_id[order.order_id] = (
            self._calculate_buying_power_reservation(synthetic_request, remaining_qty)
        )
        self.open_orders_by_id[order.order_id] = order
        self._emit_order_event(order)
        return order

    def get_order(self, order_id_or_client_order_id: str) -> Order:
        order_id = self.client_order_ids.get(
            order_id_or_client_order_id,
            order_id_or_client_order_id,
        )
        if order_id in self.open_orders_by_id:
            return self.open_orders_by_id[order_id]
        if order_id in self.closed_orders_by_id:
            return self.closed_orders_by_id[order_id]
        if order_id in self.rejected_orders_by_id:
            return self.rejected_orders_by_id[order_id]
        raise BrokerError(f"unknown order: {order_id_or_client_order_id}")

    def list_orders(self, filters: OrderFilters | None = None) -> list[Order]:
        orders = [
            *self.open_orders_by_id.values(),
            *self.closed_orders_by_id.values(),
            *self.rejected_orders_by_id.values(),
        ]
        if filters is None:
            return sorted(orders, key=lambda order: order.created_at)
        filtered = []
        for order in orders:
            if filters.open_only and order.order_id not in self.open_orders_by_id:
                continue
            if filters.symbol is not None and order.symbol != filters.symbol:
                continue
            if filters.status is not None and order.status is not filters.status:
                continue
            if filters.start is not None and order.created_at < filters.start:
                continue
            if filters.end is not None and order.created_at > filters.end:
                continue
            filtered.append(order)
        return sorted(filtered, key=lambda order: order.created_at)

    def list_open_orders(self) -> list[Order]:
        return list(self.open_orders_by_id.values())

    def subscribe_order_updates(self, handler: Callable[[OrderEvent], None]) -> str:
        subscription_id = new_id("order-sub")
        self._order_update_handlers[subscription_id] = handler
        return subscription_id

    def subscribe_fills(self, handler: Callable[[FillEvent], None]) -> str:
        subscription_id = new_id("fill-sub")
        self._fill_handlers[subscription_id] = handler
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        self._order_update_handlers.pop(subscription_id, None)
        self._fill_handlers.pop(subscription_id, None)

    def reconcile_state(self, local_state: Any) -> ReconciliationReport:
        return ReconciliationReport(
            timestamp=self.current_time,
            matched=True,
            metadata={"open_orders": len(self.open_orders_by_id)},
        )

    def health_check(self) -> HealthStatus:
        return HealthStatus(status=HealthState.OK, checked_at=self.current_time)

    def get_capabilities(self) -> BrokerCapabilities:
        return self.capabilities

    def process_market_event(self, market_event: BaseEvent) -> list[Fill]:
        """Process one market event against currently open orders."""

        self.current_time = market_event.timestamp
        snapshot = snapshot_from_market_event(market_event)
        self.latest_market_snapshots[snapshot.symbol] = snapshot
        self._mark_position_to_market(snapshot)
        open_orders = list(self.open_orders_by_id.values())
        results = self.fill_model.process_open_orders(open_orders, market_event, self)
        emitted_fills: list[Fill] = []
        for result in results:
            emitted_fills.extend(self._apply_fill_result(result))
        return emitted_fills

    def set_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Seed latest market data for reservation estimates."""

        self.latest_market_snapshots[snapshot.symbol] = snapshot
        self.current_time = max(self.current_time, snapshot.timestamp)
        self._mark_position_to_market(snapshot)

    def _validate_order_request(self, order_request: OrderRequest) -> str | None:
        if order_request.account_id != self.account_id:
            return "account_id does not match broker account"
        if order_request.client_order_id in self.client_order_ids:
            return "duplicate client_order_id"
        if len(order_request.client_order_id) > self.capabilities.max_client_order_id_length:
            return "client_order_id exceeds broker limit"
        instrument = self.instruments_by_symbol.get(order_request.symbol)
        if instrument is None:
            return f"unknown symbol: {order_request.symbol}"
        if not instrument.tradable:
            return f"symbol is not tradable: {order_request.symbol}"
        if order_request.order_type not in self.capabilities.supported_order_types:
            return f"unsupported order type: {order_request.order_type.value}"
        if order_request.time_in_force not in self.capabilities.supported_time_in_force:
            return f"unsupported time in force: {order_request.time_in_force.value}"
        requested_qty = self._request_qty(order_request)
        if requested_qty <= Decimal("0"):
            return "order quantity must be positive"
        if (
            not self.capabilities.supports_fractional
            and requested_qty % Decimal("1") != Decimal("0")
        ):
            return "fractional quantity is not supported"
        if order_request.side is OrderSide.BUY:
            reservation = self._calculate_buying_power_reservation(order_request, requested_qty)
            if reservation > self.get_account().buying_power:
                return "insufficient buying power"
        elif not self.allow_short:
            available_qty = self._available_sell_qty(order_request.symbol)
            if requested_qty > available_qty:
                return "sell quantity exceeds available long position"
        return None

    def _request_qty(self, order_request: OrderRequest) -> Decimal:
        if order_request.qty is not None:
            return order_request.qty
        if order_request.notional is None:
            raise BrokerError("order request has neither qty nor notional")
        estimate = self._estimated_order_price(order_request)
        return order_request.notional / estimate

    def _estimated_order_price(self, order_request: OrderRequest) -> Decimal:
        if order_request.order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT}:
            if order_request.limit_price is None:
                raise BrokerError("limit order requires limit price")
            return order_request.limit_price
        if order_request.order_type is OrderType.STOP and order_request.stop_price is not None:
            return order_request.stop_price * self.market_order_safety_buffer
        snapshot = self.latest_market_snapshots.get(order_request.symbol)
        if snapshot is None:
            if order_request.notional is not None:
                return Decimal("1")
            raise BrokerError(f"no market snapshot available for {order_request.symbol}")
        if snapshot.latest_quote is not None:
            return (
                snapshot.latest_quote.ask_price
                if order_request.side is OrderSide.BUY
                else snapshot.latest_quote.bid_price
            )
        if snapshot.latest_bar is not None:
            return snapshot.latest_bar.close
        if snapshot.latest_trade is not None:
            return snapshot.latest_trade.price
        raise BrokerError(f"market snapshot has no price for {order_request.symbol}")

    def _calculate_buying_power_reservation(
        self,
        order_request: OrderRequest,
        requested_qty: Decimal,
    ) -> Decimal:
        if order_request.side is not OrderSide.BUY:
            return Decimal("0")
        if order_request.notional is not None:
            return order_request.notional
        estimated_price = self._estimated_order_price(order_request)
        if order_request.order_type in {OrderType.MARKET, OrderType.STOP}:
            estimated_price *= self.market_order_safety_buffer
        return estimated_price * requested_qty

    def _calculate_sell_qty_reservation(
        self,
        order_request: OrderRequest,
        requested_qty: Decimal,
    ) -> Decimal:
        if order_request.side is OrderSide.SELL and not self.allow_short:
            return requested_qty
        return Decimal("0")

    def _available_sell_qty(self, symbol: str) -> Decimal:
        position = self.get_position(symbol)
        reserved = sum(
            qty
            for order_id, qty in self.reserved_sell_qty_by_order_id.items()
            if self.open_orders_by_id[order_id].symbol == symbol
        )
        return max(position.qty - reserved, Decimal("0"))

    def _apply_fill_result(self, result: FillResult) -> list[Fill]:
        if result.order_id not in self.open_orders_by_id:
            return []
        order = self.open_orders_by_id[result.order_id]
        if not result.fills:
            return []
        emitted: list[Fill] = []
        previous_remaining = order.remaining_qty
        for fill in result.fills:
            order = self._apply_fill_to_order(order, fill)
            self._apply_fill_to_account_and_position(fill)
            self.fills_by_order_id.setdefault(order.order_id, []).append(fill)
            self._release_reservation_for_fill(order.order_id, fill.qty, previous_remaining)
            previous_remaining = order.remaining_qty
            self._emit_fill_event(fill)
            emitted.append(fill)
        order = order.model_copy(
            update={
                "remaining_qty": result.remaining_qty,
                "status": result.status_after_fill,
                "updated_at": self.current_time,
                "filled_at": (
                    self.current_time
                    if result.status_after_fill is OrderStatus.FILLED
                    else order.filled_at
                ),
            }
        )
        self.open_orders_by_id[order.order_id] = order
        if is_terminal_status(order.status):
            self._release_reservations(order.order_id)
            self._close_order(order)
        self._emit_order_event(order)
        return emitted

    def _apply_fill_to_order(self, order: Order, fill: Fill) -> Order:
        filled_qty = order.filled_qty + fill.qty
        remaining_qty = max(order.remaining_qty - fill.qty, Decimal("0"))
        previous_notional = (order.avg_fill_price or Decimal("0")) * order.filled_qty
        new_notional = previous_notional + fill.price * fill.qty
        avg_fill_price = new_notional / filled_qty if filled_qty > Decimal("0") else None
        status = (
            OrderStatus.FILLED
            if remaining_qty <= Decimal("0")
            else OrderStatus.PARTIALLY_FILLED
        )
        return order.model_copy(
            update={
                "filled_qty": filled_qty,
                "remaining_qty": remaining_qty,
                "avg_fill_price": avg_fill_price,
                "status": status,
                "updated_at": fill.timestamp,
                "filled_at": fill.timestamp if status is OrderStatus.FILLED else None,
            }
        )

    def _apply_fill_to_account_and_position(self, fill: Fill) -> None:
        fill_value = fill.qty * fill.price
        total_cost = fill.commission + fill.fees
        current = self.get_position(fill.symbol)
        if fill.side is OrderSide.BUY:
            self._cash -= fill_value + total_cost
            updated = self._apply_buy_fill(current, fill)
        else:
            self._cash += fill_value - total_cost
            updated = self._apply_sell_fill(current, fill)
        self.positions_by_symbol[fill.symbol] = updated

    def _apply_buy_fill(self, current: Position, fill: Fill) -> Position:
        old_qty = current.qty
        new_qty = old_qty + fill.qty
        if new_qty <= Decimal("0"):
            return current.model_copy(update={"qty": new_qty, "updated_at": fill.timestamp})
        previous_cost = current.avg_entry_price * max(old_qty, Decimal("0"))
        added_cost = fill.price * fill.qty
        avg_entry_price = (previous_cost + added_cost) / new_qty
        return Position(
            account_id=self.account_id,
            symbol=fill.symbol,
            qty=new_qty,
            avg_entry_price=avg_entry_price,
            market_price=fill.price,
            market_value=new_qty * fill.price,
            cost_basis=new_qty * avg_entry_price,
            unrealized_pnl=(fill.price - avg_entry_price) * new_qty,
            realized_pnl=current.realized_pnl or Decimal("0"),
            side=PositionSide.LONG,
            updated_at=fill.timestamp,
        )

    def _apply_sell_fill(self, current: Position, fill: Fill) -> Position:
        old_qty = current.qty
        closing_qty = min(fill.qty, max(old_qty, Decimal("0")))
        realized_before = current.realized_pnl or Decimal("0")
        realized = realized_before + (fill.price - current.avg_entry_price) * closing_qty
        realized -= fill.commission + fill.fees
        new_qty = old_qty - fill.qty
        if new_qty <= Decimal("0"):
            return Position(
                account_id=self.account_id,
                symbol=fill.symbol,
                qty=new_qty,
                avg_entry_price=Decimal("0") if new_qty == Decimal("0") else fill.price,
                market_price=fill.price,
                market_value=new_qty * fill.price,
                cost_basis=Decimal("0") if new_qty == Decimal("0") else new_qty * fill.price,
                unrealized_pnl=Decimal("0"),
                realized_pnl=realized,
                side=PositionSide.FLAT if new_qty == Decimal("0") else PositionSide.SHORT,
                updated_at=fill.timestamp,
            )
        return Position(
            account_id=self.account_id,
            symbol=fill.symbol,
            qty=new_qty,
            avg_entry_price=current.avg_entry_price,
            market_price=fill.price,
            market_value=new_qty * fill.price,
            cost_basis=new_qty * current.avg_entry_price,
            unrealized_pnl=(fill.price - current.avg_entry_price) * new_qty,
            realized_pnl=realized,
            side=PositionSide.LONG,
            updated_at=fill.timestamp,
        )

    def _mark_position_to_market(self, snapshot: MarketSnapshot) -> None:
        position = self.positions_by_symbol.get(snapshot.symbol)
        price = _snapshot_price(snapshot)
        if position is None or price is None:
            return
        self.positions_by_symbol[snapshot.symbol] = position.model_copy(
            update={
                "market_price": price,
                "market_value": position.qty * price,
                "unrealized_pnl": (price - position.avg_entry_price) * position.qty,
                "updated_at": snapshot.timestamp,
            }
        )

    def _flat_position(self, symbol: str) -> Position:
        return Position(
            account_id=self.account_id,
            symbol=symbol,
            qty=Decimal("0"),
            avg_entry_price=Decimal("0"),
            market_price=_snapshot_price(self.latest_market_snapshots.get(symbol)),
            market_value=Decimal("0"),
            cost_basis=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            side=PositionSide.FLAT,
            updated_at=self.current_time,
        )

    def _transition_order(
        self,
        order: Order,
        status: OrderStatus,
        **updates: Any,
    ) -> Order:
        validate_order_transition(order.status, status)
        return order.model_copy(
            update={
                "status": status,
                "updated_at": self.current_time,
                **updates,
            }
        )

    def _close_order(self, order: Order) -> None:
        self.open_orders_by_id.pop(order.order_id, None)
        self.closed_orders_by_id[order.order_id] = order

    def _reject_order_request(self, order_request: OrderRequest, reason: str) -> Order:
        order = Order(
            order_id=new_id("order"),
            client_order_id=order_request.client_order_id,
            account_id=order_request.account_id,
            strategy_id=order_request.strategy_id,
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=order_request.qty,
            notional=order_request.notional,
            filled_qty=Decimal("0"),
            remaining_qty=order_request.qty or Decimal("0"),
            limit_price=order_request.limit_price,
            stop_price=order_request.stop_price,
            time_in_force=order_request.time_in_force,
            extended_hours=order_request.extended_hours,
            status=OrderStatus.REJECTED,
            created_at=self.current_time,
            updated_at=self.current_time,
            rejected_at=self.current_time,
            reject_reason=reason,
            metadata=dict(order_request.metadata),
        )
        self.rejected_orders_by_id[order.order_id] = order
        self.client_order_ids[order.client_order_id] = order.order_id
        self._emit_order_event(order)
        return order

    def _release_reservation_for_fill(
        self,
        order_id: str,
        fill_qty: Decimal,
        previous_remaining: Decimal,
    ) -> None:
        if previous_remaining <= Decimal("0"):
            return
        if order_id in self.reserved_buying_power_by_order_id:
            current_reservation = self.reserved_buying_power_by_order_id[order_id]
            release = min(current_reservation, current_reservation * fill_qty / previous_remaining)
            remaining_reservation = current_reservation - release
            if remaining_reservation <= Decimal("0"):
                self.reserved_buying_power_by_order_id.pop(order_id, None)
            else:
                self.reserved_buying_power_by_order_id[order_id] = remaining_reservation
        if order_id in self.reserved_sell_qty_by_order_id:
            current_sell_reservation = self.reserved_sell_qty_by_order_id[order_id]
            remaining_sell_reservation = max(current_sell_reservation - fill_qty, Decimal("0"))
            if remaining_sell_reservation <= Decimal("0"):
                self.reserved_sell_qty_by_order_id.pop(order_id, None)
            else:
                self.reserved_sell_qty_by_order_id[order_id] = remaining_sell_reservation

    def _release_reservations(self, order_id: str) -> None:
        self.reserved_buying_power_by_order_id.pop(order_id, None)
        self.reserved_sell_qty_by_order_id.pop(order_id, None)

    def _reserved_buying_power(self) -> Decimal:
        return sum(self.reserved_buying_power_by_order_id.values(), Decimal("0"))

    def _get_open_order(self, order_id_or_client_order_id: str) -> Order:
        order_id = self.client_order_ids.get(
            order_id_or_client_order_id,
            order_id_or_client_order_id,
        )
        try:
            return self.open_orders_by_id[order_id]
        except KeyError as exc:
            raise BrokerError(f"order is not open: {order_id_or_client_order_id}") from exc

    def _emit_order_event(self, order: Order) -> None:
        event = OrderEvent(
            event_id=new_id("event"),
            event_type=EventType.ORDER,
            timestamp=self.current_time,
            source="backtest_broker",
            order=order,
        )
        for handler in self._order_update_handlers.values():
            handler(event)

    def _emit_fill_event(self, fill: Fill) -> None:
        event = FillEvent(
            event_id=new_id("event"),
            event_type=EventType.FILL,
            timestamp=fill.timestamp,
            source="backtest_broker",
            fill=fill,
        )
        for handler in self._fill_handlers.values():
            handler(event)


def default_backtest_capabilities(*, allow_short: bool = False) -> BrokerCapabilities:
    return BrokerCapabilities(
        supported_asset_classes=[AssetClass.EQUITY],
        supported_order_types=[
            OrderType.MARKET,
            OrderType.LIMIT,
            OrderType.STOP,
            OrderType.STOP_LIMIT,
        ],
        supported_time_in_force=[TimeInForce.DAY, TimeInForce.GTC],
        supports_fractional=True,
        supports_short=allow_short,
        supports_extended_hours=False,
        supports_order_replace=True,
        supports_streaming_order_updates=True,
        max_client_order_id_length=48,
    )


def _snapshot_price(snapshot: MarketSnapshot | None) -> Decimal | None:
    if snapshot is None:
        return None
    if snapshot.latest_bar is not None:
        return snapshot.latest_bar.close
    if snapshot.latest_quote is not None:
        return (snapshot.latest_quote.bid_price + snapshot.latest_quote.ask_price) / Decimal("2")
    if snapshot.latest_trade is not None:
        return snapshot.latest_trade.price
    return None


def _order_to_request(order: Order) -> OrderRequest:
    return OrderRequest(
        client_order_id=order.client_order_id,
        strategy_id=order.strategy_id,
        account_id=order.account_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        qty=order.remaining_qty,
        limit_price=order.limit_price,
        stop_price=order.stop_price,
        time_in_force=order.time_in_force,
        extended_hours=order.extended_hours,
        submitted_at=order.submitted_at,
        metadata=dict(order.metadata),
    )
