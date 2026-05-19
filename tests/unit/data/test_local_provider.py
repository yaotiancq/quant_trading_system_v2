from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from qts.data.local_provider import LocalHistoricalDataProvider


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


def test_local_historical_provider_loads_csv_bars(tmp_path) -> None:
    write_fixture_csv(tmp_path / "AAPL_1m.csv")
    provider = LocalHistoricalDataProvider(tmp_path)

    bars = provider.get_bars(
        ["AAPL"],
        datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        "1m",
        adjusted=True,
    )

    assert [bar.symbol for bar in bars] == ["AAPL", "AAPL"]
    assert bars[0].close == Decimal("100.5")
    assert bars[0].timeframe == "1m"
    assert bars[0].source == "local"

