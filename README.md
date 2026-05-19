# Quant Trading System v2

Phase 1 establishes the scaffold, domain models, and abstract contracts for a modular
quantitative trading system. Strategy, risk, execution, and broker-facing code are intentionally
mode-agnostic at this stage.

## Current Status

- Phase: 1
- Scope: core models, event models, abstract interfaces, validation, and tests
- Not included yet: concrete data providers, backtest broker, Alpaca adapters, live runner, or CLI

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

