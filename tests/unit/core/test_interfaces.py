import inspect
from pathlib import Path

from qts.backtest.commission import CommissionModel
from qts.backtest.fill_model import FillModel
from qts.backtest.slippage import SlippageModel
from qts.brokers.base import Broker
from qts.brokers.capabilities import BrokerCapabilities
from qts.calendar.trading_calendar import TradingCalendar
from qts.core.time import Clock
from qts.data.portal import MarketDataPortal
from qts.data.provider_base import MarketDataProvider
from qts.execution.engine import ExecutionEngine
from qts.portfolio.construction_base import PortfolioConstruction
from qts.portfolio.order_generator import OrderGenerator
from qts.risk.base import RiskManager
from qts.strategy.base import Strategy


def test_phase_1_interfaces_are_abstract() -> None:
    for interface in [
        Clock,
        TradingCalendar,
        MarketDataProvider,
        MarketDataPortal,
        Strategy,
        PortfolioConstruction,
        OrderGenerator,
        RiskManager,
        ExecutionEngine,
        Broker,
        FillModel,
        SlippageModel,
        CommissionModel,
    ]:
        assert inspect.isabstract(interface), interface.__name__


def test_broker_capabilities_is_importable_model() -> None:
    fields = BrokerCapabilities.model_fields

    assert "supported_order_types" in fields
    assert "supports_order_replace" in fields


def test_phase_1_has_no_external_broker_sdk_imports() -> None:
    source_root = Path(__file__).resolve().parents[3] / "src" / "qts"
    import_lines = []
    for path in source_root.rglob("*.py"):
        text = path.read_text()
        import_lines.extend(
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith(("import ", "from "))
        )

    assert not any("import alpaca" in line.lower() for line in import_lines)
    assert not any("from alpaca" in line.lower() for line in import_lines)


def test_strategy_and_risk_contracts_do_not_import_concrete_brokers() -> None:
    source_root = Path(__file__).resolve().parents[3] / "src" / "qts"
    checked_paths = [
        source_root / "strategy" / "base.py",
        source_root / "strategy" / "context.py",
        source_root / "risk" / "base.py",
    ]

    for path in checked_paths:
        text = path.read_text()
        assert "qts.brokers.backtest_broker" not in text
        assert "qts.brokers.alpaca_broker" not in text
        assert "qts.execution.engine" not in text if "strategy" in path.parts else True

