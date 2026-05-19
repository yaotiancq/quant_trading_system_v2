"""Strategy engine implementation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from qts.core.events import BarEvent, BaseEvent, FillEvent, QuoteEvent, TradeEvent
from qts.core.models import Signal
from qts.strategy.base import Strategy
from qts.strategy.context import StrategyContext


class StrategyEngine:
    """Initialize strategies and dispatch events to them."""

    def __init__(
        self,
        strategies: list[Strategy],
        context_by_strategy_id: dict[str, StrategyContext],
    ) -> None:
        self.strategies = strategies
        self.context_by_strategy_id = context_by_strategy_id
        self.errors: list[Exception] = []
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> None:
        for strategy in self.strategies:
            context = self._context_for(strategy)
            self._safe_call(strategy.initialize, context)
            self._safe_call(strategy.on_start, context)

    def dispatch_market_event(self, event: BaseEvent) -> list[Signal]:
        signals: list[Signal] = []
        for strategy in self.strategies:
            context = self._context_for(strategy)
            try:
                if isinstance(event, BarEvent):
                    signals.extend(strategy.on_bar(context, event))
                elif isinstance(event, QuoteEvent):
                    signals.extend(strategy.on_quote(context, event))
                elif isinstance(event, TradeEvent):
                    signals.extend(strategy.on_trade(context, event))
            except Exception as exc:  # pragma: no cover - defensive isolation
                self.errors.append(exc)
                self.logger.exception("strategy dispatch failed")
        return signals

    def dispatch_fill(self, event: FillEvent) -> None:
        for strategy in self.strategies:
            context = self._context_for(strategy)
            self._safe_call(strategy.on_fill, context, event)

    def stop(self) -> None:
        for strategy in self.strategies:
            self._safe_call(strategy.on_stop, self._context_for(strategy))

    def _context_for(self, strategy: Strategy) -> StrategyContext:
        strategy_id = strategy.strategy_id
        return self.context_by_strategy_id[strategy_id]

    def _safe_call(self, func: Callable[..., Any], *args: Any) -> None:
        try:
            func(*args)
        except Exception as exc:  # pragma: no cover - defensive isolation
            self.errors.append(exc)
            self.logger.exception("strategy lifecycle hook failed")
