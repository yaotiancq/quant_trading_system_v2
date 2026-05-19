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


class ZeroCommission(CommissionModel):
    """Commission-free model."""

    def calculate(
        self,
        order: Order,
        fill_qty: Decimal,
        fill_price: Decimal,
    ) -> CommissionBreakdown:
        return CommissionBreakdown(commission=Decimal("0"), fees=Decimal("0"))


class FixedPerShareCommission(CommissionModel):
    """Fixed per-share commission model."""

    def __init__(self, per_share: Decimal, *, minimum: Decimal = Decimal("0")) -> None:
        self.per_share = per_share
        self.minimum = minimum

    def calculate(
        self,
        order: Order,
        fill_qty: Decimal,
        fill_price: Decimal,
    ) -> CommissionBreakdown:
        commission = max(fill_qty.copy_abs() * self.per_share, self.minimum)
        return CommissionBreakdown(commission=commission, fees=Decimal("0"))


class BpsCommission(CommissionModel):
    """Basis-point commission model on fill notional."""

    def __init__(self, bps: Decimal, *, minimum: Decimal = Decimal("0")) -> None:
        self.bps = bps
        self.minimum = minimum

    def calculate(
        self,
        order: Order,
        fill_qty: Decimal,
        fill_price: Decimal,
    ) -> CommissionBreakdown:
        notional = fill_qty.copy_abs() * fill_price
        commission = max(notional * self.bps / Decimal("10000"), self.minimum)
        return CommissionBreakdown(commission=commission, fees=Decimal("0"))
