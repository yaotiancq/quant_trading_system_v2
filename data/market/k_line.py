import argparse
import csv
import datetime
import html
import json
import os
import sys
from decimal import Decimal
from typing import Iterable

# Import MA calculation from strategy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
from qts.strategy.examples.moving_average_cross import MovingAverageCrossStrategy


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


def calculate_ma_values(closes: list[float], window: int) -> list[float | None]:
    """Calculate moving average values. Returns None for initial bars where MA cannot be calculated."""
    if not closes or window <= 0:
        return [None] * len(closes)
    
    ma_values = [None] * (window - 1)  # Not enough data for first (window-1) bars
    closes_decimal = [Decimal(str(c)) for c in closes]
    
    for i in range(window - 1, len(closes)):
        try:
            ma = MovingAverageCrossStrategy.calculate_simple_ma(closes_decimal[:i+1], window)
            ma_values.append(float(ma))
        except ValueError:
            ma_values.append(None)
    
    return ma_values


def chart_html(klines: Iterable[KLine], title: str, fast_window: int = 10, slow_window: int = 20) -> str:
    klines_list = list(klines)
    timestamps = [k.timestamp.isoformat() for k in klines_list]
    open_values = [k.open_price for k in klines_list]
    high_values = [k.high_price for k in klines_list]
    low_values = [k.low_price for k in klines_list]
    close_values = [k.close_price for k in klines_list]
    volume_values = [k.volume for k in klines_list]
    vwap_values = [k.vwap for k in klines_list]
    
    # Calculate initial MA values
    fast_ma_values = calculate_ma_values(close_values, fast_window)
    slow_ma_values = calculate_ma_values(close_values, slow_window)

    chart_data = {
        "timestamps": timestamps,
        "open": open_values,
        "high": high_values,
        "low": low_values,
        "close": close_values,
        "volume": volume_values,
        "vwap": vwap_values,
        "fast_ma": fast_ma_values,
        "slow_ma": slow_ma_values,
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
    #chart {{ width: 100vw; height: 85vh; }}
    #meta {{ padding: 12px; background: #f8f9fb; border-bottom: 1px solid #ddd; }}
    .control-group {{ display: inline-block; margin-right: 20px; }}
    .control-group label {{ font-size: 14px; margin-right: 8px; }}
    .control-group input {{ font-size: 14px; padding: 4px 8px; width: 80px; }}
  </style>
</head>
<body>
  <div id="meta"><strong>{safe_title}</strong></div>
  <div style="padding: 12px; background: #f1f3f5; border-bottom: 1px solid #ddd;">
    <div class="control-group">
      <label for="timezone-select">Timezone:</label>
      <select id="timezone-select" style="font-size: 14px; padding: 4px 8px;">
        <option value="UTC">UTC</option>
        <option value="America/New_York">America/New_York</option>
        <option value="America/Los_Angeles">America/Los_Angeles</option>
        <option value="Local">Browser Local</option>
      </select>
    </div>
    <div class="control-group">
      <label for="fast-window">Fast MA:</label>
      <input type="number" id="fast-window" min="2" value="{fast_window}">
    </div>
    <div class="control-group">
      <label for="slow-window">Slow MA:</label>
      <input type="number" id="slow-window" min="2" value="{slow_window}">
    </div>
  </div>
  <div id="chart"></div>
  <script>
    const chartData = {data_json};
    const plotTimestamps = chartData.timestamps.map((ts) => new Date(ts));
    const timeZoneFormatters = {{
      UTC: new Intl.DateTimeFormat("en-US", {{
        timeZone: "UTC",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }}),
      "America/New_York": new Intl.DateTimeFormat("en-US", {{
        timeZone: "America/New_York",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }}),
      "America/Los_Angeles": new Intl.DateTimeFormat("en-US", {{
        timeZone: "America/Los_Angeles",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }}),
      Local: new Intl.DateTimeFormat("en-US", {{
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }}),
    }};

    function formatIsoTime(date, timezone) {{
      const formatter = timeZoneFormatters[timezone] || timeZoneFormatters.UTC;
      const parts = formatter.formatToParts(date);
      const values = parts.reduce((acc, part) => {{
        if (part.type !== 'literal') {{
          acc[part.type] = part.value;
        }}
        return acc;
      }}, {{}});
      return `${{values.year}}-${{values.month}}-${{values.day}} ${{values.hour}}:${{values.minute}}:${{values.second}}`;
    }}

    function formattedXValues(timezone) {{
      return plotTimestamps.map((date) => formatIsoTime(date, timezone));
    }}

    function calculateMA(closes, window) {{
      if (window <= 0 || closes.length < window) {{
        return Array(closes.length).fill(null);
      }}
      const ma = Array(window - 1).fill(null);
      for (let i = window - 1; i < closes.length; i++) {{
        const sum = closes.slice(i - window + 1, i + 1).reduce((a, b) => a + b, 0);
        ma.push(sum / window);
      }}
      return ma;
    }}

    const initialTimeZone = 'UTC';
    const initialTimeValues = formattedXValues(initialTimeZone);

    const traceCandle = {{
      x: initialTimeValues,
      open: chartData.open,
      high: chartData.high,
      low: chartData.low,
      close: chartData.close,
      type: 'candlestick',
      name: 'Price',
      increasing: {{ line: {{ color: '#26a69a' }} }},
      decreasing: {{ line: {{ color: '#ef5350' }} }},
      text: chartData.volume,
      hovertemplate: 'Time: %{{x}}<br>Open: %{{open}}<br>High: %{{high}}<br>Low: %{{low}}<br>Close: %{{close}}<br>Volume: %{{text}}<extra></extra>',
    }};
    const traceVwap = {{
      x: initialTimeValues,
      y: chartData.vwap,
      type: 'scatter',
      mode: 'lines',
      name: 'VWAP',
      line: {{ color: '#ff9900', width: 2 }},
      hovertemplate: 'VWAP: %{{y:.2f}}<extra></extra>',
    }};
    const traceVolume = {{
      x: initialTimeValues,
      y: chartData.volume,
      marker: {{ color: '#888' }},
      type: 'bar',
      name: 'Volume',
      yaxis: 'y2',
      opacity: 0.5,
      hovertemplate: 'Volume: %{{y}}<extra></extra>',
    }};
    const traceFastMA = {{
      x: initialTimeValues,
      y: chartData.fast_ma,
      type: 'scatter',
      mode: 'lines',
      name: 'Fast MA',
      line: {{ color: '#2196F3', width: 1.5 }},
      hovertemplate: 'Fast MA: %{{y:.2f}}<extra></extra>',
    }};
    const traceSlowMA = {{
      x: initialTimeValues,
      y: chartData.slow_ma,
      type: 'scatter',
      mode: 'lines',
      name: 'Slow MA',
      line: {{ color: '#FF5722', width: 1.5 }},
      hovertemplate: 'Slow MA: %{{y:.2f}}<extra></extra>',
    }};

    const layout = {{
      title: chartData.title,
      xaxis: {{
        rangeslider: {{ visible: false }},
        type: 'category',
        showticklabels: false,
      }},
      yaxis: {{ domain: [0.25, 1], title: 'Price' }},
      yaxis2: {{ domain: [0, 0.2], title: 'Volume' }},
      legend: {{ orientation: 'h', x: 0, y: 1.05 }},
      margin: {{ t: 60, b: 30, l: 60, r: 30 }},
      hovermode: 'x unified',
    }};
    Plotly.newPlot('chart', [traceCandle, traceVwap, traceVolume, traceFastMA, traceSlowMA], layout, {{ responsive: true }});

    const timezoneSelect = document.getElementById('timezone-select');
    const fastWindowInput = document.getElementById('fast-window');
    const slowWindowInput = document.getElementById('slow-window');

    timezoneSelect.addEventListener('change', (event) => {{
      const timezone = event.target.value;
      const updatedTimeValues = formattedXValues(timezone);
      Plotly.restyle('chart', {{ x: [updatedTimeValues, updatedTimeValues, updatedTimeValues, updatedTimeValues, updatedTimeValues] }});
    }});

    function updateMovingAverages() {{
      const fastWindow = parseInt(fastWindowInput.value, 10);
      const slowWindow = parseInt(slowWindowInput.value, 10);
      
      if (fastWindow < 2 || slowWindow < 2) {{
        alert('Window size must be at least 2');
        return;
      }}
      
      const newFastMA = calculateMA(chartData.close, fastWindow);
      const newSlowMA = calculateMA(chartData.close, slowWindow);
      
      Plotly.restyle('chart', {{ y: [undefined, undefined, undefined, newFastMA, newSlowMA] }}, [3, 4]);
    }}

    fastWindowInput.addEventListener('change', updateMovingAverages);
    slowWindowInput.addEventListener('change', updateMovingAverages);
  </script>
</body>
</html>"""


def default_output_path(csv_path: str) -> str:
    base, _ = os.path.splitext(csv_path)
    return f"{base}_kline.html"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an interactive K-line (candlestick) HTML chart from CSV market data with moving averages."
    )
    parser.add_argument("csv_file", help="Input CSV file path containing OHLC market data.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output HTML file path. Defaults to <csv_file>_kline.html.",
        default=None,
    )
    parser.add_argument(
        "--fast-window",
        type=int,
        default=10,
        help="Window size for fast moving average. Defaults to 10.",
    )
    parser.add_argument(
        "--slow-window",
        type=int,
        default=20,
        help="Window size for slow moving average. Defaults to 20.",
    )
    args = parser.parse_args()

    csv_path = args.csv_file
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    if args.fast_window <= 0 or args.slow_window <= 0:
        raise ValueError("Window sizes must be positive")
    if args.fast_window >= args.slow_window:
        raise ValueError("fast_window must be smaller than slow_window")

    output_path = args.output or default_output_path(csv_path)
    klines = parse_csv(csv_path)
    if not klines:
        raise ValueError(f"No valid K-line data found in {csv_path}")

    title = f"K-line chart for {os.path.basename(csv_path)}"
    html_content = chart_html(klines, title, fast_window=args.fast_window, slow_window=args.slow_window)

    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(html_content)

    print(f"Interactive HTML chart written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    