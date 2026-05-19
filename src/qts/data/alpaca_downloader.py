"""Alpaca historical data downloader for the local backtest cache.

This module is intentionally independent from the backtest engine. It downloads bars from an
Alpaca-like historical data client, normalizes them to the QTS `Bar` model, and writes CSV files
that `LocalHistoricalDataProvider` can replay deterministically.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Self

from pydantic import Field, field_validator, model_validator

from qts.config.loader import load_config
from qts.core.enums import AdjustmentType
from qts.core.errors import DataAccessError, UnsupportedOperationError
from qts.core.models import Bar, QtsModel
from qts.core.time import ensure_timezone_aware

BAR_CSV_FIELDS = [
    "timestamp",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "trade_count",
    "source",
    "adjusted",
    "adjustment_type",
    "is_complete",
    "received_at",
]
DEFAULT_API_KEY_ENV_ALIASES = [
    "APCA_API_KEY_ID",
    "ALPACA_API_KEY_ID",
    "ALPACA_PAPER_API_KEY",
    "ALPACA_API_KEY",
]
DEFAULT_API_SECRET_ENV_ALIASES = [
    "APCA_API_SECRET_KEY",
    "ALPACA_API_SECRET_KEY",
    "ALPACA_PAPER_API_SECRET",
    "ALPACA_SECRET_KEY",
]


class AlpacaDataCredentials(QtsModel):
    """Resolved Alpaca credentials loaded from environment variables."""

    api_key: str
    api_secret: str


class AlpacaDataDownloadConfig(QtsModel):
    """Config for materializing Alpaca bars into the local market-data cache."""

    symbols: list[str]
    start: datetime
    end: datetime
    timeframe: str = "1m"
    output_dir: Path = Path("data/market")
    feed: str = "iex"
    adjusted: bool = True
    adjustment_type: AdjustmentType = AdjustmentType.ALL
    env_file: Path | None = Path(".env")
    api_key_env: str = "APCA_API_KEY_ID"
    api_secret_env: str = "APCA_API_SECRET_KEY"
    api_key_env_aliases: list[str] = Field(
        default_factory=lambda: list(DEFAULT_API_KEY_ENV_ALIASES)
    )
    api_secret_env_aliases: list[str] = Field(
        default_factory=lambda: list(DEFAULT_API_SECRET_ENV_ALIASES)
    )
    overwrite: bool = True
    allow_empty: bool = False

    @field_validator("symbols")
    @classmethod
    def _validate_symbols(cls, symbols: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        if not normalized:
            raise ValueError("at least one symbol is required")
        return normalized

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, timeframe: str) -> str:
        normalized = timeframe.strip().lower()
        if not normalized:
            raise ValueError("timeframe is required")
        return normalized

    @field_validator("feed")
    @classmethod
    def _validate_feed(cls, feed: str) -> str:
        normalized = feed.strip().lower()
        if not normalized:
            raise ValueError("feed is required")
        return normalized

    @model_validator(mode="after")
    def _validate_window(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self

    @classmethod
    def from_file(cls, path: str | Path) -> AlpacaDataDownloadConfig:
        """Load downloader config from a YAML file."""

        return cls.model_validate(load_config(path))

    def load_credentials(self) -> AlpacaDataCredentials:
        """Resolve API credentials from process environment or the configured `.env` file."""

        env_values = _load_env_file(self.env_file)
        api_key = _resolve_credential(
            primary_name=self.api_key_env,
            aliases=self.api_key_env_aliases,
            env_values=env_values,
        )
        api_secret = _resolve_credential(
            primary_name=self.api_secret_env,
            aliases=self.api_secret_env_aliases,
            env_values=env_values,
        )
        if not api_key or not api_secret:
            checked_names = sorted(
                {
                    self.api_key_env,
                    self.api_secret_env,
                    *self.api_key_env_aliases,
                    *self.api_secret_env_aliases,
                }
            )
            raise UnsupportedOperationError(
                "missing Alpaca data credentials. Checked process environment and "
                f"{self.env_file or 'no .env file'} for: "
                + ", ".join(checked_names)
            )
        return AlpacaDataCredentials(api_key=api_key, api_secret=api_secret)


class AlpacaDataDownloadResult(QtsModel):
    """Summary of files written by an Alpaca data download."""

    symbols: list[str]
    timeframe: str
    start: datetime
    end: datetime
    output_paths: list[str]
    row_counts: dict[str, int]
    source: str = "alpaca"


class AlpacaHistoricalDataDownloader:
    """Download Alpaca historical stock bars into local QTS CSV files."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def download_bars(self, config: AlpacaDataDownloadConfig) -> AlpacaDataDownloadResult:
        """Download bars and write one `{symbol}_{timeframe}.csv` file per symbol."""

        raw_response = self._request_bars(config)
        bars_by_symbol: dict[str, list[Bar]] = defaultdict(list)
        for default_symbol, raw_bar in _iter_raw_bars(raw_response):
            bar = _bar_from_alpaca(raw_bar, default_symbol=default_symbol, config=config)
            bars_by_symbol[bar.symbol].append(bar)

        config.output_dir.mkdir(parents=True, exist_ok=True)
        output_paths: list[str] = []
        row_counts: dict[str, int] = {}
        for symbol in config.symbols:
            bars = sorted(bars_by_symbol.get(symbol, []), key=lambda bar: bar.timestamp)
            if not bars and not config.allow_empty:
                raise DataAccessError(f"Alpaca returned no bars for {symbol} {config.timeframe}")
            destination = config.output_dir / f"{symbol}_{config.timeframe}.csv"
            _write_bar_csv(destination, bars, overwrite=config.overwrite)
            output_paths.append(str(destination))
            row_counts[symbol] = len(bars)

        return AlpacaDataDownloadResult(
            symbols=config.symbols,
            timeframe=config.timeframe,
            start=config.start,
            end=config.end,
            output_paths=output_paths,
            row_counts=row_counts,
        )

    def _request_bars(self, config: AlpacaDataDownloadConfig) -> Any:
        client = self.client or build_alpaca_stock_data_client(config)
        request = build_alpaca_stock_bars_request(config)
        method = getattr(client, "get_stock_bars", None)
        if callable(method):
            return method(request)
        method = getattr(client, "get_bars", None)
        if callable(method):
            return method(request)
        raise UnsupportedOperationError(
            "Alpaca historical data client must expose get_stock_bars(request)"
        )


