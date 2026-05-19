# Configuration

The backtest config uses these core blocks:

- `account`: account id and initial cash.
- `data`: local data root, timeframe, adjustment policy, and source provenance.
- `universe`: symbols to include.
- `strategies`: moving-average strategy settings.
- `portfolio`: default sizing.
- `risk`: pre-trade limits.
- `backtest`: start/end dates and timing policy.

Paper/live configs reference environment variable names for credentials. Secret values must not
be stored in config files or run artifacts.

## Alpaca Data Download

`config/download_alpaca_data.yaml` controls the independent historical data download step:

- `symbols`: symbols to download.
- `timeframe`: QTS timeframe such as `1m`.
- `start` / `end`: timezone-aware ISO datetimes.
- `output_dir`: local cache directory consumed by backtests.
- `feed`: Alpaca data feed, for example `iex`.
- `adjusted` / `adjustment_type`: bar adjustment metadata written to CSV.
- `api_key_env` / `api_secret_env`: environment variable names for credentials.
- `overwrite`: whether to replace existing cached CSV files.

Run the downloader before a backtest when using real Alpaca data:

```bash
.venv/bin/python -m qts.data.alpaca_downloader --config config/download_alpaca_data.yaml
.venv/bin/python -m qts.cli.main --config config/backtest.yaml
```
