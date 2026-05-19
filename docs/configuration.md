# Configuration

The backtest config uses these core blocks:

- `account`: account id and initial cash.
- `data`: local data root, timeframe, and adjustment policy.
- `universe`: symbols to include.
- `strategies`: moving-average strategy settings.
- `portfolio`: default sizing.
- `risk`: pre-trade limits.
- `backtest`: start/end dates and timing policy.

Paper/live configs reference environment variable names for credentials. Secret values must not
be stored in config files or run artifacts.

