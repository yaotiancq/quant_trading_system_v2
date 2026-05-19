# Interfaces

The abstract interfaces live under `src/qts/` and intentionally avoid concrete broker SDKs,
data provider SDKs, and runtime mode assumptions.

Phase 2 adds concrete local-only implementations that still satisfy those interfaces:
`USEquityCalendar`, `LocalHistoricalDataProvider`, `HistoricalMarketDataPortal`, and
`StaticUniverse`.

Phase 3 adds `BacktestBroker`, `DefaultBacktestFillModel`, slippage models, commission models,
and the order state machine while preserving the shared `Broker` interface.

Phase 4 adds concrete mode-agnostic services around those interfaces:
`StrategyEngine`, `DefaultOrderGenerator`, `BasicRiskManager`, `DefaultExecutionEngine`,
`PerformanceEngine`, and `BacktestRunStore`.

Phase 5 adds `AlpacaBroker`, `AlpacaPaperBroker`, and `AlpacaLiveBroker` implementations of the
same `Broker` interface. They are SDK-optional and can be driven by an injected client.

Phase 6 adds safety services around live broker use: `LiveSafetyService`, `KillSwitch`,
`BrokerHeartbeatMonitor`, `ReconciliationService`, and `LiveTradingRunner`.
