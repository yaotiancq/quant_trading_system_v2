from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from qts.core.enums import AdjustmentType
from qts.core.errors import DataAccessError, UnsupportedOperationError
from qts.data.alpaca_downloader import (
    AlpacaDataDownloadConfig,
    AlpacaHistoricalDataDownloader,
    build_alpaca_stock_bars_request,
)
from qts.data.local_provider import LocalHistoricalDataProvider


class FakeAlpacaBar:
    def __init__(
        self,
        *,
        symbol: str,
        timestamp: datetime,
        open: str,
        high: str,
        low: str,
        close: str,
        volume: str,
        vwap: str,
        trade_count: int,
    ) -> None:
        self.symbol = symbol
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.vwap = vwap
        self.trade_count = trade_count


class FakeBarSet:
    def __init__(self, data) -> None:
        self.data = data


class FakeAlpacaDataClient:
    def __init__(self, response) -> None:
        self.response = response
        self.requests = []

    def get_stock_bars(self, request):
        self.requests.append(request)
        return self.response


def request_value(request, key: str):
    if isinstance(request, dict):
        return request[key]
    return getattr(request, key)


def download_config(tmp_path) -> AlpacaDataDownloadConfig:
    return AlpacaDataDownloadConfig(
        symbols=["aapl"],
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 14, 32, tzinfo=UTC),
        timeframe="1m",
        output_dir=tmp_path,
        feed="iex",
        adjusted=True,
        adjustment_type=AdjustmentType.ALL,
        env_file=tmp_path / ".env",
    )


def test_alpaca_downloader_writes_local_provider_compatible_csv(tmp_path) -> None:
    response = FakeBarSet(
        {
            "AAPL": [
                FakeAlpacaBar(
                    symbol="AAPL",
                    timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
                    open="100.00",
                    high="101.00",
                    low="99.50",
                    close="100.25",
                    volume="1000",
                    vwap="100.10",
                    trade_count=15,
                ),
                FakeAlpacaBar(
                    symbol="AAPL",
                    timestamp=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
                    open="100.25",
                    high="102.00",
                    low="100.00",
                    close="101.25",
                    volume="1200",
                    vwap="101.10",
                    trade_count=18,
                ),
            ]
        }
    )
    client = FakeAlpacaDataClient(response)
    config = download_config(tmp_path)

    result = AlpacaHistoricalDataDownloader(client).download_bars(config)

    assert result.row_counts == {"AAPL": 2}
    assert request_value(client.requests[0], "symbol_or_symbols") == ["AAPL"]
    provider = LocalHistoricalDataProvider(tmp_path, source="alpaca")
    bars = provider.get_bars(
        ["AAPL"],
        datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        "1m",
        adjusted=True,
    )
    assert [bar.close for bar in bars] == [Decimal("100.25"), Decimal("101.25")]
    assert bars[0].source == "alpaca"
    assert bars[0].vwap == Decimal("100.10")
    assert bars[0].trade_count == 15


def test_downloader_csv_preserves_decimal_text_and_metadata(tmp_path) -> None:
    response = [
        {
            "symbol": "AAPL",
            "timestamp": "2024-01-02T14:30:00+00:00",
            "open": "100.0001",
            "high": "100.0002",
            "low": "99.9999",
            "close": "100.0000",
            "volume": "1234.5",
            "vwap": "100.00005",
            "trade_count": "7",
        }
    ]
    config = download_config(tmp_path)

    AlpacaHistoricalDataDownloader(FakeAlpacaDataClient(response)).download_bars(config)

    with (tmp_path / "AAPL_1m.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["open"] == "100.0001"
    assert rows[0]["volume"] == "1234.5"
    assert rows[0]["source"] == "alpaca"
    assert rows[0]["adjustment_type"] == "all"


def test_alpaca_download_config_requires_timezone_aware_window(tmp_path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AlpacaDataDownloadConfig(
            symbols=["AAPL"],
            start=datetime(2024, 1, 2, 14, 30),
            end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
            output_dir=tmp_path,
        )


def test_alpaca_download_config_loads_credentials_from_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "secret")
    config = download_config(tmp_path)

    credentials = config.load_credentials()

    assert credentials.api_key == "key"
    assert credentials.api_secret == "secret"


def test_alpaca_download_config_loads_credentials_from_dotenv(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local secrets",
                "APCA_API_KEY_ID=dotenv-key",
                "APCA_API_SECRET_KEY='dotenv-secret'",
            ]
        )
    )
    config = download_config(tmp_path)

    credentials = config.load_credentials()

    assert credentials.api_key == "dotenv-key"
    assert credentials.api_secret == "dotenv-secret"


def test_alpaca_download_config_reports_missing_credentials(tmp_path) -> None:
    config = download_config(tmp_path)

    with pytest.raises(UnsupportedOperationError, match="missing Alpaca data credential"):
        config.load_credentials()


def test_downloader_rejects_missing_symbol_data(tmp_path) -> None:
    config = download_config(tmp_path)

    with pytest.raises(DataAccessError, match="no bars"):
        AlpacaHistoricalDataDownloader(FakeAlpacaDataClient(FakeBarSet({}))).download_bars(config)


def test_request_builder_stays_sdk_optional(tmp_path) -> None:
    request = build_alpaca_stock_bars_request(download_config(tmp_path))

    assert request_value(request, "symbol_or_symbols") == ["AAPL"]
    assert str(request_value(request, "timeframe")).lower() in {"1min", "1m", "1minute"}
    assert str(request_value(request, "adjustment")).lower().endswith("all")
    assert str(request_value(request, "feed")).lower().endswith("iex")
