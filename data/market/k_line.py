import argparse
import csv
import datetime
import html
import json
import os
from typing import Iterable


class KLine:
    def __init__(self, timestamp, open_price, high_price, low_price, close_price, volume, vwap=None):
        self.timestamp = timestamp
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume
        self.vwap = vwap

    def __repr__(self):
        return (
            f"KLine(timestamp={self.timestamp}, open={self.open_price}, "
            f"high={self.high_price}, low={self.low_price}, close={self.close_price}, "
            f"volume={self.volume}, vwap={self.vwap})"
        )


def parse_csv(file_path: str) -> list[KLine]:
    klines: list[KLine] = []
    with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not row or not row.get("timestamp"):
                continue

            timestamp_text = row.get("timestamp") or row.get("time") or ""
            try:
                timestamp = datetime.datetime.fromisoformat(timestamp_text)
            except ValueError:
                timestamp = datetime.datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))

            def parse_float(key: str, default: float | None = None) -> float | None:
                value = row.get(key, "")
                if value is None or value == "":
                    return default
                try:
                    return float(value)
                except ValueError:
                    return default

            open_price = parse_float("open") or 0.0
            high_price = parse_float("high") or 0.0
            low_price = parse_float("low") or 0.0
            close_price = parse_float("close") or 0.0
            volume = parse_float("volume") or 0.0
            vwap = parse_float("vwap")

            klines.append(
                KLine(
                    timestamp=timestamp,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                    vwap=vwap,
                )
            )
    return klines


def chart_html(klines: Iterable[KLine], title: str) -> str:
    timestamps = [k.timestamp.isoformat() for k in klines]
    open_values = [k.open_price for k in klines]
    high_values = [k.high_price for k in klines]
    low_values = [k.low_price for k in klines]
    close_values = [k.close_price for k in klines]
    volume_values = [k.volume for k in klines]
    vwap_values = [k.vwap for k in klines]

    chart_data = {
        "timestamps": timestamps,
        "open": open_values,
        "high": high_values,
        "low": low_values,
        "close": close_values,
        "volume": volume_values,
        "vwap": vwap_values,
        "title": title,
    }

    safe_title = html.escape(title)
    data_json = json.dumps(chart_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{safe_title}</title>
  <script src="https://cdn.plot.ly/plotly-2.29.0.min.js"></script>
  <style>
    body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
    #chart {{ width: 100vw; height: 90vh; }}
    #meta {{ padding: 12px; background: #f8f9fb; border-bottom: 1px solid #ddd; }}
  </style>
</head>
<body>
  <div id="meta"><strong>{safe_title}</strong></div>
  <div id="chart"></div>
  <script>
    const chartData = {data_json};
    const traceCandle = {{
      x: chartData.timestamps,
      open: chartData.open,
      high: chartData.high,
      low: chartData.low,
      close: chartData.close,
      type: 'candlestick',
      name: 'Price',
      increasing: {{ line: {{ color: '#26a69a' }} }},
      decreasing: {{ line: {{ color: '#ef5350' }} }},
    }};
    const traceVwap = {{
      x: chartData.timestamps,
      y: chartData.vwap,
      type: 'scatter',
      mode: 'lines',
      name: 'VWAP',
      line: {{ color: '#ff9900', width: 2 }},
      hovertemplate: 'VWAP: %{{y:.2f}}<extra></extra>',
    }};
    const traceVolume = {{
      x: chartData.timestamps,
      y: chartData.volume,
      marker: {{ color: '#888' }},
      type: 'bar',
      name: 'Volume',
      yaxis: 'y2',
      opacity: 0.5,
    }};
    const layout = {{
      title: chartData.title,
      xaxis: {{ rangeslider: {{ visible: false }}, type: 'date' }},
      yaxis: {{ domain: [0.25, 1], title: 'Price' }},
      yaxis2: {{ domain: [0, 0.2], title: 'Volume' }},
      legend: {{ orientation: 'h', x: 0, y: 1.05 }},
      margin: {{ t: 60, b: 40, l: 60, r: 30 }},
      hovermode: 'x unified',
    }};
    Plotly.newPlot('chart', [traceCandle, traceVwap, traceVolume], layout, {{ responsive: true }});
  </script>
</body>
</html>"""


def default_output_path(csv_path: str) -> str:
    base, _ = os.path.splitext(csv_path)
    return f"{base}_kline.html"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an interactive K-line (candlestick) HTML chart from CSV market data."
    )
    parser.add_argument("csv_file", help="Input CSV file path containing OHLC market data.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output HTML file path. Defaults to <csv_file>_kline.html.",
        default=None,
    )
    args = parser.parse_args()

    csv_path = args.csv_file
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    output_path = args.output or default_output_path(csv_path)
    klines = parse_csv(csv_path)
    if not klines:
        raise ValueError(f"No valid K-line data found in {csv_path}")

    title = f"K-line chart for {os.path.basename(csv_path)}"
    html_content = chart_html(klines, title)

    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(html_content)

    print(f"Interactive HTML chart written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    