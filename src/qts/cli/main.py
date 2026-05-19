"""QTS command-line interface."""

from __future__ import annotations

import argparse

from qts.backtest.engine import BacktestEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qts-backtest")
    parser.add_argument(
        "--config",
        default="config/backtest.yaml",
        help="Path to a backtest config file.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = BacktestEngine.from_config_file(args.config).run()
    print(f"run_id={result.run_id}")
    print(f"run_dir={result.run_dir}")
    print(f"total_return={result.performance_summary.total_return}")


if __name__ == "__main__":
    main()
