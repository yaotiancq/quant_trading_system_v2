from __future__ import annotations

from datetime import UTC, datetime

from qts.calendar.us_equity_calendar import USEquityCalendar
from qts.core.enums import MarketSession
from qts.core.time import Clock
from qts.data.local_provider import LocalHistoricalDataProvider
from qts.data.portal import HistoricalMarketDataPortal
from qts.universe.static_universe import StaticUniverse


class FixedClock(Clock):
    def __init__(self, timestamp: datetime) -> None:
        self._timestamp = timestamp
        self._calendar = USEquityCalendar()

    def now(self) -> datetime:
        return self._timestamp

    def is_realtime(self) -> bool:
        return False

    def advance(self) -> datetime:
        return self._timestamp

    def get_session(self, timestamp: datetime) -> MarketSession:
        return self._calendar.classify_session(timestamp)


def write_fixture_csv(path) -> None:
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2024-01-02T14:30:00+00:00,100,101,99,100.5,1000",
                "2024-01-02T14:31:00+00:00,100.5,102,100,101.5,1200",
                "2024-01-02T14:32:00+00:00,101.5,103,101,102.5,1300",
            ]
        )
    )


def test_historical_portal_does_not_return_future_bars(tmp_path) -> None:
    write_fixture_csv(tmp_path / "AAPL_1m.csv")
    provider = LocalHistoricalDataProvider(tmp_path)
    portal = HistoricalMarketDataPortal(
        provider,
        FixedClock(datetime(2024, 1, 2, 14, 31, 30, tzinfo=UTC)),
        calendar=USEquityCalendar(),
    )

    window = portal.history("AAPL", ["close"], 10, "1m")

    assert [bar.timestamp.minute for bar in window.bars] == [30, 31]
    assert window.end == datetime(2024, 1, 2, 14, 31, 30, tzinfo=UTC)


def test_historical_portal_returns_static_universe(tmp_path) -> None:
    write_fixture_csv(tmp_path / "AAPL_1m.csv")
    portal = HistoricalMarketDataPortal(
        LocalHistoricalDataProvider(tmp_path),
        FixedClock(datetime(2024, 1, 2, 14, 31, 30, tzinfo=UTC)),
        universes={"core": StaticUniverse.from_symbols("core", ["AAPL", "MSFT"])},
    )

    instruments = portal.get_universe("core")

    assert [instrument.symbol for instrument in instruments] == ["AAPL", "MSFT"]


def test_historical_portal_data_availability_reports_missing_symbols(tmp_path) -> None:
    write_fixture_csv(tmp_path / "AAPL_1m.csv")
    portal = HistoricalMarketDataPortal(
        LocalHistoricalDataProvider(tmp_path),
        FixedClock(datetime(2024, 1, 2, 14, 31, 30, tzinfo=UTC)),
    )

    report = portal.validate_data_availability(
        ["AAPL", "MSFT"],
        datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        "1m",
    )

    assert not report.available
    assert report.missing_symbols == ["MSFT"]

