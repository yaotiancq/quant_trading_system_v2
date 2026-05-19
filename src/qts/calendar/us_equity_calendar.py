"""U.S. equity regular and extended-hours trading calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import cache
from zoneinfo import ZoneInfo

from qts.calendar.trading_calendar import TradingCalendar
from qts.core.enums import MarketSession
from qts.core.models import SessionTimes
from qts.core.time import ensure_timezone_aware

US_EASTERN = ZoneInfo("America/New_York")


def _observed_date(holiday: date) -> date:
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year, 12, 31)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _easter_date(year: int) -> date:
    """Gregorian Easter date using the Meeus/Jones/Butcher algorithm."""

    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    correction = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * correction) // 451
    month = (h + correction - 7 * m + 114) // 31
    day = ((h + correction - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@cache
def _market_holidays(year: int) -> frozenset[date]:
    holidays = {
        _observed_date(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_date(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed_date(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_date(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed_date(date(year, 6, 19)))
    next_year_new_year = _observed_date(date(year + 1, 1, 1))
    if next_year_new_year.year == year:
        holidays.add(next_year_new_year)
    return frozenset(holidays)


class USEquityCalendar(TradingCalendar):
    """U.S. equity calendar with regular and extended session classification."""

    timezone = US_EASTERN

    def is_trading_day(self, session_date: date) -> bool:
        return (
            session_date.weekday() < 5
            and session_date not in _market_holidays(session_date.year)
        )

    def get_session_times(self, session_date: date) -> SessionTimes:
        if not self.is_trading_day(session_date):
            raise ValueError(f"{session_date.isoformat()} is not a U.S. equity trading day")
        regular_close = time(13, 0) if self.is_half_day(session_date) else time(16, 0)
        after_hours_close = time(17, 0) if self.is_half_day(session_date) else time(20, 0)
        return SessionTimes(
            session_date=session_date,
            pre_market_open=datetime.combine(session_date, time(4, 0), tzinfo=self.timezone),
            regular_open=datetime.combine(session_date, time(9, 30), tzinfo=self.timezone),
            regular_close=datetime.combine(session_date, regular_close, tzinfo=self.timezone),
            after_hours_close=datetime.combine(
                session_date,
                after_hours_close,
                tzinfo=self.timezone,
            ),
        )

    def is_market_open(self, timestamp: datetime, include_extended: bool = False) -> bool:
        session = self.classify_session(timestamp)
        if include_extended:
            return session in {
                MarketSession.PRE_MARKET,
                MarketSession.REGULAR,
                MarketSession.AFTER_HOURS,
            }
        return session == MarketSession.REGULAR

    def get_next_open(self, timestamp: datetime) -> datetime:
        local_timestamp = ensure_timezone_aware(timestamp).astimezone(self.timezone)
        current_date = local_timestamp.date()
        for day_offset in range(370):
            candidate = current_date + timedelta(days=day_offset)
            if not self.is_trading_day(candidate):
                continue
            open_time = self.get_session_times(candidate).regular_open
            if local_timestamp <= open_time:
                return open_time
        raise ValueError("unable to find next market open within one year")

    def get_next_close(self, timestamp: datetime) -> datetime:
        local_timestamp = ensure_timezone_aware(timestamp).astimezone(self.timezone)
        current_date = local_timestamp.date()
        for day_offset in range(370):
            candidate = current_date + timedelta(days=day_offset)
            if not self.is_trading_day(candidate):
                continue
            close_time = self.get_session_times(candidate).regular_close
            if local_timestamp <= close_time:
                return close_time
        raise ValueError("unable to find next market close within one year")

    def is_half_day(self, session_date: date) -> bool:
        if not self.is_trading_day(session_date):
            return False
        thanksgiving = _nth_weekday(session_date.year, 11, 3, 4)
        day_after_thanksgiving = thanksgiving + timedelta(days=1)
        christmas_eve = date(session_date.year, 12, 24)
        july_third = date(session_date.year, 7, 3)
        return session_date in {day_after_thanksgiving, christmas_eve, july_third}

    def classify_session(self, timestamp: datetime) -> MarketSession:
        local_timestamp = ensure_timezone_aware(timestamp).astimezone(self.timezone)
        session_date = local_timestamp.date()
        if not self.is_trading_day(session_date):
            return MarketSession.CLOSED
        times = self.get_session_times(session_date)
        pre_market_open = times.pre_market_open
        after_hours_close = times.after_hours_close
        if pre_market_open is None or after_hours_close is None:
            return MarketSession.CLOSED
        if pre_market_open <= local_timestamp < times.regular_open:
            return MarketSession.PRE_MARKET
        if times.regular_open <= local_timestamp < times.regular_close:
            return MarketSession.REGULAR
        if times.regular_close <= local_timestamp < after_hours_close:
            return MarketSession.AFTER_HOURS
        return MarketSession.OVERNIGHT
