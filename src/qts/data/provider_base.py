"""Market data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from qts.core.models import Bar, HealthStatus, MarketSnapshot, Quote, Trade


class MarketDataProvider(ABC):
    """Abstract data provider contract for historical and streaming data."""

    @abstractmethod
    def get_bars(
        self,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        timeframe: str,
        adjusted: bool,
    ) -> list[Bar]:
        """Return historical bars."""

    @abstractmethod
    def get_latest_bar(self, symbol: str, timeframe: str) -> Bar:
        """Return the latest complete bar for a symbol."""

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Quote:
        """Return the latest quote for a symbol."""

    @abstractmethod
    def get_latest_trade(self, symbol: str) -> Trade:
        """Return the latest trade for a symbol."""

    @abstractmethod
    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return a consolidated market snapshot."""

    @abstractmethod
    def subscribe_bars(
        self,
        symbols: Sequence[str],
        timeframe: str,
        handler: Callable[[Bar], None],
    ) -> str:
        """Subscribe to bar events."""

    @abstractmethod
    def subscribe_quotes(self, symbols: Sequence[str], handler: Callable[[Quote], None]) -> str:
        """Subscribe to quote events."""

    @abstractmethod
    def subscribe_trades(self, symbols: Sequence[str], handler: Callable[[Trade], None]) -> str:
        """Subscribe to trade events."""

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Cancel a subscription."""

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Return provider health."""

    def close(self) -> None:
        """Optional cleanup hook for implementations."""
        return None

    def __enter__(self) -> MarketDataProvider:
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        self.close()
