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

Download Alpaca historical bars into the local cache:

```bash
.venv/bin/python -m qts.data.alpaca_downloader --config config/download_alpaca_data.yaml
```

The downloader reads `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` from `.env` by default.

After reinstalling the editable package, the script entry point is:

```bash
qts-download-alpaca-data --config config/download_alpaca_data.yaml
```
