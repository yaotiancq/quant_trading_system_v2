"""Bar-driven backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from qts.backtest.clock import BacktestClock
from qts.brokers.backtest_broker import BacktestBroker
from qts.calendar.us_equity_calendar import USEquityCalendar
from qts.config.loader import load_config
from qts.core.enums import AdjustmentType, EventType
from qts.core.events import BarEvent, FillEvent
from qts.core.models import (
    AccountSnapshot,
    Bar,
    Fill,
    Order,
    OrderIntent,
    PortfolioSnapshot,
    RiskDecision,
    Signal,
    TargetPosition,
)
from qts.data.local_provider import LocalHistoricalDataProvider
from qts.data.manifest import DataManifestGenerator
from qts.data.portal import HistoricalMarketDataPortal
from qts.data.quality import DataQualityChecker
from qts.execution.engine import DefaultExecutionEngine
from qts.performance.metrics import PerformanceEngine, PerformanceSummary
from qts.performance.report import render_html_report
from qts.portfolio.fixed_notional import FixedNotionalPortfolioConstruction
from qts.portfolio.order_generator import DefaultOrderGenerator
from qts.risk.manager import BasicRiskManager, RiskConfig
from qts.storage.run_store import BacktestRunStore, make_run_id
from qts.strategy.context import StrategyContext
from qts.strategy.engine import StrategyEngine
from qts.strategy.examples.moving_average_cross import MovingAverageCrossStrategy
from qts.universe.static_universe import StaticUniverse


@dataclass
class BacktestResult:
    run_id: str
    run_dir: Path
    performance_summary: PerformanceSummary
    orders: list[Order]
    fills: list[Fill]
    account_snapshots: list[AccountSnapshot]


class BacktestEngine:
    """Run a deterministic single or multi-symbol bar backtest from config."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        run_store: BacktestRunStore | None = None,
    ) -> None:
        self.config = config
        self.run_store = run_store or BacktestRunStore()

    @classmethod
    def from_config_file(
        cls,
        path: str | Path,
        *,
        run_store: BacktestRunStore | None = None,
    ) -> BacktestEngine:
        return cls(load_config(path), run_store=run_store)

    def run(self) -> BacktestResult:
        account_config = self.config.get("account", {})
        data_config = self.config.get("data", {})
        backtest_config = self.config.get("backtest", {})
        strategy_config = _strategy_config(self.config)
        risk_config = self.config.get("risk", {})
        symbols = _symbols(self.config, strategy_config)
        timeframe = str(data_config.get("timeframe", "1m"))
        adjusted = bool(data_config.get("adjusted", True))
        start = _parse_datetime_or_date(backtest_config.get("start_date"))
        end = _parse_datetime_or_date(backtest_config.get("end_date"), end_of_day=True)
        data_root = data_config.get("root", data_config.get("path", "data/market"))

        calendar = USEquityCalendar()
        provider = LocalHistoricalDataProvider(
            data_root,
            default_timeframe=timeframe,
            adjusted=adjusted,
            adjustment_type=AdjustmentType(str(data_config.get("adjustment_type", "all"))),
        )
        bars = provider.get_bars(symbols, start, end, timeframe, adjusted)
        if not bars:
            raise ValueError("backtest has no bars to replay")
        clock = BacktestClock([bar.timestamp for bar in bars], calendar=calendar)
        universe = StaticUniverse.from_symbols("backtest", symbols)
        portal = HistoricalMarketDataPortal(
            provider,
            clock,
            calendar=calendar,
            universes={"backtest": universe},
            adjusted=adjusted,
            default_timeframe=timeframe,
        )
        instruments = universe.get_instruments(clock.now())
        broker = BacktestBroker(
            account_id=str(account_config.get("account_id", "backtest-account")),
            initial_cash=Decimal(str(account_config.get("initial_cash", "100000"))),
            instruments=instruments,
            current_time=clock.now(),
        )
        strategy = MovingAverageCrossStrategy(
            strategy_id=str(strategy_config.get("strategy_id", "ma-cross")),
            symbol=symbols[0],
            fast_window=int(strategy_config.get("fast_window", 3)),
            slow_window=int(strategy_config.get("slow_window", 5)),
            target_notional=Decimal(str(strategy_config.get("target_notional", "1000"))),
        )
        context = StrategyContext(
            strategy_id=strategy.strategy_id,
            account_id=broker.account_id,
            clock=clock,
            data=portal,
            portfolio_view=lambda: _portfolio_snapshot(broker),
            config=strategy_config,
            state_store={},
            logger=None,
        )
        strategy_engine = StrategyEngine([strategy], {strategy.strategy_id: context})
        portfolio = FixedNotionalPortfolioConstruction(
            Decimal(str(self.config.get("portfolio", {}).get("default_notional", "1000")))
        )
        order_generator = DefaultOrderGenerator()
        risk_manager = BasicRiskManager(
            RiskConfig(
                max_order_notional=Decimal(str(risk_config.get("max_order_notional", "5000"))),
                max_symbol_exposure_pct=Decimal(
                    str(risk_config.get("max_symbol_exposure_pct", "0.10"))
                ),
                max_gross_exposure_pct=Decimal(
                    str(risk_config.get("max_gross_exposure_pct", "1.00"))
                ),
            )
        )
        execution = DefaultExecutionEngine(
            broker=broker,
            risk_manager=risk_manager,
            market_snapshot_provider=lambda symbol: broker.latest_market_snapshots[symbol],
            portfolio_snapshot_provider=lambda: _portfolio_snapshot(broker),
        )
        strategy_engine.initialize()

        signals: list[Signal] = []
        targets: list[TargetPosition] = []
        intents: list[OrderIntent] = []
        fills: list[Fill] = []
        account_snapshots: list[AccountSnapshot] = []
        position_records: list[dict[str, Any]] = []
        grouped_bars = sorted(bars, key=lambda bar: bar.timestamp)
        for bar in grouped_bars:
            clock.set_time(bar.timestamp)
            event = BarEvent(
                event_id=f"bar-{bar.symbol}-{bar.timestamp.isoformat()}",
                event_type=EventType.BAR,
                timestamp=bar.timestamp,
                source=bar.source,
                bar=bar,
            )
            new_fills = broker.process_market_event(event)
            fills.extend(new_fills)
            for fill in new_fills:
                fill_event = FillEvent(
                    event_id=f"fill-{fill.fill_id}",
                    event_type=EventType.FILL,
                    timestamp=fill.timestamp,
                    source="backtest_engine",
                    fill=fill,
                )
                execution.handle_fill(fill_event)
                strategy_engine.dispatch_fill(fill_event)

            event_signals = strategy_engine.dispatch_market_event(event)
            event_targets = portfolio.build_targets(
                event_signals,
                _portfolio_snapshot(broker),
                broker.latest_market_snapshots,
            )
            event_intents = order_generator.generate_order_intents(
                event_targets,
                broker.get_positions(),
                broker.get_account(),
                broker.latest_market_snapshots,
            )
            for intent in event_intents:
                execution.submit_order_intent(intent)
            signals.extend(event_signals)
            targets.extend(event_targets)
            intents.extend(event_intents)
            account_snapshot = broker.get_account()
            account_snapshots.append(account_snapshot)
            position_records.append(
                {
                    "timestamp": bar.timestamp.isoformat(),
                    "positions": [position.to_dict() for position in broker.get_positions()],
                }
            )

        strategy_engine.stop()
        all_orders = broker.list_orders()
        summary = PerformanceEngine().summarize(
            account_snapshots=account_snapshots,
            orders=all_orders,
            fills=fills,
            initial_cash=Decimal(str(account_config.get("initial_cash", "100000"))),
        )
        run_id = str(self.config.get("run_id") or make_run_id("backtest", strategy.strategy_id))
        run_dir = self._write_artifacts(
            run_id=run_id,
            config=self.config,
            provider=provider,
            symbols=symbols,
            timeframe=timeframe,
            start=start,
            end=end,
            bars=bars,
            signals=signals,
            targets=targets,
            intents=intents,
            risk_decisions=execution.risk_decisions,
            orders=all_orders,
            fills=fills,
            position_records=position_records,
            account_snapshots=account_snapshots,
            summary=summary,
        )
        return BacktestResult(
            run_id=run_id,
            run_dir=run_dir,
            performance_summary=summary,
            orders=all_orders,
            fills=fills,
            account_snapshots=account_snapshots,
        )

    def _write_artifacts(
        self,
        *,
        run_id: str,
        config: dict[str, Any],
        provider: LocalHistoricalDataProvider,
        symbols: list[str],
        timeframe: str,
        start: datetime,
        end: datetime,
        bars: list[Bar],
        signals: list[Signal],
        targets: list[TargetPosition],
        intents: list[OrderIntent],
        risk_decisions: list[RiskDecision],
        orders: list[Order],
        fills: list[Fill],
        position_records: list[dict[str, Any]],
        account_snapshots: list[AccountSnapshot],
        summary: PerformanceSummary,
    ) -> Path:
        run_dir = self.run_store.create_run_dir(run_id)
        quality_report = DataQualityChecker().check_bars(bars, timeframe=timeframe)
        file_paths: list[str | Path] = [
            provider.resolve_bar_file(symbol, timeframe) for symbol in symbols
        ]
        manifest = DataManifestGenerator().generate(
            symbols=symbols,
            timeframe=timeframe,
            start_time=start,
            end_time=end,
            data_source="local",
            adjusted=provider.adjusted,
            adjustment_type=provider.adjustment_type,
            file_paths=file_paths,
            quality_report=quality_report,
        )
        manifest.write_json(run_dir / "data_manifest.json")
        self.run_store.write_json(run_dir, "config_snapshot.json", config)
        self.run_store.write_jsonl(run_dir, "signals.jsonl", signals)
        self.run_store.write_jsonl(run_dir, "targets.jsonl", targets)
        self.run_store.write_jsonl(run_dir, "order_intents.jsonl", intents)
        self.run_store.write_jsonl(run_dir, "risk_decisions.jsonl", risk_decisions)
        self.run_store.write_jsonl(run_dir, "orders.jsonl", orders)
        self.run_store.write_jsonl(run_dir, "fills.jsonl", fills)
        self.run_store.write_jsonl(run_dir, "positions.jsonl", position_records)
        self.run_store.write_jsonl(run_dir, "account_snapshots.jsonl", account_snapshots)
        self.run_store.write_json(run_dir, "performance_summary.json", summary.to_dict())
        self.run_store.write_text(run_dir, "report.html", render_html_report(summary))
        self.run_store.write_text(run_dir, "logs.txt", "backtest completed\n")
        return run_dir


