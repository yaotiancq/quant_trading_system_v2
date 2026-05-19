"""Run the moving-average cross backtest from a config file."""

from __future__ import annotations

from pathlib import Path

from qts.backtest.engine import BacktestEngine


def main() -> None:
    config_path = Path("config/backtest.yaml")
    result = BacktestEngine.from_config_file(config_path).run()
    print(f"run_id={result.run_id}")
    print(f"run_dir={result.run_dir}")
    print(f"total_return={result.performance_summary.total_return}")


if __name__ == "__main__":
    main()
