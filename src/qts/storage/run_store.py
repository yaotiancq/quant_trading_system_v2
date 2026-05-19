"""Run artifact storage."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from qts.core.models import QtsModel
from qts.core.time import utc_now


class BacktestRunStore:
    """Write backtest artifacts under `runs/backtests/{run_id}`."""

    def __init__(self, root: str | Path = "runs/backtests") -> None:
        self.root = Path(root)

    def create_run_dir(self, run_id: str) -> Path:
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def write_json(self, run_dir: Path, name: str, payload: dict[str, Any]) -> Path:
        path = run_dir / name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path

    def write_jsonl(self, run_dir: Path, name: str, records: Iterable[Any]) -> Path:
        path = run_dir / name
        lines = []
        for record in records:
            if isinstance(record, QtsModel):
                lines.append(json.dumps(record.to_dict(), sort_keys=True))
            else:
                lines.append(json.dumps(record, sort_keys=True))
        path.write_text("\n".join(lines) + ("\n" if lines else ""))
        return path

    def write_text(self, run_dir: Path, name: str, text: str) -> Path:
        path = run_dir / name
        path.write_text(text)
        return path


def make_run_id(mode: str, strategy_group: str) -> str:
    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return f"{mode}-{strategy_group}-{timestamp}"
