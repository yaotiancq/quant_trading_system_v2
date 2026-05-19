"""Commission model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from qts.core.models import CommissionBreakdown, Order


class CommissionModel(ABC):
    """Abstract commission model contract."""

    @abstractmethod
    def calculate(
        self,
        order: Order,
        fill_qty: Decimal,
        fill_price: Decimal,
    ) -> CommissionBreakdown:
        """Calculate commission and fees for a fill."""
