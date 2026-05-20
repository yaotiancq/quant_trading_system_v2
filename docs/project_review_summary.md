# Quant Trading System v2 — Project Review Summary

## Overview

This repository implements a modular quantitative trading system in Python, focused on:
- deterministic historical backtesting
- standardized strategy execution
- portfolio construction and order generation
- risk-aware order submission
- simulated brokerage execution
- artifact and performance report generation
- scaffolded live/paper trading adapters

It is a Phase 7 proof-of-concept repository, providing a strong architecture for research and backtesting, with future expansion paths for production live integration.

## Key Files and Entry Points

- `README.md`
  - project status, development instructions, example usage, backtest CLI and sample script
- `pyproject.toml`
  - package metadata, Python version, dependencies, CLI entrypoint `qts-backtest`
- `src/qts/cli/main.py`
  - CLI entrypoint for backtests
- `examples/run_backtest_ma_cross.py`
  - sample example script using the moving-average crossover strategy
- `config/backtest.yaml`
  - sample backtest configuration
- `runs/backtests/`
  - generated run artifacts from sample backtests

## Architecture Overview

The system is built from composable layers:
- `core` — shared domain model definitions, event types, time utilities, enumerations
- `data` — historical data provider, portal, manifest generation, quality checks
- `universe` — instrument universe abstraction and static universe implementation
- `strategy` — strategy lifecycle and signal generation
- `portfolio` — target sizing and order intent generation
- `risk` — order/risk decision evaluation
- `execution` — risk-aware execution engine interface and default implementation
- `brokers` — backtest broker simulator and Alpaca adapter scaffolding
- `backtest` — orchestrator, clock, fill model, slippage, commission
- `performance` — metrics calculation and report rendering
- `storage` — persistent run artifact writing

## Backtest Flow

The main backtest loop is implemented in `src/qts/backtest/engine.py`.

High-level flow:
1. Load configuration from a YAML file.
2. Build the calendar, data provider, and historical data portal.
3. Load bars for configured symbols and date range.
4. Create a `BacktestClock` from bar timestamps.
5. Instantiate a static universe of instruments.
6. Construct `BacktestBroker` with account and instrument state.
7. Initialize strategy and strategy engine.
8. Build portfolio construction, order generation, risk manager, execution engine.
9. For each bar event:
   - process fills from open orders using the broker and fill model
   - dispatch the market event to strategies
   - translate strategy signals into target positions
   - create order intents from targets
   - evaluate intents and requests with risk manager
   - submit approved orders through the execution engine
   - record account snapshots, positions, orders, fills, and artifacts
10. After replay, summarize performance and save run outputs.

## Core Domain Models

All shared runtime data is represented using Pydantic models in `src/qts/core/models.py`.

Important models include:
- `Bar` — market bar data
- `MarketSnapshot` — latest market state for a symbol
- `Signal` — trading signal emitted by a strategy
- `TargetPosition` — desired portfolio exposure
- `OrderIntent` — high-level execution request from portfolio logic
- `OrderRequest` / `Order` — concrete broker execution objects
- `Fill` — executed fills and their economics
- `AccountSnapshot` / `PortfolioSnapshot` — account and position state
- `RiskDecision` — risk evaluation results

## Data and No-Lookahead Boundary

### `LocalHistoricalDataProvider`
- Loads bar data from local CSV or Parquet files.
- Supports adjusted or raw bars.
- Resolves files from paths such as `SYMBOL_1m.csv`, `SYMBOL.csv`, or `SYMBOL/1m.csv`.

### `AlpacaHistoricalDataDownloader`
- Downloads historical bars from an Alpaca-like data client as a separate acquisition step.
- Writes normalized CSV files under `data/market/`.
- Uses Alpaca SIP data by default.
- Reads credentials from `.env` by default with `APCA_API_KEY_ID` and
  `APCA_API_SECRET_KEY`.
- Keeps the backtest engine file-based and deterministic.

### `HistoricalMarketDataPortal`
- Exposes historical window access to strategies.
- Enforces no-lookahead by clipping historical data to the current backtest clock time.
- Provides the latest bar for current symbol state and tradeability checks.

## Portfolio and Order Generation

### `FixedNotionalPortfolioConstruction`
- Converts `Signal` objects into `TargetPosition` objects with fixed notional sizes.
- FLAT signals generate zero size targets, LONG signals allocate fixed notional.

