"""Slippage model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from qts.core.models import MarketSnapshot, Order


class SlippageModel(ABC):
    """Abstract slippage model contract."""

    @abstractmethod
    def calculate(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
        fill_qty: Decimal,
    ) -> Decimal:
        """Calculate slippage for a proposed fill."""

