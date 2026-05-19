"""Alpaca broker adapter.

This module is SDK-optional: tests and dry runs can inject an Alpaca-like client object. Real
SDK construction is intentionally deferred to application wiring so importing this module never
requires Alpaca credentials or external packages.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from qts.brokers.base import Broker
from qts.brokers.capabilities import BrokerCapabilities
from qts.core.enums import (
    AccountStatus,
    AssetClass,
    FillSource,
    HealthState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
)
from qts.core.errors import BrokerError, UnsupportedOperationError
from qts.core.events import FillEvent, OrderEvent
from qts.core.identifiers import new_id
from qts.core.models import (
    AccountSnapshot,
    Fill,
    HealthStatus,
    Order,
    OrderFilters,
    OrderRequest,
    Position,
    QtsModel,
    ReconciliationReport,
    ReplaceOrderRequest,
)
from qts.core.time import ensure_timezone_aware, utc_now


class AlpacaBrokerConfig(QtsModel):
    environment: str
    api_key_env: str
    api_secret_env: str
    paper: bool = True
    base_url: str | None = None

    def load_credentials(self) -> AlpacaCredentials:
        api_key = os.environ.get(self.api_key_env)
        api_secret = os.environ.get(self.api_secret_env)
        if not api_key or not api_secret:
            raise BrokerError(
                f"missing Alpaca credentials in {self.api_key_env}/{self.api_secret_env}"
            )
        return AlpacaCredentials(api_key=api_key, api_secret=api_secret)


class AlpacaCredentials(QtsModel):
    api_key: str
    api_secret: str


class AlpacaOrderMapper:
    """Map between internal order models and Alpaca-compatible payloads."""

    def to_submit_payload(self, order_request: OrderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": order_request.symbol,
            "side": order_request.side.value,
            "type": order_request.order_type.value,
            "time_in_force": order_request.time_in_force.value,
            "extended_hours": order_request.extended_hours,
            "client_order_id": order_request.client_order_id,
        }
        if order_request.qty is not None:
            payload["qty"] = str(order_request.qty)
        if order_request.notional is not None:
            payload["notional"] = str(order_request.notional)
        if order_request.limit_price is not None:
            payload["limit_price"] = str(order_request.limit_price)
        if order_request.stop_price is not None:
            payload["stop_price"] = str(order_request.stop_price)
        if order_request.trail_price is not None:
            payload["trail_price"] = str(order_request.trail_price)
        if order_request.trail_percent is not None:
            payload["trail_percent"] = str(order_request.trail_percent)
        return payload

    def order_from_alpaca(self, raw: Any, *, account_id: str, strategy_id: str = "") -> Order:
        data = _as_dict(raw)
        qty = _optional_decimal(data.get("qty"))
        filled_qty = _decimal(data.get("filled_qty"), Decimal("0"))
        return Order(
            order_id=str(data.get("id") or data.get("order_id") or new_id("alpaca-order")),
            broker_order_id=str(data.get("id")) if data.get("id") is not None else None,
            client_order_id=str(data.get("client_order_id") or ""),
            account_id=account_id,
            strategy_id=str(data.get("strategy_id") or strategy_id or "unknown"),
            symbol=str(data["symbol"]),
            side=OrderSide(str(data["side"])),
            order_type=OrderType(str(data["type"])),
            qty=qty,
            notional=_optional_decimal(data.get("notional")),
            filled_qty=filled_qty,
            remaining_qty=max((qty or Decimal("0")) - filled_qty, Decimal("0")),
            avg_fill_price=_optional_decimal(data.get("filled_avg_price")),
            limit_price=_optional_decimal(data.get("limit_price")),
            stop_price=_optional_decimal(data.get("stop_price")),
            time_in_force=TimeInForce(str(data["time_in_force"])),
            extended_hours=bool(data.get("extended_hours", False)),
            status=map_alpaca_order_status(str(data.get("status", "unknown"))),
            created_at=_timestamp(data.get("created_at")),
            submitted_at=_optional_timestamp(data.get("submitted_at")),
            updated_at=_timestamp(data.get("updated_at")),
            filled_at=_optional_timestamp(data.get("filled_at")),
            canceled_at=_optional_timestamp(data.get("canceled_at")),
            rejected_at=_optional_timestamp(data.get("failed_at")),
            reject_reason=data.get("reject_reason"),
            metadata={"raw_status": data.get("status")},
        )


class AlpacaBroker(Broker):
    """Broker implementation backed by an Alpaca-like trading client."""

    def __init__(
        self,
        *,
        client: Any,
        account_id: str,
        environment: str,
        mapper: AlpacaOrderMapper | None = None,
    ) -> None:
        self.client = client
        self.account_id = account_id
        self.environment = environment
        self.mapper = mapper or AlpacaOrderMapper()
        self._order_update_handlers: dict[str, Callable[[OrderEvent], None]] = {}
        self._fill_handlers: dict[str, Callable[[FillEvent], None]] = {}

    def get_account(self) -> AccountSnapshot:
        raw = _call_first(self.client, ["get_account", "get_account_info"])
        data = _as_dict(raw)
        now = utc_now()
        return AccountSnapshot(
            account_id=self.account_id,
            timestamp=now,
            cash=_decimal(data.get("cash"), Decimal("0")),
            equity=_decimal(data.get("equity"), Decimal("0")),
            buying_power=_decimal(data.get("buying_power"), Decimal("0")),
            portfolio_value=_decimal(data.get("portfolio_value"), Decimal("0")),
            long_market_value=_decimal(data.get("long_market_value"), Decimal("0")),
            short_market_value=_decimal(data.get("short_market_value"), Decimal("0")),
            reserved_buying_power=Decimal("0"),
            initial_margin=_optional_decimal(data.get("initial_margin")),
            maintenance_margin=_optional_decimal(data.get("maintenance_margin")),
            daytrade_count=int(data.get("daytrade_count", 0)),
            status=AccountStatus(str(data.get("status", "unknown")).lower())
            if str(data.get("status", "unknown")).lower() in {item.value for item in AccountStatus}
            else AccountStatus.UNKNOWN,
        )

    def get_positions(self) -> list[Position]:
        raw_positions = _call_first(self.client, ["get_all_positions", "list_positions"])
        return [self._position_from_alpaca(raw) for raw in raw_positions]

    def get_position(self, symbol: str) -> Position:
        try:
            raw = _call_first(self.client, ["get_open_position", "get_position"], symbol)
        except Exception:
            return _flat_position(self.account_id, symbol)
        return self._position_from_alpaca(raw)

    def get_buying_power(self, symbol: str, side: OrderSide, order_type: OrderType) -> Decimal:
        return self.get_account().buying_power

    def submit_order(self, order_request: OrderRequest) -> Order:
        payload = self.mapper.to_submit_payload(order_request)
        try:
            raw_order = _call_first(self.client, ["submit_order"], **payload)
        except TimeoutError:
            raw_order = _call_first(
                self.client,
                ["get_order_by_client_order_id", "get_order"],
                order_request.client_order_id,
            )
        order = self.mapper.order_from_alpaca(
            raw_order,
            account_id=self.account_id,
            strategy_id=order_request.strategy_id,
        )
        self._emit_order_event(order)
        return order

    def cancel_order(self, order_id_or_client_order_id: str) -> Order:
        order = self.get_order(order_id_or_client_order_id)
        _call_first(
            self.client,
            ["cancel_order_by_id", "cancel_order"],
            order.broker_order_id or order.order_id,
        )
        refreshed = self.get_order(order_id_or_client_order_id)
        self._emit_order_event(refreshed)
        return refreshed

    def replace_order(self, order_id: str, replace_request: ReplaceOrderRequest) -> Order:
        payload = replace_request.to_dict()
        raw = _call_first(
            self.client,
            ["replace_order_by_id", "replace_order"],
            order_id,
            **payload,
        )
        order = self.mapper.order_from_alpaca(raw, account_id=self.account_id)
        self._emit_order_event(order)
        return order

    def get_order(self, order_id_or_client_order_id: str) -> Order:
        raw = _call_first(
            self.client,
            ["get_order_by_id", "get_order", "get_order_by_client_order_id"],
            order_id_or_client_order_id,
        )
        return self.mapper.order_from_alpaca(raw, account_id=self.account_id)

    def list_orders(self, filters: OrderFilters | None = None) -> list[Order]:
        raw_orders = _call_first(self.client, ["get_orders", "list_orders"])
        orders = [
            self.mapper.order_from_alpaca(raw, account_id=self.account_id)
            for raw in raw_orders
        ]
        if filters is None:
            return orders
        return [
            order
            for order in orders
            if (filters.symbol is None or order.symbol == filters.symbol)
            and (filters.status is None or order.status is filters.status)
            and (not filters.open_only or order.status not in _TERMINAL_STATUSES)
        ]

    def list_open_orders(self) -> list[Order]:
        return self.list_orders(OrderFilters(open_only=True))

    def subscribe_order_updates(self, handler: Callable[[OrderEvent], None]) -> str:
        subscription_id = new_id("alpaca-order-sub")
        self._order_update_handlers[subscription_id] = handler
        return subscription_id

    def subscribe_fills(self, handler: Callable[[FillEvent], None]) -> str:
        subscription_id = new_id("alpaca-fill-sub")
        self._fill_handlers[subscription_id] = handler
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        self._order_update_handlers.pop(subscription_id, None)
        self._fill_handlers.pop(subscription_id, None)

    def reconcile_state(self, local_state: Any) -> ReconciliationReport:
        local_positions = {
            position.symbol: position.qty
            for position in local_state.get("positions", [])
        } if isinstance(local_state, dict) else {}
        broker_positions = {position.symbol: position.qty for position in self.get_positions()}
        discrepancies = []
        for symbol, broker_qty in broker_positions.items():
            if local_positions and local_positions.get(symbol) != broker_qty:
                discrepancies.append(
                    f"position mismatch {symbol}: "
                    f"local={local_positions.get(symbol)} broker={broker_qty}"
                )
        return ReconciliationReport(
            timestamp=utc_now(),
            matched=not discrepancies,
            discrepancies=discrepancies,
        )

    def health_check(self) -> HealthStatus:
        try:
            self.get_account()
        except Exception as exc:
            return HealthStatus(
                status=HealthState.UNAVAILABLE,
                checked_at=utc_now(),
                message=str(exc),
            )
        return HealthStatus(status=HealthState.OK, checked_at=utc_now())

    def get_capabilities(self) -> BrokerCapabilities:
        return alpaca_capabilities()

    def handle_trade_update(self, raw_update: Any) -> None:
        data = _as_dict(raw_update)
        if data.get("event") == "fill" and data.get("order") is not None:
            order = self.mapper.order_from_alpaca(data["order"], account_id=self.account_id)
            fill = Fill(
                fill_id=str(data.get("execution_id") or new_id("alpaca-fill")),
                order_id=order.order_id,
                broker_order_id=order.broker_order_id,
                symbol=order.symbol,
                side=order.side,
                qty=_decimal(data.get("qty"), order.filled_qty),
                price=_decimal(data.get("price"), order.avg_fill_price or Decimal("0")),
                commission=Decimal("0"),
                fees=Decimal("0"),
                timestamp=_timestamp(data.get("timestamp")),
                source=(
                    FillSource.ALPACA_PAPER
                    if self.environment == "paper"
                    else FillSource.ALPACA_LIVE
                ),
            )
            self._emit_fill_event(fill)
        elif data.get("order") is not None:
            self._emit_order_event(
                self.mapper.order_from_alpaca(data["order"], account_id=self.account_id)
            )

    def _position_from_alpaca(self, raw: Any) -> Position:
        data = _as_dict(raw)
        qty = _decimal(data.get("qty"), Decimal("0"))
        market_price = _optional_decimal(data.get("current_price"))
        market_value = _optional_decimal(data.get("market_value"))
        side = PositionSide.FLAT
        if qty > Decimal("0"):
            side = PositionSide.LONG
        elif qty < Decimal("0"):
            side = PositionSide.SHORT
        return Position(
            account_id=self.account_id,
            symbol=str(data["symbol"]),
            qty=qty,
            avg_entry_price=_decimal(data.get("avg_entry_price"), Decimal("0")),
            market_price=market_price,
            market_value=market_value,
            cost_basis=_decimal(data.get("cost_basis"), Decimal("0")),
            unrealized_pnl=_optional_decimal(data.get("unrealized_pl")),
            realized_pnl=Decimal("0"),
            side=side,
            updated_at=utc_now(),
        )

    def _emit_order_event(self, order: Order) -> None:
        event = OrderEvent(
            event_id=new_id("event"),
            timestamp=utc_now(),
            source=f"alpaca_{self.environment}",
            order=order,
        )
        for handler in self._order_update_handlers.values():
            handler(event)

    def _emit_fill_event(self, fill: Fill) -> None:
        event = FillEvent(
            event_id=new_id("event"),
            timestamp=fill.timestamp,
            source=f"alpaca_{self.environment}",
            fill=fill,
        )
        for handler in self._fill_handlers.values():
            handler(event)


class AlpacaPaperBroker(AlpacaBroker):
    def __init__(self, *, client: Any, account_id: str = "alpaca-paper") -> None:
        super().__init__(client=client, account_id=account_id, environment="paper")


class AlpacaLiveBroker(AlpacaBroker):
    def __init__(self, *, client: Any, account_id: str = "alpaca-live") -> None:
        super().__init__(client=client, account_id=account_id, environment="live")


def alpaca_capabilities() -> BrokerCapabilities:
    return BrokerCapabilities(
        supported_asset_classes=[AssetClass.EQUITY, AssetClass.CRYPTO],
        supported_order_types=[
            OrderType.MARKET,
            OrderType.LIMIT,
            OrderType.STOP,
            OrderType.STOP_LIMIT,
            OrderType.TRAILING_STOP,
        ],
        supported_time_in_force=[
            TimeInForce.DAY,
            TimeInForce.GTC,
            TimeInForce.IOC,
            TimeInForce.FOK,
            TimeInForce.OPG,
            TimeInForce.CLS,
        ],
        supports_fractional=True,
        supports_short=True,
        supports_extended_hours=True,
        supports_order_replace=True,
        supports_streaming_order_updates=True,
        max_client_order_id_length=48,
    )


def map_alpaca_order_status(status: str) -> OrderStatus:
    mapping = {
        "accepted": OrderStatus.ACCEPTED,
        "new": OrderStatus.NEW,
        "partially_filled": OrderStatus.PARTIALLY_FILLED,
        "filled": OrderStatus.FILLED,
        "pending_cancel": OrderStatus.PENDING_CANCEL,
        "canceled": OrderStatus.CANCELED,
        "pending_replace": OrderStatus.PENDING_REPLACE,
        "replaced": OrderStatus.REPLACED,
        "expired": OrderStatus.EXPIRED,
        "done_for_day": OrderStatus.DONE_FOR_DAY,
        "rejected": OrderStatus.REJECTED,
        "suspended": OrderStatus.SUSPENDED,
    }
    return mapping.get(status.lower(), OrderStatus.UNKNOWN)


_TERMINAL_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}


def _call_first(client: Any, names: list[str], *args: Any, **kwargs: Any) -> Any:
    for name in names:
        method = getattr(client, name, None)
        if method is not None:
            return method(*args, **kwargs)
    raise UnsupportedOperationError(f"client supports none of: {', '.join(names)}")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TypeError(f"cannot map Alpaca object: {type(value).__name__}")


def _decimal(value: Any, default: Decimal) -> Decimal:
    if value in {None, ""}:
        return default
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    return Decimal(str(value))


def _timestamp(value: Any) -> datetime:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        return ensure_timezone_aware(value)
    return ensure_timezone_aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def _optional_timestamp(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    return _timestamp(value)


def _flat_position(account_id: str, symbol: str) -> Position:
    return Position(
        account_id=account_id,
        symbol=symbol,
        qty=Decimal("0"),
        avg_entry_price=Decimal("0"),
        market_price=Decimal("0"),
        market_value=Decimal("0"),
        cost_basis=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        realized_pnl=Decimal("0"),
        side=PositionSide.FLAT,
        updated_at=utc_now(),
    )