def build_alpaca_stock_data_client(config: AlpacaDataDownloadConfig) -> Any:
    """Build a real alpaca-py historical stock data client when the SDK is installed."""

    try:
        historical_module = importlib.import_module("alpaca.data.historical")
    except ModuleNotFoundError as exc:
        raise UnsupportedOperationError(
            "Alpaca data downloads require alpaca-py. Install it with "
            ".venv/bin/python -m pip install -e '.[alpaca]'"
        ) from exc
    client_cls = historical_module.StockHistoricalDataClient
    credentials = config.load_credentials()
    return client_cls(credentials.api_key, credentials.api_secret)


def build_alpaca_stock_bars_request(config: AlpacaDataDownloadConfig) -> Any:
    """Build an alpaca-py request object, falling back to a plain dict for tests."""

    payload = _alpaca_request_payload(config)
    try:
        requests_module = importlib.import_module("alpaca.data.requests")
    except ModuleNotFoundError:
        return payload
    request_cls = getattr(requests_module, "StockBarsRequest", None)
    if request_cls is None:
        return payload
    return request_cls(**payload)


def download_bars_from_config(path: str | Path) -> AlpacaDataDownloadResult:
    """Download historical bars using a config file path."""

    config = AlpacaDataDownloadConfig.from_file(path)
    return AlpacaHistoricalDataDownloader().download_bars(config)


