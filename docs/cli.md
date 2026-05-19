# CLI

Run the example backtest:

```bash
.venv/bin/python -m qts.cli.main --config config/backtest.yaml
```

The installed script entry point is:

```bash
qts-backtest --config config/backtest.yaml
```

The command prints the run id, run directory, and total return. Artifacts are written under
`runs/backtests/{run_id}/`.

