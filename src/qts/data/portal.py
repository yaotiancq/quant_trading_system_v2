"""Market data portal interface and historical implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from qts.core.errors import DataAccessError, UnsupportedOperationError
from qts.core.models import (
    Bar,
    DataAvailabilityReport,
    HistoricalWindow,
    Instrument,
    MarketSnapshot,
    Quote,
    Trade,
)
from qts.core.time import Clock, ensure_timezone_aware
from qts.data.provider_base import MarketDataProvider
from qts.universe.universe import Universe


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


class HistoricalMarketDataPortal(MarketDataPortal):
    """Clock-aware data portal for historical data.

    The portal is the no-lookahead boundary: every request is clipped to the current logical clock
    time, even if the underlying local files contain later rows.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        clock: Clock,
        *,
        calendar: object | None = None,
        universes: dict[str, Universe] | None = None,
        adjusted: bool = True,
        default_timeframe: str = "1m",
        source: str = "historical-portal",
    ) -> None:
        self.provider = provider
        self.clock = clock
        self.calendar = calendar
        self.universes = universes or {}
        self.adjusted = adjusted
        self.default_timeframe = default_timeframe
        self.source = source

    def history(
        self,
        symbol: str,
        fields: list[str],
        lookback: int,
        timeframe: str,
        end_time: datetime | None = None,
    ) -> HistoricalWindow:
        if lookback <= 0:
            raise ValueError("lookback must be positive")
        effective_end = self._effective_end_time(end_time)
        start = datetime(1970, 1, 1, tzinfo=UTC)
        bars = self.provider.get_bars([symbol], start, effective_end, timeframe, self.adjusted)
        selected = bars[-lookback:]
        window_start = selected[0].timestamp if selected else effective_end
        return HistoricalWindow(
            symbol=symbol,
            fields=fields,
            timeframe=timeframe,
            start=window_start,
            end=effective_end,
            bars=selected,
        )

    def current(self, symbol: str) -> MarketSnapshot:
        latest = self.latest_bar(symbol, self.default_timeframe)
        session = self.clock.get_session(latest.timestamp)
        return MarketSnapshot(
            timestamp=latest.timestamp,
            symbol=symbol,
            latest_bar=latest,
            session=session,
            is_tradable=self.can_trade(symbol, latest.timestamp),
            source=self.source,
        )

    def latest_bar(self, symbol: str, timeframe: str) -> Bar:
        window = self.history(symbol, ["open", "high", "low", "close", "volume"], 1, timeframe)
        if not window.bars:
            raise DataAccessError(f"no bars available for {symbol} at or before {self.clock.now()}")
        return window.bars[-1]

    def latest_quote(self, symbol: str) -> Quote:
        raise UnsupportedOperationError(f"historical portal has no quote data for {symbol}")

    def latest_trade(self, symbol: str) -> Trade:
        raise UnsupportedOperationError(f"historical portal has no trade data for {symbol}")

    def can_trade(self, symbol: str, timestamp: datetime) -> bool:
        timestamp = ensure_timezone_aware(timestamp)
        if self.calendar is not None and hasattr(self.calendar, "is_market_open"):
            return bool(self.calendar.is_market_open(timestamp, include_extended=False))
        return self.clock.get_session(timestamp).value == "regular"

    def get_universe(self, universe_id: str) -> list[Instrument]:
        try:
            universe = self.universes[universe_id]
        except KeyError as exc:
            raise DataAccessError(f"unknown universe_id: {universe_id}") from exc
        return universe.get_instruments(self.clock.now())

    def validate_data_availability(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> DataAvailabilityReport:
        start = ensure_timezone_aware(start)
        end = self._effective_end_time(end)
        missing_symbols = []
        for symbol in symbols:
            try:
                bars = self.provider.get_bars([symbol], start, end, timeframe, self.adjusted)
            except DataAccessError:
                bars = []
            if not bars:
                missing_symbols.append(symbol)
        return DataAvailabilityReport(
            symbols=symbols,
            start=start,
            end=end,
            timeframe=timeframe,
            available=not missing_symbols,
            missing_symbols=missing_symbols,
        )

    def _effective_end_time(self, requested_end: datetime | None) -> datetime:
        clock_now = ensure_timezone_aware(self.clock.now())
        if requested_end is None:
            return clock_now
        requested_end = ensure_timezone_aware(requested_end)
        return min(requested_end, clock_now)
