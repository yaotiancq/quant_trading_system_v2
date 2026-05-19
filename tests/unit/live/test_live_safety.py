from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from qts.brokers.base import Broker
from qts.brokers.capabilities import BrokerCapabilities
from qts.core.enums import (
    AccountStatus,
    AssetClass,
    HealthState,
    OrderSide,
    OrderType,
    TimeInForce,
)
from qts.core.models import (
    AccountSnapshot,
    HealthStatus,
    Order,
    OrderFilters,
    OrderRequest,
    Position,
    ReconciliationReport,
    ReplaceOrderRequest,
)
from qts.core.result import Rejection
from qts.live.runner import LiveTradingRunner
from qts.risk.live_safety import LiveSafetyConfig, LiveSafetyService, sanitize_audit_payload


class RecordingBroker(Broker):
    def __init__(self) -> None:
        self.submitted = 0

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            account_id="acct-1",
            timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
            cash=Decimal("1000"),
            equity=Decimal("1000"),
            buying_power=Decimal("1000"),
            portfolio_value=Decimal("1000"),
            long_market_value=Decimal("0"),
            short_market_value=Decimal("0"),
            reserved_buying_power=Decimal("0"),
            status=AccountStatus.ACTIVE,
        )

    def get_positions(self) -> list[Position]:
        return []

    def get_position(self, symbol: str) -> Position:
        raise KeyError(symbol)

    def get_buying_power(self, symbol: str, side: OrderSide, order_type: OrderType) -> Decimal:
        return Decimal("1000")

    def submit_order(self, order_request: OrderRequest) -> Order:
        self.submitted += 1
        raise AssertionError("dry-run test should not submit")

    def cancel_order(self, order_id_or_client_order_id: str) -> Order:
        raise NotImplementedError

    def replace_order(self, order_id: str, replace_request: ReplaceOrderRequest) -> Order:
        raise NotImplementedError

    def get_order(self, order_id_or_client_order_id: str) -> Order:
        raise NotImplementedError

    def list_orders(self, filters: OrderFilters | None = None) -> list[Order]:
        return []

    def list_open_orders(self) -> list[Order]:
        return []

    def subscribe_order_updates(self, handler) -> str:
        return "orders"

    def subscribe_fills(self, handler) -> str:
        return "fills"

    def unsubscribe(self, subscription_id: str) -> None:
        return None

    def reconcile_state(self, local_state: Any) -> ReconciliationReport:
        return ReconciliationReport(
            timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
            matched=True,
        )

    def health_check(self) -> HealthStatus:
        return HealthStatus(
            status=HealthState.OK,
            checked_at=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        )

    def get_capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            supported_asset_classes=[AssetClass.EQUITY],
            supported_order_types=[OrderType.MARKET],
            supported_time_in_force=[TimeInForce.DAY],
            supports_fractional=True,
            supports_short=False,
            supports_extended_hours=False,
            supports_order_replace=False,
            supports_streaming_order_updates=False,
            max_client_order_id_length=48,
        )


def order_request() -> OrderRequest:
    return OrderRequest(
        client_order_id="client-1",
        strategy_id="strategy-1",
        account_id="acct-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("1"),
        time_in_force=TimeInForce.DAY,
        extended_hours=False,
        submitted_at=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
    )


def test_kill_switch_blocks_order_submission() -> None:
    safety = LiveSafetyService()
    safety.engage_kill_switch("operator requested")

    assert not safety.can_submit_orders()
    assert safety.kill_switch.reason == "operator requested"


def test_data_staleness_enters_safe_mode() -> None:
    safety = LiveSafetyService(LiveSafetyConfig(data_staleness_limit_seconds=5))

    ok = safety.check_data_freshness(
        datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        now=datetime(2024, 1, 2, 14, 30, 6, tzinfo=UTC),
    )

    assert not ok
    assert safety.safe_mode
    assert not safety.can_submit_orders()


def test_reconciliation_mismatch_enters_safe_mode() -> None:
    safety = LiveSafetyService()
    report = ReconciliationReport(
        timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        matched=False,
        discrepancies=["position mismatch"],
    )

    assert not safety.handle_reconciliation(report)
    assert safety.safe_mode_reason == "reconciliation mismatch"


def test_audit_payload_sanitizes_secret_like_keys() -> None:
    payload = sanitize_audit_payload({"api_secret": "hidden", "symbol": "AAPL"})

    assert payload == {"api_secret": "***", "symbol": "AAPL"}


def test_dry_run_live_runner_does_not_submit_real_order() -> None:
    broker = RecordingBroker()
    runner = LiveTradingRunner(
        broker=broker,
        safety=LiveSafetyService(LiveSafetyConfig(dry_run=True)),
    )

    result = runner.submit_order_request(order_request())

    assert isinstance(result, Rejection)
    assert broker.submitted == 0
