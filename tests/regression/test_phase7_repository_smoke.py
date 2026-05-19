from pathlib import Path

from qts.cli.main import build_parser


def test_phase7_docs_and_sample_data_exist() -> None:
    root = Path(__file__).resolve().parents[2]

    assert (root / "docs" / "architecture.md").exists()
    assert (root / "docs" / "interfaces.md").exists()
    assert (root / "docs" / "backtest_rules.md").exists()
    assert (root / "docs" / "alpaca_integration.md").exists()
    assert (root / "docs" / "cli.md").exists()
    assert (root / "docs" / "configuration.md").exists()
    assert (root / "data" / "market" / "AAPL_1m.csv").exists()


def test_cli_parser_accepts_config_argument() -> None:
    args = build_parser().parse_args(["--config", "config/backtest.yaml"])

    assert args.config == "config/backtest.yaml"

