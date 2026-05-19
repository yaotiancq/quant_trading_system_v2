# Alpaca Integration

Phase 5 adds an SDK-optional Alpaca adapter. The adapter accepts an injected Alpaca-like trading
client, maps internal `OrderRequest` objects to Alpaca payloads, maps account/position/order
responses back to internal models, and keeps credentials behind environment variable names.

No module imports the external Alpaca SDK at import time. Application wiring can provide a real
SDK client later, while unit tests use a mock client.

Phase 6 adds live-safety controls around broker usage: kill switch, safe mode, data staleness,
broker health checks, reconciliation mismatch handling, sanitized audit events, and dry-run order
blocking.
