from __future__ import annotations

import json
from decimal import Decimal

from qts.backtest.engine import BacktestEngine
from qts.storage.run_store import BacktestRunStore


def write_prices(path) -> None:
    rows = ["timestamp,open,high,low,close,volume"]
    closes = [
        Decimal("100"),
        Decimal("99"),
        Decimal("98"),
        Decimal("101"),
        Decimal("102"),
        Decimal("103"),
        Decimal("104"),
        Decimal("105"),
        Decimal("106"),
        Decimal("107"),
        Decimal("108"),
        Decimal("109"),
    ]
    for minute, price in enumerate(closes):
        rows.append(
            ",".join(
                [
                    f"2024-01-02T14:{30 + minute:02d}:00+00:00",
                    str(price),
                    str(price + Decimal("1")),
                    str(price - Decimal("1")),
                    str(price + Decimal("0.50")),
                    "1000",
                ]
            )
        )
    path.write_text("\n".join(rows))


def test_backtest_engine_runs_from_config_and_writes_artifacts(tmp_path) -> None:
    data_root = tmp_path / "market"
    data_root.mkdir()
    write_prices(data_root / "AAPL_1m.csv")
    config = {
        "run_id": "phase4-e2e",
        "mode": "backtest",
        "account": {"account_id": "acct-1", "initial_cash": "100000"},
        "data": {
            "root": str(data_root),
            "timeframe": "1m",
            "adjusted": True,
            "adjustment_type": "all",
        },
        "backtest": {"start_date": "2024-01-02", "end_date": "2024-01-02"},
        "universe": {"symbols": ["AAPL"]},
        "strategies": {
            "strategy_id": "ma-cross",
            "symbol": "AAPL",
            "fast_window": 2,
            "slow_window": 3,
            "target_notional": "1000",
        },
        "portfolio": {"default_notional": "1000"},
        "risk": {"max_order_notional": "5000"},
    }

    result = BacktestEngine(
        config,
        run_store=BacktestRunStore(tmp_path / "runs"),
    ).run()

    assert result.performance_summary.fill_rate > Decimal("0")
    assert result.fills
    assert (result.run_dir / "performance_summary.json").exists()
    assert (result.run_dir / "report.html").exists()
    assert (result.run_dir / "data_manifest.json").exists()
    payload = json.loads((result.run_dir / "performance_summary.json").read_text())
    assert "total_return" in payload
