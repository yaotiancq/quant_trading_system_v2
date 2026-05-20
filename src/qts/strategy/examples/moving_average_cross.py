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
    """Simple moving-average crossover strategy that emits signals on MA crossovers."""

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
        # Track previous state for crossover detection
        self.prev_fast_ma: Decimal | None = None
        self.prev_slow_ma: Decimal | None = None

    def initialize(self, context: StrategyContext) -> None:
        return None

    @staticmethod
    def calculate_simple_ma(closes: list[Decimal], window: int) -> Decimal:
        """
        Calculate simple moving average.
        
        Args:
            closes: List of closing prices (Decimal).
            window: Window size for the moving average.
        
        Returns:
            Simple moving average as Decimal.
        """
        if len(closes) < window:
            raise ValueError(f"Not enough data points: {len(closes)} < {window}")
        return sum(closes[-window:], Decimal("0")) / Decimal(window)

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
        fast_average = self.calculate_simple_ma(closes, self.fast_window)
        slow_average = self.calculate_simple_ma(closes, self.slow_window)
        
        signals = []
        
        # Detect crossover: previous bar had fast <= slow, current bar has fast > slow
        if self.prev_fast_ma is not None and self.prev_slow_ma is not None:
            prev_was_below = self.prev_fast_ma <= self.prev_slow_ma
            curr_is_above = fast_average > slow_average
            
            # Buy signal on upward crossover
            if prev_was_below and curr_is_above:
                signals.append(
                    Signal(
                        signal_id=new_id("signal"),
                        strategy_id=self.strategy_id,
                        symbol=self.symbol,
                        timestamp=event.bar.timestamp,
                        direction=SignalDirection.LONG,
                        strength=1.0,
                        confidence=1.0,
                        signal_type=SignalType.RULE_BASED,
                        suggested_notional=self.target_notional,
                        metadata={
                            "fast_average": str(fast_average),
                            "slow_average": str(slow_average),
                            "signal": "crossover_up",
                        },
                    )
                )
            # Sell signal on downward crossover
            elif not prev_was_below and not curr_is_above:
                signals.append(
                    Signal(
                        signal_id=new_id("signal"),
                        strategy_id=self.strategy_id,
                        symbol=self.symbol,
                        timestamp=event.bar.timestamp,
                        direction=SignalDirection.FLAT,
                        strength=1.0,
                        confidence=1.0,
                        signal_type=SignalType.RULE_BASED,
                        suggested_notional=Decimal("0"),
                        metadata={
                            "fast_average": str(fast_average),
                            "slow_average": str(slow_average),
                            "signal": "crossover_down",
                        },
                    )
                )
        
        # Update state for next bar
        self.prev_fast_ma = fast_average
        self.prev_slow_ma = slow_average
        
        return signals

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
