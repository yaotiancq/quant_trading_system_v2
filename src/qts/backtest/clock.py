"""Deterministic backtest clock."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, cast

from qts.calendar.trading_calendar import TradingCalendar
from qts.calendar.us_equity_calendar import USEquityCalendar
from qts.core.enums import MarketSession
from qts.core.time import Clock, ensure_timezone_aware


class SessionClassifier(Protocol):
    def classify_session(self, timestamp: datetime) -> MarketSession:
        """Classify timestamp into a market session."""


class BacktestClock(Clock):
    """Clock that advances through a predefined sequence of event times."""

    def __init__(
        self,
        event_times: list[datetime],
        *,
        calendar: TradingCalendar | None = None,
    ) -> None:
        if not event_times:
            raise ValueError("BacktestClock requires at least one event time")
        self.event_times = sorted(ensure_timezone_aware(timestamp) for timestamp in event_times)
        self.calendar = calendar or USEquityCalendar()
        self._index = 0
        self._current = self.event_times[0]

    def now(self) -> datetime:
        return self._current

    def is_realtime(self) -> bool:
        return False

    def advance(self) -> datetime:
        if self._index < len(self.event_times) - 1:
            self._index += 1
            self._current = self.event_times[self._index]
        return self._current

    def set_time(self, timestamp: datetime) -> datetime:
        """Set logical time directly during deterministic event replay."""

        self._current = ensure_timezone_aware(timestamp)
        return self._current

    def get_session(self, timestamp: datetime) -> MarketSession:
        if hasattr(self.calendar, "classify_session"):
            return cast(SessionClassifier, self.calendar).classify_session(timestamp)
        return (
            MarketSession.REGULAR
            if self.calendar.is_market_open(timestamp)
            else MarketSession.CLOSED
        )