def _portfolio_snapshot(broker: BacktestBroker) -> PortfolioSnapshot:
    account = broker.get_account()
    return PortfolioSnapshot(
        account_id=account.account_id,
        timestamp=account.timestamp,
        positions=broker.get_positions(),
        total_market_value=account.long_market_value - account.short_market_value,
    )


def _strategy_config(config: dict[str, Any]) -> dict[str, Any]:
    strategies = config.get("strategies", {})
    if isinstance(strategies, list) and strategies:
        first_strategy = strategies[0]
        if isinstance(first_strategy, dict):
            return dict(first_strategy)
        return {}
    if isinstance(strategies, dict):
        return dict(strategies)
    return {}


def _symbols(config: dict[str, Any], strategy_config: dict[str, Any]) -> list[str]:
    universe = config.get("universe", {})
    if isinstance(universe, dict) and universe.get("symbols"):
        return list(universe["symbols"])
    if strategy_config.get("symbols"):
        return list(strategy_config["symbols"])
    if strategy_config.get("symbol"):
        return [str(strategy_config["symbol"])]
    raise ValueError("backtest config requires universe.symbols or strategy symbol(s)")


def _parse_datetime_or_date(value: Any, *, end_of_day: bool = False) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(23, 59, 59) if end_of_day else time.min, tzinfo=UTC)
    if value is None:
        raise ValueError("backtest start_date and end_date are required")
    text = str(value)
    if "T" in text:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    parsed_date = date.fromisoformat(text)
    return datetime.combine(
        parsed_date,
        time(23, 59, 59) if end_of_day else time.min,
        tzinfo=UTC,
    )
