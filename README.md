# Quant Trading System v2

Phase 2 establishes the local historical data path, U.S. equity calendar, static universe,
data quality checks, data manifests, and a clock-aware `MarketDataPortal`.

## Current Status

- Phase: 2
- Scope: core models, abstract interfaces, local historical data, calendar, static universe,
  no-lookahead portal, data quality checks, manifests, and tests
- Not included yet: backtest broker, strategy engine, Alpaca adapters, live runner, or CLI

## Development

Use the existing virtual environment launcher:

```bash
.venv/bin/python -m pytest
```

Optional checks after installing development dependencies:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
```
