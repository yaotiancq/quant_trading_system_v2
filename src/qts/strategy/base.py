"""Strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from qts.core.events import BarEvent, ClockEvent, FillEvent, QuoteEvent, TradeEvent
from qts.core.models import Signal
from qts.strategy.context import StrategyContext


class Strategy(ABC):
    """Abstract strategy contract.

    Strategies produce signals only. They must not submit orders or access concrete brokers.
    """

    strategy_id: str

    @abstractmethod
    def initialize(self, context: StrategyContext) -> None:
        """Initialize strategy-owned state."""

    @abstractmethod
    def on_start(self, context: StrategyContext) -> None:
        """Handle runtime start."""

    @abstractmethod
    def on_bar(self, context: StrategyContext, event: BarEvent) -> list[Signal]:
        """Handle a bar event and return signals."""

    @abstractmethod
    def on_quote(self, context: StrategyContext, event: QuoteEvent) -> list[Signal]:
        """Handle a quote event and return signals."""

    @abstractmethod
    def on_trade(self, context: StrategyContext, event: TradeEvent) -> list[Signal]:
        """Handle a trade event and return signals."""

    @abstractmethod
    def on_timer(self, context: StrategyContext, event: ClockEvent) -> list[Signal]:
        """Handle a timer event and return signals."""

    @abstractmethod
    def on_fill(self, context: StrategyContext, event: FillEvent) -> None:
        """Handle a fill notification."""

    @abstractmethod
    def on_stop(self, context: StrategyContext) -> None:
        """Handle runtime stop."""
