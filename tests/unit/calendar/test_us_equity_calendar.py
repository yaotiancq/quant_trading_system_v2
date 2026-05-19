from datetime import UTC, date, datetime

from qts.calendar.us_equity_calendar import USEquityCalendar
from qts.core.enums import MarketSession


def test_us_equity_calendar_rejects_weekends_and_holidays() -> None:
    calendar = USEquityCalendar()

    assert calendar.is_trading_day(date(2024, 1, 2))
    assert not calendar.is_trading_day(date(2024, 1, 6))
    assert not calendar.is_trading_day(date(2024, 7, 4))


def test_us_equity_calendar_classifies_regular_and_extended_sessions() -> None:
    calendar = USEquityCalendar()

    pre_market = datetime(2024, 1, 2, 13, 0, tzinfo=UTC)
    regular = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
    after_hours = datetime(2024, 1, 2, 22, 0, tzinfo=UTC)

    assert calendar.classify_session(pre_market) is MarketSession.PRE_MARKET
    assert calendar.classify_session(regular) is MarketSession.REGULAR
    assert calendar.classify_session(after_hours) is MarketSession.AFTER_HOURS
    assert calendar.is_market_open(regular)
    assert not calendar.is_market_open(pre_market)
    assert calendar.is_market_open(pre_market, include_extended=True)


def test_us_equity_calendar_knows_half_days() -> None:
    calendar = USEquityCalendar()

    assert calendar.is_half_day(date(2024, 11, 29))
    assert calendar.get_session_times(date(2024, 11, 29)).regular_close.hour == 13

