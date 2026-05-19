"""Broker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from qts.brokers.capabilities import BrokerCapabilities
from qts.core.enums import OrderSide, OrderType
from qts.core.events import FillEvent, OrderEvent
from qts.core.models import (
    AccountSnapshot,
    HealthStatus,
    Order,
    OrderFilters,
    OrderRequest,
    Position,
    ReconciliationReport,
    ReplaceOrderRequest,
)


class Broker(ABC):
    """Abstract broker contract shared by backtest, paper, and live brokers."""

    @abstractmethod
    def get_account(self) -> AccountSnapshot:
        """Return the current account snapshot."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return all positions."""

    @abstractmethod
    def get_position(self, symbol: str) -> Position:
        """Return a single position."""

    @abstractmethod
    def get_buying_power(self, symbol: str, side: OrderSide, order_type: OrderType) -> Decimal:
        """Return buying power available for an order shape."""

    @abstractmethod
    def submit_order(self, order_request: OrderRequest) -> Order:
        """Submit an order."""

    @abstractmethod
    def cancel_order(self, order_id_or_client_order_id: str) -> Order:
        """Cancel an order."""

    @abstractmethod
    def replace_order(self, order_id: str, replace_request: ReplaceOrderRequest) -> Order:
        """Replace an order."""

    @abstractmethod
    def get_order(self, order_id_or_client_order_id: str) -> Order:
        """Return a broker order by internal or client id."""

    @abstractmethod
    def list_orders(self, filters: OrderFilters | None = None) -> list[Order]:
        """List orders matching filters."""

    @abstractmethod
    def list_open_orders(self) -> list[Order]:
        """List open orders."""

    @abstractmethod
    def subscribe_order_updates(self, handler: Callable[[OrderEvent], None]) -> str:
        """Subscribe to order updates."""

    @abstractmethod
    def subscribe_fills(self, handler: Callable[[FillEvent], None]) -> str:
        """Subscribe to fills."""

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Cancel a broker subscription."""

    @abstractmethod
    def reconcile_state(self, local_state: Any) -> ReconciliationReport:
        """Reconcile external broker state with local state."""

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Return broker health."""

    @abstractmethod
    def get_capabilities(self) -> BrokerCapabilities:
        """Return broker capabilities."""
