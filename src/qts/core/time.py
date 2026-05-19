"""Time helpers and the clock interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from qts.core.enums import MarketSession


def ensure_timezone_aware(value: datetime) -> datetime:
    """Return a datetime only if it is timezone-aware."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime fields must be timezone-aware")
    return value


def utc_now() -> datetime:
    """Current UTC time as a timezone-aware datetime."""

    return datetime.now(UTC)


class Clock(ABC):
    """Abstract clock contract used by backtest and live runtime modes."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current logical time."""

    @abstractmethod
    def is_realtime(self) -> bool:
        """Return whether this clock is driven by wall-clock time."""

    @abstractmethod
    def advance(self) -> datetime:
        """Advance and return the next logical time."""

    @abstractmethod
    def get_session(self, timestamp: datetime) -> MarketSession:
        """Classify a timestamp into a market session."""

