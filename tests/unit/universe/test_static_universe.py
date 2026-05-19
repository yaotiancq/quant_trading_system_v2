from datetime import UTC, datetime

from qts.universe.static_universe import StaticUniverse


def test_static_universe_returns_instruments_and_validates() -> None:
    universe = StaticUniverse.from_symbols("core", ["AAPL", "MSFT"])
    timestamp = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)

    instruments = universe.get_instruments(timestamp)
    report = universe.validate_universe(timestamp)

    assert [instrument.symbol for instrument in instruments] == ["AAPL", "MSFT"]
    assert report.valid
    assert report.symbol_count == 2


def test_static_universe_reports_duplicate_symbols() -> None:
    universe = StaticUniverse.from_symbols("core", ["AAPL", "AAPL"])

    report = universe.validate_universe(datetime(2024, 1, 2, 14, 30, tzinfo=UTC))

    assert not report.valid
    assert report.reasons == ["duplicate symbol: AAPL"]

