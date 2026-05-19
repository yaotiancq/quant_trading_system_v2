# Interfaces

The abstract interfaces live under `src/qts/` and intentionally avoid concrete broker SDKs,
data provider SDKs, and runtime mode assumptions.

Phase 2 adds concrete local-only implementations that still satisfy those interfaces:
`USEquityCalendar`, `LocalHistoricalDataProvider`, `HistoricalMarketDataPortal`, and
`StaticUniverse`.
