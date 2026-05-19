"""Data manifest generation."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from pydantic import Field

from qts.core.enums import AdjustmentType
from qts.core.errors import UnsupportedOperationError
from qts.core.models import QtsModel
from qts.core.time import utc_now
from qts.data.quality import DataQualityReport


class DataManifest(QtsModel):
    symbols: list[str]
    timeframe: str
    start_time: datetime
    end_time: datetime
    data_source: str
    adjusted: bool
    adjustment_type: AdjustmentType
    file_paths: list[str]
    file_hashes: dict[str, str]
    row_counts: dict[str, int]
    missing_data_summary: dict[str, int] = Field(default_factory=dict)
    created_at: datetime

    def write_json(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))


class DataManifestGenerator:
    """Create reproducibility manifests for local data inputs."""

    def generate(
        self,
        *,
        symbols: list[str],
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        data_source: str,
        adjusted: bool,
        adjustment_type: AdjustmentType,
        file_paths: list[str | Path],
        quality_report: DataQualityReport | None = None,
    ) -> DataManifest:
        normalized_paths = [str(Path(path)) for path in file_paths]
        return DataManifest(
            symbols=symbols,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            data_source=data_source,
            adjusted=adjusted,
            adjustment_type=adjustment_type,
            file_paths=normalized_paths,
            file_hashes={path: _sha256_file(Path(path)) for path in normalized_paths},
            row_counts={path: _count_rows(Path(path)) for path in normalized_paths},
            missing_data_summary=quality_report.missing_data_summary if quality_report else {},
            created_at=utc_now(),
        )


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _count_rows(path: Path) -> int:
    if path.suffix.lower() == ".csv":
        with path.open(newline="") as handle:
            return sum(1 for _row in csv.DictReader(handle))
    if path.suffix.lower() == ".parquet":
        try:
            from pyarrow import parquet
        except ModuleNotFoundError as exc:
            raise UnsupportedOperationError(
                "Parquet row counting requires installing the 'parquet' extra"
            ) from exc
        metadata = parquet.read_metadata(path)
        return int(metadata.num_rows)
    raise UnsupportedOperationError(f"unsupported manifest file extension: {path.suffix}")
