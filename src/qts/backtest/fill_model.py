"""Backtest fill model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from qts.core.events import BaseEvent
from qts.core.models import FillResult, MarketSnapshot, Order


class FillModel(ABC):
    """Abstract fill model contract for simulated execution."""

    @abstractmethod
    def process_order(
        self,
        order: Order,
        market_event: BaseEvent,
        broker_state: object,
    ) -> FillResult:
        """Process one order against one market event."""

    @abstractmethod
    def process_open_orders(
        self,
        open_orders: list[Order],
        market_event: BaseEvent,
        broker_state: object,
    ) -> list[FillResult]:
        """Process open orders against one market event."""

    @abstractmethod
    def estimate_market_price(self, order: Order, market_snapshot: MarketSnapshot) -> Decimal:
        """Estimate the fill reference price for a market order."""

    @abstractmethod
    def check_trigger(self, order: Order, market_event: BaseEvent) -> bool:
        """Return whether an order trigger condition is met."""

    @abstractmethod
    def calculate_slippage(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
    ) -> Decimal:
        """Calculate slippage for an order."""

    @abstractmethod
    def calculate_commission(self, order: Order, fill_qty: Decimal, fill_price: Decimal) -> Decimal:
        """Calculate commission for a fill."""