### `DefaultOrderGenerator`
- Converts target positions into market `OrderIntent`s.
- Computes quantity deltas relative to current holdings.
- Nets intents by symbol and applies default execution style.

## Execution and Broker Simulation

### `DefaultExecutionEngine`
- Receives `OrderIntent`s from portfolio/order logic.
- Evaluates intent and request through a `RiskManager`.
- Submits approved `OrderRequest`s to the broker interface.
- Tracks orders, rejections, and risk decisions.

### `BacktestBroker`
- A stateful, deterministic broker simulator.
- Tracks account cash, positions, open/closed/rejected orders, and market snapshots.
- Reserve buying power or sell quantity when orders are submitted.
- Applies fills only when later market events are replayed.

### Fill and Market Modeling

#### `DefaultBacktestFillModel`
- Supports market, limit, stop, and stop-limit order types.
- Uses latest market snapshot data to decide if orders fill.
- Supports partial fills and configurable fill policies.

#### Slippage Models
- `NoSlippage`
- `FixedBpsSlippage`
- `SpreadBasedSlippage`
- `VolumeParticipationSlippage`

#### Commission Models
- `ZeroCommission`
- `FixedPerShareCommission`
- `BpsCommission`

## Risk Management

### `BasicRiskManager`
- Provides an MVP risk layer for order intents and requests.
- Enforces limits such as `max_order_notional`, `max_order_qty`, and buying power.
- Can modify orders to fit risk limits or reject them.
- Returns structured `RiskDecision` objects.

## Strategy Engine

### `StrategyEngine`
- Manages strategy lifecycle hooks: `initialize`, `on_start`, `on_bar`, `on_fill`, `on_stop`.
- Dispatches market data and fill events to strategies.
- Captures strategy errors without stopping the engine.

### `MovingAverageCrossStrategy`
- Example strategy implementation.
- Generates `Signal` objects based on short and long moving average crossover.
- Uses historical bars from the portal for lookback calculations.

## Live / Paper Trading Scaffolding

### `PaperTradingRunner` and `LiveTradingRunner`
- Minimal wrappers around broker submission.
- Support for live safety gating in `LiveTradingRunner`.

### `AlpacaBroker`
- Adapter stub for Alpaca-like trading clients.
- Contains order mapping, account/position conversion, and event emission support.
- Designed to be SDK-optional and not require Alpaca packages at import time.

## Performance and Artifacts

### `PerformanceEngine`
- Calculates summary metrics such as:
  - total return
  - volatility
  - sharpe ratio
  - max drawdown
  - turnover
  - average slippage
  - total commission
  - fill rate
- Many advanced metrics are placeholder zeros in this phase.

### `BacktestRunStore`
- Writes run outputs to `runs/backtests/{run_id}`.
- Persisted artifacts include:
  - `config_snapshot.json`
  - `data_manifest.json`
  - `signals.jsonl`
  - `targets.jsonl`
  - `order_intents.jsonl`
  - `risk_decisions.jsonl`
  - `orders.jsonl`
  - `fills.jsonl`
  - `positions.jsonl`
  - `account_snapshots.jsonl`
  - `performance_summary.json`
  - `report.html`
  - `logs.txt`

## Running the Project

Recommended commands:
```bash
.venv/bin/python -m pytest
.venv/bin/python -m qts.data.alpaca_downloader --config config/download_alpaca_data.yaml
.venv/bin/python examples/run_backtest_ma_cross.py
.venv/bin/python -m qts.cli.main --config config/backtest.yaml
```

## Extension Points

This codebase is designed for extensibility. The most natural extension points are:
- new strategies via `Strategy` subclasses
- new portfolio sizing models via `PortfolioConstruction`
- new order generation and execution styles via `OrderGenerator`
- new risk policies via `RiskManager`
- new broker backends via `Broker`
- new market data sources via `MarketDataProvider`
- new performance metrics and reports in `performance`

## Notes

- The `config` loader supports simple YAML natively; install PyYAML for full YAML parsing.
- Parquet data support is optional and enabled via the `parquet` extra.
- The backtest is bar-driven and deterministic, with no-lookahead enforced through `HistoricalMarketDataPortal`.
- `AlpacaBroker` is a scaffold, not a complete production adapter.

---

### Download
This file is available at `docs/project_review_summary.md` in the repository.
Feel free to download it from your workspace or export it from Git.
