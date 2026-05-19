# Quant Trading System v2

Phase 7 completes the first repository pass with docs, sample data, CLI wiring, examples, and
regression coverage.

## Current Status

- Phase: 7
- Scope: core models, abstract interfaces, local historical data, calendar, static universe,
  no-lookahead portal, data quality checks, manifests, backtest broker, fill model, slippage,
  commission, strategy engine, portfolio construction, risk, execution, full backtest, artifacts,
  Alpaca paper adapter, reconciliation scaffolding, live safety, dry-run runner, CLI, docs,
  sample data, examples, and tests
- Not included yet: production Alpaca SDK client construction and advanced strategy/risk models

## Development

Use the existing virtual environment launcher:

```bash
.venv/bin/python -m pytest
```

Run the included example backtest:

```bash
.venv/bin/python examples/run_backtest_ma_cross.py
```

Or use the CLI module:

```bash
.venv/bin/python -m qts.cli.main --config config/backtest.yaml
```

Optional checks after installing development dependencies:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
```
