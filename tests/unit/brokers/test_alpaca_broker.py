from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from qts.brokers.alpaca_broker import AlpacaBrokerConfig, AlpacaOrderMapper, AlpacaPaperBroker
from qts.core.enums import OrderSide, OrderStatus, OrderType, PositionSide, TimeInForce
from qts.core.models import OrderRequest, Position
from qts.live.reconciliation import ReconciliationService


class FakeAlpacaClient:
    def __init__(self) -> None:
        self.submitted_payloads = []
        self.orders = {}
        self.positions = [
            {
                "symbol": "AAPL",
                "qty": "2",
                "avg_entry_price": "100",
                "current_price": "101",
                "market_value": "202",
                "cost_basis": "200",
                "unrealized_pl": "2",
            }
        ]

    def get_account(self):
        return {
            "cash": "10000",
            "equity": "10002",
            "buying_power": "10000",
            "portfolio_value": "10002",
            "long_market_value": "202",
            "short_market_value": "0",
            "status": "active",
        }

    def submit_order(self, **payload):
        self.submitted_payloads.append(payload)
        raw = {
            "id": "alpaca-1",
            "client_order_id": payload["client_order_id"],
            "symbol": payload["symbol"],
            "side": payload["side"],
            "type": payload["type"],
            "time_in_force": payload["time_in_force"],
            "qty": payload.get("qty"),
            "filled_qty": "0",
            "status": "new",
            "extended_hours": payload["extended_hours"],
            "created_at": "2024-01-02T14:30:00+00:00",
            "submitted_at": "2024-01-02T14:30:00+00:00",
            "updated_at": "2024-01-02T14:30:00+00:00",
        }
        self.orders[raw["id"]] = raw
        return raw

    def get_order_by_id(self, order_id):
        if order_id in self.orders:
            return self.orders[order_id]
        return self.get_order_by_client_order_id(order_id)

    def get_order_by_client_order_id(self, client_order_id):
        for order in self.orders.values():
            if order["client_order_id"] == client_order_id:
                return order
        raise KeyError(client_order_id)

    def get_orders(self):
        return list(self.orders.values())

    def cancel_order_by_id(self, order_id):
        self.orders[order_id]["status"] = "canceled"

    def get_all_positions(self):
        return self.positions


def order_request() -> OrderRequest:
    return OrderRequest(
        client_order_id="client-1",
        strategy_id="strategy-1",
        account_id="acct-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("1.5"),
        time_in_force=TimeInForce.DAY,
        extended_hours=False,
        submitted_at=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
    )


def test_alpaca_config_loads_credentials_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "secret")
    config = AlpacaBrokerConfig(
        environment="paper",
        api_key_env="ALPACA_PAPER_API_KEY",
        api_secret_env="ALPACA_PAPER_API_SECRET",
    )

    credentials = config.load_credentials()

    assert credentials.api_key == "key"
    assert credentials.api_secret == "secret"


def test_alpaca_mapper_uses_client_order_id_and_decimal_strings() -> None:
    payload = AlpacaOrderMapper().to_submit_payload(order_request())

    assert payload["client_order_id"] == "client-1"
    assert payload["qty"] == "1.5"
    assert payload["type"] == "market"


def test_alpaca_paper_broker_submit_cancel_and_list_orders() -> None:
    client = FakeAlpacaClient()
    broker = AlpacaPaperBroker(client=client, account_id="acct-1")

    submitted = broker.submit_order(order_request())
    canceled = broker.cancel_order(submitted.order_id)
    open_orders = broker.list_open_orders()

    assert client.submitted_payloads[0]["client_order_id"] == "client-1"
    assert submitted.status is OrderStatus.NEW
    assert canceled.status is OrderStatus.CANCELED
    assert open_orders == []


def test_alpaca_reconciliation_reports_position_mismatch() -> None:
    broker = AlpacaPaperBroker(client=FakeAlpacaClient(), account_id="acct-1")
    local = Position(
        account_id="acct-1",
        symbol="AAPL",
        qty=Decimal("1"),
        avg_entry_price=Decimal("100"),
        cost_basis=Decimal("100"),
        side=PositionSide.LONG,
        updated_at=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
    )

    report = ReconciliationService(broker).reconcile_positions([local])

    assert not report.matched
    assert report.discrepancies
