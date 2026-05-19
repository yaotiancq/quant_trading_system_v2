from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from qts.backtest.commission import FixedPerShareCommission
from qts.backtest.fill_model import DefaultBacktestFillModel, FillModelConfig
from qts.brokers.backtest_broker import BacktestBroker
from qts.core.enums import (
    AdjustmentType,
    AssetClass,
    EventType,
    MarketSession,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
)
from qts.core.events import BarEvent
from qts.core.models import Bar, Instrument, MarketSnapshot, OrderRequest, ReplaceOrderRequest


def ts(minutes: int) -> datetime:
    return datetime(2024, 1, 2, 14, 30, tzinfo=UTC) + timedelta(minutes=minutes)


def instrument(symbol: str = "AAPL") -> Instrument:
    return Instrument(
        instrument_id=f"US.EQUITY.{symbol}",
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        currency="USD",
        tradable=True,
        fractionable=True,
        timezone="America/New_York",
    )


def bar_event(minutes: int, *, open_: str = "100", high: str = "101", low: str = "99") -> BarEvent:
    close = Decimal(open_) + Decimal("0.50")
    bar = Bar(
        symbol="AAPL",
        timestamp=ts(minutes),
        timeframe="1m",
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=close,
        volume=Decimal("1000"),
        source="fixture",
        adjusted=True,
        adjustment_type=AdjustmentType.ALL,
        is_complete=True,
    )
    return BarEvent(
        event_id=f"bar-{minutes}",
        event_type=EventType.BAR,
        timestamp=bar.timestamp,
        source="fixture",
        bar=bar,
    )


def broker(
    *,
    initial_cash: str = "10000",
    fill_model: DefaultBacktestFillModel | None = None,
) -> BacktestBroker:
    broker_ = BacktestBroker(
        account_id="acct-1",
        initial_cash=Decimal(initial_cash),
        instruments=[instrument()],
        current_time=ts(0),
        fill_model=fill_model,
    )
    broker_.set_market_snapshot(
        MarketSnapshot(
            timestamp=ts(0),
            symbol="AAPL",
            latest_bar=bar_event(0, open_="100").bar,
            session=MarketSession.REGULAR,
            is_tradable=True,
            source="fixture",
        )
    )
    return broker_


def order_request(
    client_order_id: str,
    *,
    side: OrderSide = OrderSide.BUY,
    order_type: OrderType = OrderType.MARKET,
    qty: str = "10",
    limit_price: str | None = None,
    stop_price: str | None = None,
) -> OrderRequest:
    return OrderRequest(
        client_order_id=client_order_id,
        strategy_id="strategy-1",
        account_id="acct-1",
        symbol="AAPL",
        side=side,
        order_type=order_type,
        qty=Decimal(qty),
        limit_price=Decimal(limit_price) if limit_price is not None else None,
        stop_price=Decimal(stop_price) if stop_price is not None else None,
        time_in_force=TimeInForce.DAY,
        extended_hours=False,
        submitted_at=ts(0),
    )


def test_market_order_fills_only_on_next_event_and_releases_reservation() -> None:
    broker_ = broker()
    events = []
    fills = []
    broker_.subscribe_order_updates(events.append)
    broker_.subscribe_fills(fills.append)

    order = broker_.submit_order(order_request("client-1"))

    assert order.status is OrderStatus.NEW
    assert broker_.get_account().reserved_buying_power == Decimal("1055.250")
    assert broker_.process_market_event(bar_event(0, open_="100")) == []
    emitted = broker_.process_market_event(bar_event(1, open_="101"))

    filled = broker_.get_order(order.order_id)
    position = broker_.get_position("AAPL")
    account = broker_.get_account()
    assert len(emitted) == 1
    assert filled.status is OrderStatus.FILLED
    assert filled.avg_fill_price == Decimal("101")
    assert position.qty == Decimal("10")
    assert position.side is PositionSide.LONG
    assert account.cash == Decimal("8990")
    assert account.reserved_buying_power == Decimal("0")
    assert len(events) >= 2
    assert len(fills) == 1


def test_limit_order_uses_conservative_default_fill_policy() -> None:
    broker_ = broker()
    order = broker_.submit_order(
        order_request(
            "client-2",
            order_type=OrderType.LIMIT,
            limit_price="99",
        )
    )

    broker_.process_market_event(bar_event(1, open_="100", high="101", low="98"))

    assert broker_.get_order(order.order_id).status is OrderStatus.NEW
    assert broker_.get_position("AAPL").qty == Decimal("0")


