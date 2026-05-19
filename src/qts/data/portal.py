"""Market data portal interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from qts.core.models import (
    Bar,
    DataAvailabilityReport,
    HistoricalWindow,
    Instrument,
    MarketSnapshot,
    Quote,
    Trade,
)


class MarketDataPortal(ABC):
    """Strategy-facing market data interface."""

    @abstractmethod
    def history(
        self,
        symbol: str,
        fields: list[str],
        lookback: int,
        timeframe: str,
        end_time: datetime | None = None,
    ) -> HistoricalWindow:
        """Return a historical data window, respecting logical clock time."""

    @abstractmethod
    def current(self, symbol: str) -> MarketSnapshot:
        """Return the current market snapshot for a symbol."""

    @abstractmethod
    def latest_bar(self, symbol: str, timeframe: str) -> Bar:
        """Return the latest completed bar for a symbol."""

    @abstractmethod
    def latest_quote(self, symbol: str) -> Quote:
        """Return the latest quote for a symbol."""

    @abstractmethod
    def latest_trade(self, symbol: str) -> Trade:
        """Return the latest trade for a symbol."""

    @abstractmethod
    def can_trade(self, symbol: str, timestamp: datetime) -> bool:
        """Return whether the symbol can be traded at the timestamp."""

    @abstractmethod
    def get_universe(self, universe_id: str) -> list[Instrument]:
        """Return instruments in a universe."""

    @abstractmethod
    def validate_data_availability(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> DataAvailabilityReport:
        """Return data availability diagnostics."""

