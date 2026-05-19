"""Simple HTML report generation."""

from __future__ import annotations

from qts.performance.metrics import PerformanceSummary


def render_html_report(summary: PerformanceSummary) -> str:
    rows = "\n".join(
        f"<tr><th>{key}</th><td>{value}</td></tr>"
        for key, value in summary.to_dict().items()
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Backtest Report</title>"
        "<style>body{font-family:sans-serif;margin:2rem}table{border-collapse:collapse}"
        "th,td{border:1px solid #ddd;padding:0.4rem;text-align:left}</style></head>"
        f"<body><h1>Backtest Report</h1><table>{rows}</table></body></html>"
    )