def build_parser() -> argparse.ArgumentParser:
    """Create the Alpaca data downloader CLI parser."""

    parser = argparse.ArgumentParser(prog="qts-download-alpaca-data")
    parser.add_argument(
        "--config",
        default="config/download_alpaca_data.yaml",
        help="Path to an Alpaca data download config file.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for downloading Alpaca bars into the local cache."""

    parser = build_parser()
    args = parser.parse_args(argv)
    result = download_bars_from_config(args.config)
    print(f"source={result.source}")
    print(f"timeframe={result.timeframe}")
    for symbol in result.symbols:
        print(f"{symbol} rows={result.row_counts[symbol]}")
    for output_path in result.output_paths:
        print(f"wrote={output_path}")


def _alpaca_request_payload(config: AlpacaDataDownloadConfig) -> dict[str, Any]:
    return {
        "symbol_or_symbols": config.symbols,
        "timeframe": _coerce_alpaca_timeframe(config.timeframe),
        "start": config.start,
        "end": config.end,
        "adjustment": _coerce_alpaca_adjustment(config.adjustment_type),
        "feed": _coerce_alpaca_feed(config.feed),
    }


def _load_env_file(env_file: str | Path | None) -> dict[str, str]:
    if env_file is None:
        return {}
    path = Path(env_file)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if key:
            values[key] = _parse_env_value(value.strip())
    return values


def _parse_env_value(value: str) -> str:
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        unquoted = value[1:-1]
        if value[0] == '"':
            return unquoted.replace(r"\"", '"').replace(r"\n", "\n")
        return unquoted
    for marker in (" #", "\t#"):
        if marker in value:
            value = value.split(marker, 1)[0].rstrip()
    return value


def _resolve_credential(
    *,
    primary_name: str,
    aliases: Sequence[str],
    env_values: Mapping[str, str],
) -> str | None:
    names = list(dict.fromkeys([primary_name, *aliases]))
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    for name in names:
        value = env_values.get(name)
        if value:
            return value
    return None


def _coerce_alpaca_timeframe(timeframe: str) -> Any:
    amount, unit_name = _parse_timeframe(timeframe)
    try:
        timeframe_module = importlib.import_module("alpaca.data.timeframe")
    except ModuleNotFoundError:
        return timeframe
    timeframe_cls = getattr(timeframe_module, "TimeFrame", None)
    unit_cls = getattr(timeframe_module, "TimeFrameUnit", None)
    if timeframe_cls is None or unit_cls is None:
        return timeframe
    unit = getattr(unit_cls, unit_name)
    return timeframe_cls(amount=amount, unit=unit)


def _coerce_alpaca_adjustment(adjustment_type: AdjustmentType) -> Any:
    try:
        enums_module = importlib.import_module("alpaca.data.enums")
    except ModuleNotFoundError:
        return adjustment_type.value
    adjustment_cls = getattr(enums_module, "Adjustment", None)
    if adjustment_cls is None:
        return adjustment_type.value
    return getattr(adjustment_cls, adjustment_type.name)


def _coerce_alpaca_feed(feed: str) -> Any:
    try:
        enums_module = importlib.import_module("alpaca.data.enums")
    except ModuleNotFoundError:
        return feed
    data_feed_cls = getattr(enums_module, "DataFeed", None)
    if data_feed_cls is None:
        return feed
    return getattr(data_feed_cls, feed.upper())


def _parse_timeframe(timeframe: str) -> tuple[int, str]:
    normalized = timeframe.strip().lower()
    aliases = {
        "1min": (1, "Minute"),
        "1minute": (1, "Minute"),
        "minute": (1, "Minute"),
        "1day": (1, "Day"),
        "day": (1, "Day"),
    }
    if normalized in aliases:
        return aliases[normalized]
    suffix_to_unit = {
        "m": "Minute",
        "min": "Minute",
        "h": "Hour",
        "hour": "Hour",
        "d": "Day",
        "day": "Day",
    }
    for suffix, unit in suffix_to_unit.items():
        if normalized.endswith(suffix):
            raw_amount = normalized[: -len(suffix)] or "1"
            return int(raw_amount), unit
    raise ValueError(f"unsupported Alpaca timeframe: {timeframe}")


def _iter_raw_bars(raw_response: Any) -> list[tuple[str, Any]]:
    data = getattr(raw_response, "data", None)
    if isinstance(data, Mapping):
        return _iter_symbol_mapping(data)
    if isinstance(raw_response, Mapping):
        if "bars" in raw_response:
            return _iter_raw_bars(raw_response["bars"])
        if _looks_like_symbol_mapping(raw_response):
            return _iter_symbol_mapping(raw_response)
        return [(str(raw_response.get("symbol", "")), raw_response)]
    if _is_sequence(raw_response):
        return [(str(_raw_value(raw_bar, "symbol") or ""), raw_bar) for raw_bar in raw_response]
    frame = getattr(raw_response, "df", None)
    if frame is not None and hasattr(frame, "reset_index"):
        records = frame.reset_index().to_dict("records")
        return [(str(record.get("symbol", "")), record) for record in records]
    raise DataAccessError("could not read bars from Alpaca response")


def _iter_symbol_mapping(data: Mapping[Any, Any]) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for symbol, raw_bars in data.items():
        if _is_sequence(raw_bars):
            rows.extend((str(symbol), raw_bar) for raw_bar in raw_bars)
        else:
            rows.append((str(symbol), raw_bars))
    return rows


def _looks_like_symbol_mapping(data: Mapping[Any, Any]) -> bool:
    if not data:
        return False
    non_bar_keys = {"timestamp", "t", "open", "o", "close", "c", "volume", "v"}
    return not any(str(key) in non_bar_keys for key in data)


def _bar_from_alpaca(
    raw_bar: Any,
    *,
    default_symbol: str,
    config: AlpacaDataDownloadConfig,
) -> Bar:
    symbol = str(_raw_value(raw_bar, "symbol") or default_symbol).upper()
    if not symbol:
        raise DataAccessError("Alpaca bar is missing a symbol")
    return Bar(
        symbol=symbol,
        timestamp=_parse_timestamp(_raw_value(raw_bar, "timestamp", "t", "time")),
        timeframe=config.timeframe,
        open=_parse_decimal(_raw_value(raw_bar, "open", "o")),
        high=_parse_decimal(_raw_value(raw_bar, "high", "h")),
        low=_parse_decimal(_raw_value(raw_bar, "low", "l")),
        close=_parse_decimal(_raw_value(raw_bar, "close", "c")),
        volume=_parse_decimal(_raw_value(raw_bar, "volume", "v")),
        vwap=_parse_optional_decimal(_raw_value(raw_bar, "vwap", "vw")),
        trade_count=_parse_optional_int(_raw_value(raw_bar, "trade_count", "n")),
        source="alpaca",
        adjusted=config.adjusted,
        adjustment_type=config.adjustment_type,
        is_complete=True,
    )


def _write_bar_csv(path: Path, bars: Sequence[Bar], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise DataAccessError(f"refusing to overwrite existing bar file: {path}")
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BAR_CSV_FIELDS)
        writer.writeheader()
        for bar in bars:
            writer.writerow(_bar_csv_row(bar))
    temporary_path.replace(path)


def _bar_csv_row(bar: Bar) -> dict[str, str]:
    return {
        "timestamp": bar.timestamp.isoformat(),
        "symbol": bar.symbol,
        "timeframe": bar.timeframe,
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": str(bar.volume),
        "vwap": "" if bar.vwap is None else str(bar.vwap),
        "trade_count": "" if bar.trade_count is None else str(bar.trade_count),
        "source": bar.source,
        "adjusted": str(bar.adjusted).lower(),
        "adjustment_type": "" if bar.adjustment_type is None else bar.adjustment_type.value,
        "is_complete": str(bar.is_complete).lower(),
        "received_at": "" if bar.received_at is None else bar.received_at.isoformat(),
    }


def _raw_value(raw: Any, *names: str) -> Any:
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
        return None
    for name in names:
        value = getattr(raw, name, None)
        if value is not None:
            return value
    return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return ensure_timezone_aware(value)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ensure_timezone_aware(parsed)
    raise DataAccessError("Alpaca bar is missing a timestamp")


def _parse_decimal(value: Any) -> Decimal:
    if value in {None, ""}:
        raise DataAccessError("Alpaca bar is missing a required price or volume field")
    return Decimal(str(value))


def _parse_optional_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    return Decimal(str(value))


def _parse_optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray)


if __name__ == "__main__":
    main()
