from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from qts.core.enums import AdjustmentType
from qts.core.models import Bar
from qts.data.manifest import DataManifestGenerator
from qts.data.quality import DataQualityChecker


def bar(minute: int, *, volume: str = "1000") -> Bar:
    return Bar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 2, 14, minute, tzinfo=UTC),
        timeframe="1m",
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal(volume),
        source="fixture",
        adjusted=True,
        adjustment_type=AdjustmentType.ALL,
        is_complete=True,
    )


def test_data_quality_detects_missing_duplicate_and_bad_volume() -> None:
    bars = [bar(30), bar(31), bar(31), bar(33), bar(34, volume="0")]

    report = DataQualityChecker().check_bars(bars, timeframe="1m")
    checks = {issue.check for issue in report.issues}

    assert "duplicate_bars" in checks
    assert "missing_bars" in checks
    assert "zero_or_negative_volume" in checks
    assert report.missing_data_summary == {"AAPL": 1}


def test_data_manifest_generator_hashes_and_counts_rows(tmp_path) -> None:
    path = tmp_path / "AAPL_1m.csv"
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2024-01-02T14:30:00+00:00,100,101,99,100.5,1000",
                "2024-01-02T14:31:00+00:00,100.5,102,100,101.5,1200",
            ]
        )
    )
    quality_report = DataQualityChecker().check_bars([bar(30), bar(31)], timeframe="1m")

    manifest = DataManifestGenerator().generate(
        symbols=["AAPL"],
        timeframe="1m",
        start_time=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end_time=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        data_source="fixture",
        adjusted=True,
        adjustment_type=AdjustmentType.ALL,
        file_paths=[path],
        quality_report=quality_report,
    )
    output_path = tmp_path / "data_manifest.json"
    manifest.write_json(output_path)
    payload = json.loads(output_path.read_text())

    assert manifest.row_counts[str(path)] == 2
    assert len(manifest.file_hashes[str(path)]) == 64
    assert payload["symbols"] == ["AAPL"]
    assert payload["row_counts"][str(path)] == 2

