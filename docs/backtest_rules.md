# Backtest Rules

Backtest execution is deferred until Phase 3 and Phase 4. The Phase 1 contracts already encode
the invariant that strategies produce signals and orders flow through execution and broker
interfaces.

Phase 2 adds the first backtest data invariant: historical data returned by the portal must not
extend beyond the current logical clock time.

Phase 3 adds execution invariants:

- Market orders submitted on an event cannot fill on the same event by default.
- Open orders are filled only by the fill model during market-event replay.
- Cash and positions change only through `Fill` application.
- Buy orders reserve buying power until filled, canceled, rejected, or expired.
- Limit orders use conservative intrabar behavior by default.

Phase 4 event order:

1. Set the logical clock to the current bar timestamp.
2. Let `BacktestBroker` process open orders against the current bar.
3. Dispatch fills back to execution/risk/strategy listeners.
4. Dispatch the bar to strategies.
5. Convert signals to targets and order intents.
6. Submit approved orders through `DefaultExecutionEngine`.
7. Record account, positions, orders, fills, risk decisions, and performance artifacts.
