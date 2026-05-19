# Architecture

Phase 2 adds the local historical data path while preserving the shared dependency direction.
Historical data flows through `LocalHistoricalDataProvider`, optional data quality/manifest
generation, and `HistoricalMarketDataPortal`.

The portal is the no-lookahead boundary. It clips all historical windows to the current logical
clock time before data reaches strategy, portfolio, or risk code.
