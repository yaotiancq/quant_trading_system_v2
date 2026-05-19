"""Local historical market data provider."""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from qts.core.enums import AdjustmentType, HealthState, MarketSession
from qts.core.errors import DataAccessError, UnsupportedOperationError
from qts.core.models import Bar, HealthStatus, MarketSnapshot, Quote, Trade
from qts.core.time import ensure_timezone_aware, utc_now
from qts.data.provider_base import MarketDataProvider


class LocalHistoricalDataProvider(MarketDataProvider):
    """Load local historical bar files from CSV, with optional Parquet support."""

    def __init__(
        self,
        data_root: str | Path,
        *,
        source: str = "local",
        default_timeframe: str = "1m",
        adjusted: bool = True,
        adjustment_type: AdjustmentType = AdjustmentType.ALL,
    ) -> None:
        self.data_root = Path(data_root)
        self.source = source
        self.default_timeframe = default_timeframe
        self.adjusted = adjusted
        self.adjustment_type = adjustment_type
        self._bar_cache: dict[tuple[str, str], list[Bar]] = {}

    def get_bars(
        self,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        timeframe: str,
        adjusted: bool,
    ) -> list[Bar]:
        start = ensure_timezone_aware(start)
        end = ensure_timezone_aware(end)
        bars: list[Bar] = []
        for symbol in symbols:
            for bar in self._load_symbol_bars(symbol, timeframe):
                if start <= bar.timestamp <= end and bar.adjusted is adjusted:
                    bars.append(bar)
        return sorted(bars, key=lambda bar: (bar.symbol, bar.timestamp))

    def get_latest_bar(self, symbol: str, timeframe: str) -> Bar:
        bars = self._load_symbol_bars(symbol, timeframe)
        if not bars:
            raise DataAccessError(f"no bars available for {symbol} {timeframe}")
        return bars[-1]

    def get_latest_quote(self, symbol: str) -> Quote:
        raise UnsupportedOperationError(f"local historical provider has no quote data for {symbol}")

    def get_latest_trade(self, symbol: str) -> Trade:
        raise UnsupportedOperationError(f"local historical provider has no trade data for {symbol}")

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        latest_bar = self.get_latest_bar(symbol, self.default_timeframe)
        return MarketSnapshot(
            timestamp=latest_bar.timestamp,
            symbol=symbol,
            latest_bar=latest_bar,
            session=MarketSession.REGULAR,
            is_tradable=True,
            source=self.source,
        )

    def subscribe_bars(
        self,
        symbols: Sequence[str],
        timeframe: str,
        handler: Callable[[Bar], None],
    ) -> str:
        raise UnsupportedOperationError("local historical provider does not support streaming bars")

    def subscribe_quotes(self, symbols: Sequence[str], handler: Callable[[Quote], None]) -> str:
        raise UnsupportedOperationError(
            "local historical provider does not support streaming quotes"
        )

    def subscribe_trades(self, symbols: Sequence[str], handler: Callable[[Trade], None]) -> str:
        raise UnsupportedOperationError(
            "local historical provider does not support streaming trades"
        )

    def unsubscribe(self, subscription_id: str) -> None:
        raise UnsupportedOperationError("local historical provider has no active subscriptions")

    def health_check(self) -> HealthStatus:
        return HealthStatus(
            status=HealthState.OK if self.data_root.exists() else HealthState.UNAVAILABLE,
            checked_at=utc_now(),
            message=str(self.data_root),
        )

    def _load_symbol_bars(self, symbol: str, timeframe: str) -> list[Bar]:
        key = (symbol, timeframe)
        if key not in self._bar_cache:
            path = self.resolve_bar_file(symbol, timeframe)
            self._bar_cache[key] = sorted(
                self._load_bar_file(path, symbol=symbol, timeframe=timeframe),
                key=lambda bar: bar.timestamp,
            )
        return self._bar_cache[key]

    def resolve_bar_file(self, symbol: str, timeframe: str) -> Path:
        """Return the local file path that would be used for a symbol/timeframe."""

        return self._resolve_bar_file(symbol, timeframe)

    def _resolve_bar_file(self, symbol: str, timeframe: str) -> Path:
        candidates = [
            self.data_root / f"{symbol}_{timeframe}.csv",
            self.data_root / f"{symbol}.csv",
            self.data_root / symbol / f"{timeframe}.csv",
            self.data_root / f"{symbol}_{timeframe}.parquet",
            self.data_root / f"{symbol}.parquet",
            self.data_root / symbol / f"{timeframe}.parquet",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise DataAccessError(
            f"no local bar file found for {symbol} {timeframe} under {self.data_root}"
        )

    def _load_bar_file(self, path: Path, *, symbol: str, timeframe: str) -> list[Bar]:
        if path.suffix.lower() == ".csv":
            return self._load_csv_bars(path, default_symbol=symbol, default_timeframe=timeframe)
        if path.suffix.lower() == ".parquet":
            return self._load_parquet_bars(path, default_symbol=symbol, default_timeframe=timeframe)
        raise DataAccessError(f"unsupported bar file extension: {path.suffix}")

    def _load_csv_bars(
        self,
        path: Path,
        *,
        default_symbol: str,
        default_timeframe: str,
    ) -> list[Bar]:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        return [
            self._row_to_bar(
                row,
                default_symbol=default_symbol,
                default_timeframe=default_timeframe,
            )
            for row in rows
        ]

    def _load_parquet_bars(
        self,
        path: Path,
        *,
        default_symbol: str,
        default_timeframe: str,
    ) -> list[Bar]:
        try:
            from pyarrow import parquet
        except ModuleNotFoundError as exc:
            raise UnsupportedOperationError(
                "Parquet loading requires installing the 'parquet' extra: "
                ".venv/bin/python -m pip install -e '.[parquet]'"
            ) from exc
        table = parquet.read_table(path)
        return [
            self._row_to_bar(
                row,
                default_symbol=default_symbol,
                default_timeframe=default_timeframe,
            )
            for row in table.to_pylist()
        ]

    def _row_to_bar(
        self,
        row: dict[str, Any],
        *,
        default_symbol: str,
        default_timeframe: str,
    ) -> Bar:
        timestamp = _parse_timestamp(str(row["timestamp"]))
        return Bar(
            symbol=str(row.get("symbol") or default_symbol),
            timestamp=timestamp,
            timeframe=str(row.get("timeframe") or default_timeframe),
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            volume=Decimal(str(row["volume"])),
            vwap=_optional_decimal(row.get("vwap")),
            trade_count=_optional_int(row.get("trade_count")),
            source=str(row.get("source") or self.source),
            adjusted=_parse_bool(row.get("adjusted"), self.adjusted),
            adjustment_type=AdjustmentType(
                str(row.get("adjustment_type") or self.adjustment_type.value)
            ),
            is_complete=_parse_bool(row.get("is_complete"), True),
            received_at=_optional_timestamp(row.get("received_at")),
        )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ensure_timezone_aware(parsed)


def _optional_timestamp(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    return _parse_timestamp(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    return Decimal(str(value))


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _parse_bool(value: Any, default: bool) -> bool:
    if value in {None, ""}:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"cannot parse boolean value: {value!r}")
