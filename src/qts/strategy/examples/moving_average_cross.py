"""Moving-average crossover example strategy."""

from __future__ import annotations

from decimal import Decimal

from qts.core.enums import SignalDirection, SignalType
from qts.core.events import BarEvent, ClockEvent, FillEvent, QuoteEvent, TradeEvent
from qts.core.identifiers import new_id
from qts.core.models import Signal
from qts.strategy.base import Strategy
from qts.strategy.context import StrategyContext


class MovingAverageCrossStrategy(Strategy):
    """Simple moving-average strategy that emits standardized signals only."""

    def __init__(
        self,
        *,
        strategy_id: str,
        symbol: str,
        fast_window: int,
        slow_window: int,
        target_notional: Decimal,
    ) -> None:
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("moving-average windows must be positive")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.target_notional = target_notional

    def initialize(self, context: StrategyContext) -> None:
        return None

    def on_start(self, context: StrategyContext) -> None:
        return None

    def on_bar(self, context: StrategyContext, event: BarEvent) -> list[Signal]:
        if event.bar.symbol != self.symbol:
            return []
        window = context.data.history(
            self.symbol,
            ["close"],
            self.slow_window,
            event.bar.timeframe,
            end_time=event.bar.timestamp,
        )
        if len(window.bars) < self.slow_window:
            return []
        closes = [bar.close for bar in window.bars]
        fast_average = sum(closes[-self.fast_window:], Decimal("0")) / Decimal(self.fast_window)
        slow_average = sum(closes, Decimal("0")) / Decimal(self.slow_window)
        direction = SignalDirection.LONG if fast_average > slow_average else SignalDirection.FLAT
        return [
            Signal(
                signal_id=new_id("signal"),
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                timestamp=event.bar.timestamp,
                direction=direction,
                strength=1.0,
                confidence=1.0,
                signal_type=SignalType.RULE_BASED,
                suggested_notional=(
                    self.target_notional if direction is SignalDirection.LONG else Decimal("0")
                ),
                metadata={
                    "fast_average": str(fast_average),
                    "slow_average": str(slow_average),
                },
            )
        ]

    def on_quote(self, context: StrategyContext, event: QuoteEvent) -> list[Signal]:
        return []

    def on_trade(self, context: StrategyContext, event: TradeEvent) -> list[Signal]:
        return []

    def on_timer(self, context: StrategyContext, event: ClockEvent) -> list[Signal]:
        return []

    def on_fill(self, context: StrategyContext, event: FillEvent) -> None:
        return None

    def on_stop(self, context: StrategyContext) -> None:
        return None
