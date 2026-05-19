"""Order generator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from qts.core.models import AccountSnapshot, OrderIntent, Position, TargetPosition


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

