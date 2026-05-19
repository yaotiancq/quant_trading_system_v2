"""Data quality checks for local historical bars."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import Field

from qts.core.models import Bar, QtsModel
from qts.core.time import utc_now


class DataQualityIssue(QtsModel):
    check: str
    symbol: str
    message: str
    timestamp: datetime | None = None
    severity: str = "error"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataQualityReport(QtsModel):
    checked_at: datetime
    symbols: list[str]
    timeframe: str
    issues: list[DataQualityIssue] = Field(default_factory=list)
    missing_data_summary: dict[str, int] = Field(default_factory=dict)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def passed(self) -> bool:
        return not self.issues


class DataQualityChecker:
    """Run deterministic quality checks on historical bars."""

    def check_bars(
        self,
        bars: Sequence[Bar],
        *,
        timeframe: str,
        expected_interval: timedelta | None = None,
        allow_zero_volume: bool = False,
        allow_mixed_adjustment: bool = False,
    ) -> DataQualityReport:
        symbols = sorted({bar.symbol for bar in bars})
        interval = expected_interval or timeframe_to_timedelta(timeframe)
        issues: list[DataQualityIssue] = []
        missing_summary: dict[str, int] = {}
        grouped: dict[str, list[Bar]] = defaultdict(list)
        for bar in bars:
            grouped[bar.symbol].append(bar)
            self._check_price_and_volume(bar, issues, allow_zero_volume=allow_zero_volume)
        for symbol, symbol_bars in grouped.items():
            self._check_duplicates(symbol, symbol_bars, issues)
            self._check_order(symbol, symbol_bars, issues)
            missing_count = self._check_missing(symbol, symbol_bars, interval, issues)
            if missing_count:
                missing_summary[symbol] = missing_count
            if not allow_mixed_adjustment:
                self._check_adjustment_consistency(symbol, symbol_bars, issues)
        return DataQualityReport(
            checked_at=utc_now(),
            symbols=symbols,
            timeframe=timeframe,
            issues=issues,
            missing_data_summary=missing_summary,
        )

    def _check_price_and_volume(
        self,
        bar: Bar,
        issues: list[DataQualityIssue],
        *,
        allow_zero_volume: bool,
    ) -> None:
        prices = {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
        }
        for field_name, value in prices.items():
            if value <= Decimal("0"):
                issues.append(
                    DataQualityIssue(
                        check="negative_price",
                        symbol=bar.symbol,
                        timestamp=bar.timestamp,
                        message=f"{field_name} must be positive",
                    )
                )
        if bar.volume < Decimal("0") or (bar.volume == Decimal("0") and not allow_zero_volume):
            issues.append(
                DataQualityIssue(
                    check="zero_or_negative_volume",
                    symbol=bar.symbol,
                    timestamp=bar.timestamp,
                    message="volume must be positive",
                )
            )

    def _check_duplicates(
        self,
        symbol: str,
        bars: Sequence[Bar],
        issues: list[DataQualityIssue],
    ) -> None:
        seen: set[tuple[datetime, str]] = set()
        for bar in bars:
            key = (bar.timestamp, bar.timeframe)
            if key in seen:
                issues.append(
                    DataQualityIssue(
                        check="duplicate_bars",
                        symbol=symbol,
                        timestamp=bar.timestamp,
                        message="duplicate timestamp for symbol/timeframe",
                    )
                )
            seen.add(key)

    def _check_order(
        self,
        symbol: str,
        bars: Sequence[Bar],
        issues: list[DataQualityIssue],
    ) -> None:
        previous: datetime | None = None
        for bar in bars:
            if previous is not None and bar.timestamp < previous:
                issues.append(
                    DataQualityIssue(
                        check="out_of_order_rows",
                        symbol=symbol,
                        timestamp=bar.timestamp,
                        message="rows are not sorted by timestamp",
                    )
                )
            previous = bar.timestamp

    def _check_missing(
        self,
        symbol: str,
        bars: Sequence[Bar],
        interval: timedelta,
        issues: list[DataQualityIssue],
    ) -> int:
        sorted_bars = sorted(bars, key=lambda bar: bar.timestamp)
        missing_count = 0
        for previous, current in zip(sorted_bars, sorted_bars[1:], strict=False):
            gap = current.timestamp - previous.timestamp
            if gap > interval:
                count = int(gap / interval) - 1
                missing_count += count
                issues.append(
                    DataQualityIssue(
                        check="missing_bars",
                        symbol=symbol,
                        timestamp=current.timestamp,
                        message=f"{count} missing bar(s) before timestamp",
                        metadata={"missing_count": count},
                    )
                )
        return missing_count

    def _check_adjustment_consistency(
        self,
        symbol: str,
        bars: Sequence[Bar],
        issues: list[DataQualityIssue],
    ) -> None:
        adjusted_values = {bar.adjusted for bar in bars}
        if len(adjusted_values) > 1:
            issues.append(
                DataQualityIssue(
                    check="adjustment_consistency",
                    symbol=symbol,
                    message="mixed adjusted and raw bars are not allowed",
                )
            )


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    unit = timeframe[-1]
    amount = int(timeframe[:-1])
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError(f"unsupported timeframe: {timeframe}")
