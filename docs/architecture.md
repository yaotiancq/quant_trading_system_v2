# Architecture

Phase 2 adds the local historical data path while preserving the shared dependency direction.
Historical data flows through `LocalHistoricalDataProvider`, optional data quality/manifest
generation, and `HistoricalMarketDataPortal`.

The portal is the no-lookahead boundary. It clips all historical windows to the current logical
clock time before data reaches strategy, portfolio, or risk code.

Phase 3 adds `BacktestBroker` as the first concrete broker implementation. Orders are submitted
to broker state first, reserve buying power or sellable quantity, and are filled only when later
market events are replayed through `process_market_event()`.

Phase 4 connects the research path end to end. `BacktestEngine` replays bars, lets the broker
process open orders first, dispatches the event to strategies, converts signals to targets and
order intents, evaluates risk, submits through `DefaultExecutionEngine -> Broker`, and writes run
artifacts plus a performance summary.

Phase 7 adds package/usage polish: CLI wiring, sample local data, configuration docs, and
regression smoke tests.

Alpaca historical data is handled as an independent acquisition step:

```text
Alpaca historical API -> qts.data.alpaca_downloader -> data/market/*.csv
data/market/*.csv -> LocalHistoricalDataProvider -> HistoricalMarketDataPortal -> BacktestEngine
```

The backtest engine never calls Alpaca directly. This keeps simulations deterministic and makes
the exact downloaded CSV files part of the run manifest.
