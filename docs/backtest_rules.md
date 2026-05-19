# Backtest Rules

Backtest execution is deferred until Phase 3 and Phase 4. The Phase 1 contracts already encode
the invariant that strategies produce signals and orders flow through execution and broker
interfaces.

Phase 2 adds the first backtest data invariant: historical data returned by the portal must not
extend beyond the current logical clock time.