def test_stop_order_triggers_and_fills_as_market_order() -> None:
    broker_ = broker()
    order = broker_.submit_order(
        order_request(
            "client-3",
            order_type=OrderType.STOP,
            stop_price="102",
        )
    )

    broker_.process_market_event(bar_event(1, open_="101", high="103", low="100"))

    assert broker_.get_order(order.order_id).status is OrderStatus.FILLED
    assert broker_.get_position("AAPL").qty == Decimal("10")


def test_stop_limit_can_trigger_but_remain_unfilled() -> None:
    broker_ = broker()
    order = broker_.submit_order(
        order_request(
            "client-4",
            order_type=OrderType.STOP_LIMIT,
            stop_price="102",
            limit_price="101",
        )
    )

    broker_.process_market_event(bar_event(1, open_="103", high="104", low="102"))

    assert broker_.get_order(order.order_id).status is OrderStatus.NEW
    assert broker_.get_position("AAPL").qty == Decimal("0")


def test_partial_fill_keeps_order_open_and_releases_reservation_proportionally() -> None:
    fill_model = DefaultBacktestFillModel(
        config=FillModelConfig(
            allow_partial_fill=True,
            max_participation_rate=Decimal("0.01"),
        )
    )
    broker_ = broker(fill_model=fill_model)
    order = broker_.submit_order(order_request("client-5", qty="20"))

    broker_.process_market_event(bar_event(1, open_="100"))

    partially_filled = broker_.get_order(order.order_id)
    assert partially_filled.status is OrderStatus.PARTIALLY_FILLED
    assert partially_filled.filled_qty == Decimal("10.00")
    assert partially_filled.remaining_qty == Decimal("10.00")
    assert broker_.get_account().reserved_buying_power == Decimal("1055.25000")


def test_sell_order_updates_cash_position_and_realized_pnl_only_after_fill() -> None:
    broker_ = broker()
    broker_.submit_order(order_request("client-6", qty="10"))
    broker_.process_market_event(bar_event(1, open_="100"))
    sell = broker_.submit_order(
        order_request(
            "client-7",
            side=OrderSide.SELL,
            qty="4",
        )
    )

    assert broker_.get_position("AAPL").qty == Decimal("10")
    broker_.process_market_event(bar_event(2, open_="110"))

    filled_sell = broker_.get_order(sell.order_id)
    position = broker_.get_position("AAPL")
    assert filled_sell.status is OrderStatus.FILLED
    assert position.qty == Decimal("6")
    assert position.realized_pnl == Decimal("40")
    assert broker_.get_account().cash == Decimal("9440")


def test_cancel_order_releases_reserved_buying_power() -> None:
    broker_ = broker()
    order = broker_.submit_order(order_request("client-8", qty="10"))

    canceled = broker_.cancel_order(order.order_id)

    assert canceled.status is OrderStatus.CANCELED
    assert broker_.get_account().reserved_buying_power == Decimal("0")
    assert broker_.list_open_orders() == []


def test_replace_order_updates_order_and_recalculates_reservation() -> None:
    broker_ = broker()
    order = broker_.submit_order(
        order_request(
            "client-9",
            order_type=OrderType.LIMIT,
            qty="10",
            limit_price="99",
        )
    )

    replaced = broker_.replace_order(
        order.order_id,
        ReplaceOrderRequest(qty=Decimal("5"), limit_price=Decimal("98")),
    )

    assert replaced.status is OrderStatus.NEW
    assert replaced.qty == Decimal("5")
    assert replaced.remaining_qty == Decimal("5")
    assert replaced.limit_price == Decimal("98")
    assert broker_.get_account().reserved_buying_power == Decimal("490")


def test_rejected_order_is_recorded_without_cash_or_position_mutation() -> None:
    broker_ = broker(initial_cash="100")

    rejected = broker_.submit_order(order_request("client-10", qty="10"))

    assert rejected.status is OrderStatus.REJECTED
    assert rejected.reject_reason == "insufficient buying power"
    assert broker_.get_account().cash == Decimal("100")
    assert broker_.get_position("AAPL").qty == Decimal("0")


def test_commission_is_applied_to_cash_and_realized_pnl() -> None:
    broker_ = broker(
        fill_model=DefaultBacktestFillModel(
            commission_model=FixedPerShareCommission(Decimal("0.01"))
        )
    )

    broker_.submit_order(order_request("client-11", qty="10"))
    broker_.process_market_event(bar_event(1, open_="100"))

    assert broker_.get_account().cash == Decimal("8999.90")
