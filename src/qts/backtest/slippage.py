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


class NoSlippage(SlippageModel):
    """Zero slippage."""

    def calculate(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
        fill_qty: Decimal,
    ) -> Decimal:
        return Decimal("0")


class FixedBpsSlippage(SlippageModel):
    """Fixed basis-point slippage relative to reference price."""

    def __init__(self, bps: Decimal) -> None:
        self.bps = bps

    def calculate(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
        fill_qty: Decimal,
    ) -> Decimal:
        return reference_price * self.bps / Decimal("10000")


class SpreadBasedSlippage(SlippageModel):
    """Use a fraction of quoted spread when quote data is present."""

    def __init__(self, spread_fraction: Decimal = Decimal("0.5")) -> None:
        self.spread_fraction = spread_fraction

    def calculate(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
        fill_qty: Decimal,
    ) -> Decimal:
        quote = market_snapshot.latest_quote
        if quote is None:
            return Decimal("0")
        spread = (quote.ask_price - quote.bid_price).copy_abs()
        return spread * self.spread_fraction


class VolumeParticipationSlippage(SlippageModel):
    """Simple volume-participation impact model for bar data."""

    def __init__(self, impact_bps: Decimal = Decimal("10")) -> None:
        self.impact_bps = impact_bps

    def calculate(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
        fill_qty: Decimal,
    ) -> Decimal:
        bar = market_snapshot.latest_bar
        if bar is None or bar.volume <= Decimal("0"):
            return Decimal("0")
        participation = min(fill_qty.copy_abs() / bar.volume, Decimal("1"))
        return reference_price * self.impact_bps * participation / Decimal("10000")
