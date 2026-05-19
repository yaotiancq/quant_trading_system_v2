"""Trading calendar interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from qts.core.models import SessionTimes


class TradingCalendar(ABC):
    """Abstract market calendar contract."""

    @abstractmethod
    def is_trading_day(self, session_date: date) -> bool:
        """Return whether the supplied date is a trading day."""

    @abstractmethod
    def get_session_times(self, session_date: date) -> SessionTimes:
        """Return market session boundaries for the supplied date."""

    @abstractmethod
    def is_market_open(self, timestamp: datetime, include_extended: bool = False) -> bool:
        """Return whether the market is open at a timestamp."""

    @abstractmethod
    def get_next_open(self, timestamp: datetime) -> datetime:
        """Return the next regular-session open."""

    @abstractmethod
    def get_next_close(self, timestamp: datetime) -> datetime:
        """Return the next regular-session close."""

    @abstractmethod
    def is_half_day(self, session_date: date) -> bool:
        """Return whether the supplied trading day has shortened hours."""

