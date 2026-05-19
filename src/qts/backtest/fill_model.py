"""Backtest fill model interface and default implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from qts.backtest.commission import CommissionModel, ZeroCommission
from qts.backtest.slippage import NoSlippage, SlippageModel
from qts.core.enums import (
    FillSource,
    LiquidityFlag,
    MarketSession,
    OrderSide,
    OrderStatus,
    OrderType,
)
from qts.core.events import BarEvent, BaseEvent, MarketDataEvent, QuoteEvent, TradeEvent
from qts.core.identifiers import new_id
from qts.core.models import Bar, Fill, FillResult, MarketSnapshot, Order


class FillModel(ABC):
    """Abstract fill model contract for simulated execution."""

    @abstractmethod
    def process_order(
        self,
        order: Order,
        market_event: BaseEvent,
        broker_state: object,
    ) -> FillResult:
        """Process one order against one market event."""

    @abstractmethod
    def process_open_orders(
        self,
        open_orders: list[Order],
        market_event: BaseEvent,
        broker_state: object,
    ) -> list[FillResult]:
        """Process open orders against one market event."""

    @abstractmethod
    def estimate_market_price(self, order: Order, market_snapshot: MarketSnapshot) -> Decimal:
        """Estimate the fill reference price for a market order."""

    @abstractmethod
    def check_trigger(self, order: Order, market_event: BaseEvent) -> bool:
        """Return whether an order trigger condition is met."""

    @abstractmethod
    def calculate_slippage(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
    ) -> Decimal:
        """Calculate slippage for an order."""

    @abstractmethod
    def calculate_commission(self, order: Order, fill_qty: Decimal, fill_price: Decimal) -> Decimal:
        """Calculate commission for a fill."""


class LimitFillPolicy(StrEnum):
    PESSIMISTIC = "pessimistic"
    NEUTRAL = "neutral"
    OPTIMISTIC = "optimistic"


@dataclass(frozen=True)
class FillModelConfig:
    allow_same_event_fill: bool = False
    allow_partial_fill: bool = False
    max_participation_rate: Decimal = Decimal("0.10")
    min_fill_qty: Decimal = Decimal("0")
    limit_fill_policy: LimitFillPolicy = LimitFillPolicy.PESSIMISTIC


class DefaultBacktestFillModel(FillModel):
    """Deterministic bar/quote/trade fill model."""

    def __init__(
        self,
        *,
        slippage_model: SlippageModel | None = None,
        commission_model: CommissionModel | None = None,
        config: FillModelConfig | None = None,
    ) -> None:
        self.slippage_model = slippage_model or NoSlippage()
        self.commission_model = commission_model or ZeroCommission()
        self.config = config or FillModelConfig()

    def process_order(
        self,
        order: Order,
        market_event: BaseEvent,
        broker_state: object,
    ) -> FillResult:
        if order.status not in {OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED}:
            return self._no_fill(order, "order is not open")
        if order.remaining_qty <= Decimal("0"):
            return self._no_fill(order, "order has no remaining quantity")
        if not self.config.allow_same_event_fill and order.submitted_at is not None:
            if market_event.timestamp <= order.submitted_at:
                return self._no_fill(order, "same-event fills are disabled")

        snapshot = snapshot_from_market_event(market_event)
        if order.order_type == OrderType.MARKET:
            return self._fill_market_order(order, snapshot)
        if order.order_type == OrderType.LIMIT:
            return self._fill_limit_order(order, snapshot)
        if order.order_type == OrderType.STOP:
            if not self.check_trigger(order, market_event):
                return self._no_fill(order, "stop trigger not reached")
            return self._fill_market_order(order, snapshot)
        if order.order_type == OrderType.STOP_LIMIT:
            if not self.check_trigger(order, market_event):
                return self._no_fill(order, "stop-limit trigger not reached")
            limit_result = self._fill_limit_order(order, snapshot)
            if not limit_result.fills:
                return self._no_fill(order, "stop-limit triggered but limit not filled")
            return limit_result
        return self._no_fill(order, f"unsupported order type: {order.order_type.value}")

    def process_open_orders(
        self,
        open_orders: list[Order],
        market_event: BaseEvent,
        broker_state: object,
    ) -> list[FillResult]:
        return [
            self.process_order(order, market_event, broker_state)
            for order in open_orders
        ]

    def estimate_market_price(self, order: Order, market_snapshot: MarketSnapshot) -> Decimal:
        quote = market_snapshot.latest_quote
        if quote is not None:
            return quote.ask_price if order.side is OrderSide.BUY else quote.bid_price
        bar = market_snapshot.latest_bar
        if bar is not None:
            return bar.open
        trade = market_snapshot.latest_trade
        if trade is not None:
            return trade.price
        raise ValueError("market snapshot has no price source")

    def check_trigger(self, order: Order, market_event: BaseEvent) -> bool:
        if order.stop_price is None:
            return False
        snapshot = snapshot_from_market_event(market_event)
        if order.side is OrderSide.BUY:
            return _high_price(snapshot) >= order.stop_price
        return _low_price(snapshot) <= order.stop_price

    def calculate_slippage(
        self,
        order: Order,
        reference_price: Decimal,
        market_snapshot: MarketSnapshot,
    ) -> Decimal:
        fill_qty = min(order.remaining_qty, order.qty or order.remaining_qty)
        return self.slippage_model.calculate(order, reference_price, market_snapshot, fill_qty)

    def calculate_commission(self, order: Order, fill_qty: Decimal, fill_price: Decimal) -> Decimal:
        return self.commission_model.calculate(order, fill_qty, fill_price).commission

    def _fill_market_order(self, order: Order, snapshot: MarketSnapshot) -> FillResult:
        reference_price = self.estimate_market_price(order, snapshot)
        fill_qty = self._calculate_fill_qty(order, snapshot)
        if fill_qty <= Decimal("0"):
            return self._no_fill(order, "liquidity below minimum fill quantity")
        slippage = self.slippage_model.calculate(order, reference_price, snapshot, fill_qty)
        fill_price = (
            reference_price + slippage
            if order.side is OrderSide.BUY
            else reference_price - slippage
        )
        return self._build_fill_result(order, snapshot, fill_qty, fill_price, slippage)

    def _fill_limit_order(self, order: Order, snapshot: MarketSnapshot) -> FillResult:
        if order.limit_price is None:
            return self._no_fill(order, "limit price missing")
        reference_price = self._limit_reference_price(order, snapshot)
        if reference_price is None:
            return self._no_fill(order, "limit price not reached")
        fill_qty = self._calculate_fill_qty(order, snapshot)
        if fill_qty <= Decimal("0"):
            return self._no_fill(order, "liquidity below minimum fill quantity")
        return self._build_fill_result(order, snapshot, fill_qty, reference_price, Decimal("0"))

    def _limit_reference_price(self, order: Order, snapshot: MarketSnapshot) -> Decimal | None:
        if order.limit_price is None:
            return None
        quote = snapshot.latest_quote
        if quote is not None:
            if order.side is OrderSide.BUY and quote.ask_price <= order.limit_price:
                return min(quote.ask_price, order.limit_price)
            if order.side is OrderSide.SELL and quote.bid_price >= order.limit_price:
                return max(quote.bid_price, order.limit_price)
            return None
        bar = snapshot.latest_bar
        if bar is not None:
            return self._bar_limit_reference_price(order, bar)
        trade = snapshot.latest_trade
        if trade is not None:
            if order.side is OrderSide.BUY and trade.price <= order.limit_price:
                return min(trade.price, order.limit_price)
            if order.side is OrderSide.SELL and trade.price >= order.limit_price:
                return max(trade.price, order.limit_price)
        return None

    def _bar_limit_reference_price(self, order: Order, bar: Bar) -> Decimal | None:
        limit_price = order.limit_price
        if limit_price is None:
            return None
        if order.side is OrderSide.BUY:
            if bar.open <= limit_price:
                return min(bar.open, limit_price)
            if bar.low <= limit_price < bar.open:
                return self._intrabar_limit_price(limit_price)
        else:
            if bar.open >= limit_price:
                return max(bar.open, limit_price)
            if bar.high >= limit_price > bar.open:
                return self._intrabar_limit_price(limit_price)
        return None

    def _intrabar_limit_price(self, limit_price: Decimal) -> Decimal | None:
        if self.config.limit_fill_policy is LimitFillPolicy.PESSIMISTIC:
            return None
        return limit_price

    def _calculate_fill_qty(self, order: Order, snapshot: MarketSnapshot) -> Decimal:
        if not self.config.allow_partial_fill:
            return order.remaining_qty
        bar = snapshot.latest_bar
        if bar is None:
            return order.remaining_qty
        max_fill_qty = bar.volume * self.config.max_participation_rate
        fill_qty = min(order.remaining_qty, max_fill_qty)
        if fill_qty < self.config.min_fill_qty:
            return Decimal("0")
        return fill_qty

    def _build_fill_result(
        self,
        order: Order,
        snapshot: MarketSnapshot,
        fill_qty: Decimal,
        fill_price: Decimal,
        slippage: Decimal,
    ) -> FillResult:
        commission = self.commission_model.calculate(order, fill_qty, fill_price)
        fill = Fill(
            fill_id=new_id("fill"),
            order_id=order.order_id,
            broker_order_id=order.broker_order_id,
            symbol=order.symbol,
            side=order.side,
            qty=fill_qty,
            price=fill_price,
            commission=commission.commission,
            fees=commission.fees,
            slippage=slippage,
            liquidity_flag=LiquidityFlag.TAKER,
            timestamp=snapshot.timestamp,
            source=FillSource.SIMULATED,
        )
        remaining_qty = order.remaining_qty - fill_qty
        status_after_fill = (
            OrderStatus.FILLED
            if remaining_qty <= Decimal("0")
            else OrderStatus.PARTIALLY_FILLED
        )
        return FillResult(
            order_id=order.order_id,
            status_after_fill=status_after_fill,
            fills=[fill],
            remaining_qty=max(remaining_qty, Decimal("0")),
        )

    def _no_fill(self, order: Order, reason: str) -> FillResult:
        return FillResult(
            order_id=order.order_id,
            status_after_fill=order.status,
            fills=[],
            remaining_qty=order.remaining_qty,
            reason=reason,
        )


def snapshot_from_market_event(market_event: BaseEvent) -> MarketSnapshot:
    if isinstance(market_event, MarketDataEvent):
        return market_event.snapshot
    if isinstance(market_event, BarEvent):
        return MarketSnapshot(
            timestamp=market_event.bar.timestamp,
            symbol=market_event.bar.symbol,
            latest_bar=market_event.bar,
            session=MarketSession.REGULAR,
            is_tradable=True,
            source=market_event.source,
        )
    if isinstance(market_event, QuoteEvent):
        return MarketSnapshot(
            timestamp=market_event.quote.timestamp,
            symbol=market_event.quote.symbol,
            latest_quote=market_event.quote,
            session=MarketSession.REGULAR,
            is_tradable=True,
            source=market_event.source,
        )
    if isinstance(market_event, TradeEvent):
        return MarketSnapshot(
            timestamp=market_event.trade.timestamp,
            symbol=market_event.trade.symbol,
            latest_trade=market_event.trade,
            session=MarketSession.REGULAR,
            is_tradable=True,
            source=market_event.source,
        )
    raise ValueError(f"unsupported market event type: {type(market_event).__name__}")


def _high_price(snapshot: MarketSnapshot) -> Decimal:
    bar = snapshot.latest_bar
    if bar is not None:
        return bar.high
    quote = snapshot.latest_quote
    if quote is not None:
        return quote.ask_price
    trade = snapshot.latest_trade
    if trade is not None:
        return trade.price
    raise ValueError("snapshot has no high price source")


def _low_price(snapshot: MarketSnapshot) -> Decimal:
    bar = snapshot.latest_bar
    if bar is not None:
        return bar.low
    quote = snapshot.latest_quote
    if quote is not None:
        return quote.bid_price
    trade = snapshot.latest_trade
    if trade is not None:
        return trade.price
    raise ValueError("snapshot has no low price source")
