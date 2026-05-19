"""Order generator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from qts.core.enums import OrderAction, OrderSide, OrderType, TimeInForce
from qts.core.identifiers import new_id
from qts.core.models import AccountSnapshot, MarketSnapshot, OrderIntent, Position, TargetPosition


class OrderGenerator(ABC):
    """Abstract target-to-order-intent contract."""

    @abstractmethod
    def generate_order_intents(
        self,
        targets: list[TargetPosition],
        positions: list[Position],
        account: AccountSnapshot,
        market_data: Any,
    ) -> list[OrderIntent]:
        """Create order intents from target positions."""

    @abstractmethod
    def net_orders(self, order_intents: list[OrderIntent]) -> list[OrderIntent]:
        """Net and de-duplicate order intents."""

    @abstractmethod
    def apply_execution_style(
        self,
        order_intents: list[OrderIntent],
        execution_config: dict[str, Any],
    ) -> list[OrderIntent]:
        """Apply execution style defaults to order intents."""


class DefaultOrderGenerator(OrderGenerator):
    """Generate simple market order intents from target positions."""

    def __init__(
        self,
        *,
        default_order_type: OrderType = OrderType.MARKET,
        default_time_in_force: TimeInForce = TimeInForce.DAY,
        min_qty: Decimal = Decimal("0.000001"),
    ) -> None:
        self.default_order_type = default_order_type
        self.default_time_in_force = default_time_in_force
        self.min_qty = min_qty

    def generate_order_intents(
        self,
        targets: list[TargetPosition],
        positions: list[Position],
        account: AccountSnapshot,
        market_data: Any,
    ) -> list[OrderIntent]:
        position_by_symbol = {position.symbol: position for position in positions}
        snapshot_by_symbol = _snapshot_map(market_data)
        intents: list[OrderIntent] = []
        for target in targets:
            snapshot = snapshot_by_symbol[target.symbol]
            target_qty = self._target_qty(target, account, snapshot)
            current_qty = position_by_symbol.get(target.symbol)
            current = current_qty.qty if current_qty is not None else Decimal("0")
            delta = target_qty - current
            if delta.copy_abs() < self.min_qty:
                continue
            intents.append(
                OrderIntent(
                    intent_id=new_id("intent"),
                    strategy_id=target.strategy_id,
                    symbol=target.symbol,
                    timestamp=target.timestamp,
                    action=self._action(current, target_qty),
                    side=OrderSide.BUY if delta > Decimal("0") else OrderSide.SELL,
                    desired_qty=delta.copy_abs(),
                    order_type=self.default_order_type,
                    time_in_force=self.default_time_in_force,
                    extended_hours=False,
                    source_target_id=target.target_id,
                    source_signal_ids=list(target.source_signal_ids),
                    metadata={"target_qty": str(target_qty), "current_qty": str(current)},
                )
            )
        return self.net_orders(intents)

    def net_orders(self, order_intents: list[OrderIntent]) -> list[OrderIntent]:
        by_symbol: dict[str, OrderIntent] = {}
        for intent in order_intents:
            by_symbol[intent.symbol] = intent
        return list(by_symbol.values())

    def apply_execution_style(
        self,
        order_intents: list[OrderIntent],
        execution_config: dict[str, Any],
    ) -> list[OrderIntent]:
        return [
            intent.model_copy(
                update={
                    "order_type": execution_config.get("default_order_type", intent.order_type),
                    "time_in_force": execution_config.get(
                        "default_time_in_force",
                        intent.time_in_force,
                    ),
                }
            )
            for intent in order_intents
        ]

    def _target_qty(
        self,
        target: TargetPosition,
        account: AccountSnapshot,
        snapshot: MarketSnapshot,
    ) -> Decimal:
        price = _snapshot_price(snapshot)
        if target.target_qty is not None:
            return target.target_qty
        if target.target_notional is not None:
            return target.target_notional / price
        if target.target_weight is not None:
            return account.portfolio_value * target.target_weight / price
        raise ValueError("target has no sizing field")

    def _action(self, current_qty: Decimal, target_qty: Decimal) -> OrderAction:
        if target_qty == Decimal("0"):
            return OrderAction.CLOSE
        if current_qty == Decimal("0"):
            return OrderAction.OPEN
        if target_qty.copy_abs() > current_qty.copy_abs():
            return OrderAction.INCREASE
        if target_qty.copy_abs() < current_qty.copy_abs():
            return OrderAction.REDUCE
        return OrderAction.REBALANCE


def _snapshot_map(market_data: Any) -> dict[str, MarketSnapshot]:
    if isinstance(market_data, MarketSnapshot):
        return {market_data.symbol: market_data}
    if isinstance(market_data, dict):
        return market_data
    raise TypeError("market_data must be a MarketSnapshot or mapping of symbol to MarketSnapshot")


def _snapshot_price(snapshot: MarketSnapshot) -> Decimal:
    if snapshot.latest_bar is not None:
        return snapshot.latest_bar.close
    if snapshot.latest_quote is not None:
        return (snapshot.latest_quote.bid_price + snapshot.latest_quote.ask_price) / Decimal("2")
    if snapshot.latest_trade is not None:
        return snapshot.latest_trade.price
    raise ValueError(f"snapshot has no price for {snapshot.symbol}")
