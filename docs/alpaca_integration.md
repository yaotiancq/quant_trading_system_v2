# Alpaca Integration

Phase 5 adds an SDK-optional Alpaca adapter. The adapter accepts an injected Alpaca-like trading
client, maps internal `OrderRequest` objects to Alpaca payloads, maps account/position/order
responses back to internal models, and keeps credentials behind environment variable names.

No module imports the external Alpaca SDK at import time. Application wiring can provide a real
SDK client later, while unit tests use a mock client.

Phase 6 adds live-safety controls around broker usage: kill switch, safe mode, data staleness,
broker health checks, reconciliation mismatch handling, sanitized audit events, and dry-run order
blocking.

Historical backtest data uses a separate acquisition module:

- `qts.data.alpaca_downloader` builds an Alpaca historical data client only when invoked.
- It writes normalized CSV files such as `data/market/AAPL_1m.csv`.
- It reads credentials from process environment first, then from the configured `.env` file.
- `BacktestEngine` reads those files through `LocalHistoricalDataProvider`; it does not call
  Alpaca during simulation.
- The backtest manifest records `data.source` from config, so Alpaca-sourced caches remain visible
  in run artifacts.

Example:

```bash
.venv/bin/python -m qts.data.alpaca_downloader --config config/download_alpaca_data.yaml
.venv/bin/python -m qts.cli.main --config config/backtest.yaml
```
