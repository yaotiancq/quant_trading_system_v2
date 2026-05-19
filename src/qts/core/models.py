"""Pydantic domain models shared across runtime modes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qts.core.enums import (
    AccountStatus,
    AdjustmentType,
    AssetClass,
    FillSource,
    HealthState,
    LiquidityFlag,
    MarketSession,
    OrderAction,
    OrderSide,
    OrderStatus,
    OrderType,
    OrderUrgency,
    PositionSide,
    RiskDecisionStatus,
    RuleOutcome,
    SignalDirection,
    SignalType,
    TimeInForce,
)
from qts.core.time import ensure_timezone_aware


class QtsModel(BaseModel):
    """Base model with strict fields and JSON-compatible dump helper."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=False,
    )

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def _require_timezone_aware_datetimes(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return ensure_timezone_aware(value)
        return value

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""

        return self.model_dump(mode="json")


class Instrument(QtsModel):
    instrument_id: str
    symbol: str
    asset_class: AssetClass
    currency: str
    tradable: bool
    timezone: str
    exchange: str | None = None
    shortable: bool | None = None
    fractionable: bool | None = None
    min_qty: Decimal | None = None
    qty_increment: Decimal | None = None
    price_increment: Decimal | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Bar(QtsModel):
    symbol: str
    timestamp: datetime
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str
    adjusted: bool
    is_complete: bool
    adjustment_type: AdjustmentType | None = None
    vwap: Decimal | None = None
    trade_count: int | None = None
    received_at: datetime | None = None


class Quote(QtsModel):
    symbol: str
    timestamp: datetime
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    source: str
    exchange: str | None = None
    conditions: list[str] = Field(default_factory=list)
    received_at: datetime | None = None


class Trade(QtsModel):
    symbol: str
    timestamp: datetime
    price: Decimal
    size: Decimal
    source: str
    exchange: str | None = None
    conditions: list[str] = Field(default_factory=list)
    trade_id: str | None = None
    received_at: datetime | None = None


class MarketSnapshot(QtsModel):
    timestamp: datetime
    symbol: str
    session: MarketSession
    is_tradable: bool
    source: str
    latest_bar: Bar | None = None
    latest_quote: Quote | None = None
    latest_trade: Trade | None = None
    data_latency_ms: int | None = None


class Signal(QtsModel):
    signal_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    direction: SignalDirection
    strength: float = Field(ge=0.0, le=1.0)
    signal_type: SignalType
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    horizon: str | None = None
    suggested_weight: Decimal | None = None
    suggested_qty: Decimal | None = None
    suggested_notional: Decimal | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TargetPosition(QtsModel):
    target_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    target_qty: Decimal | None = None
    target_weight: Decimal | None = None
    target_notional: Decimal | None = None
    priority: int | None = None
    reason: str | None = None
    source_signal_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_one_target_field(self) -> Self:
        if self.target_qty is None and self.target_weight is None and self.target_notional is None:
            raise ValueError("at least one target sizing field is required")
        return self


class OrderIntent(QtsModel):
    intent_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    action: OrderAction
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    extended_hours: bool
    desired_qty: Decimal | None = None
    desired_notional: Decimal | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    urgency: OrderUrgency | None = None
    source_target_id: str | None = None
    source_signal_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderRequest(QtsModel):
    client_order_id: str
    strategy_id: str
    account_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    extended_hours: bool
    qty: Decimal | None = None
    notional: Decimal | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    trail_price: Decimal | None = None
    trail_percent: Decimal | None = None
    submitted_at: datetime | None = None
    risk_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_order_shape(self) -> Self:
        if (self.qty is None and self.notional is None) or (
            self.qty is not None and self.notional is not None
        ):
            raise ValueError("exactly one of qty or notional must be provided")
        if self.order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT} and self.limit_price is None:
            raise ValueError("limit_price is required for limit and stop_limit orders")
        if self.order_type in {OrderType.STOP, OrderType.STOP_LIMIT} and self.stop_price is None:
            raise ValueError("stop_price is required for stop and stop_limit orders")
        if self.order_type == OrderType.TRAILING_STOP:
            if (self.trail_price is None and self.trail_percent is None) or (
                self.trail_price is not None and self.trail_percent is not None
            ):
                raise ValueError("exactly one trailing stop field must be provided")
        return self


class Order(QtsModel):
    order_id: str
    client_order_id: str
    account_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    filled_qty: Decimal
    remaining_qty: Decimal
    time_in_force: TimeInForce
    extended_hours: bool
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    broker_order_id: str | None = None
    qty: Decimal | None = None
    notional: Decimal | None = None
    avg_fill_price: Decimal | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    canceled_at: datetime | None = None
    rejected_at: datetime | None = None
    reject_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Fill(QtsModel):
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    qty: Decimal
    price: Decimal
    commission: Decimal
    fees: Decimal
    timestamp: datetime
    source: FillSource
    broker_order_id: str | None = None
    slippage: Decimal | None = None
    liquidity_flag: LiquidityFlag | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Position(QtsModel):
    account_id: str
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    cost_basis: Decimal
    side: PositionSide
    updated_at: datetime
    market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None


class AccountSnapshot(QtsModel):
    account_id: str
    timestamp: datetime
    cash: Decimal
    equity: Decimal
    buying_power: Decimal
    portfolio_value: Decimal
    long_market_value: Decimal
    short_market_value: Decimal
    reserved_buying_power: Decimal
    status: AccountStatus
    initial_margin: Decimal | None = None
    maintenance_margin: Decimal | None = None
    daytrade_count: int | None = None
    leverage: Decimal | None = None


class RuleResult(QtsModel):
    rule_name: str
    status: RuleOutcome
    passed: bool
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskDecision(QtsModel):
    decision_id: str
    timestamp: datetime
    status: RiskDecisionStatus
    reasons: list[str]
    rule_results: list[RuleResult]
    intent_id: str | None = None
    client_order_id: str | None = None
    original_order: OrderRequest | None = None
    adjusted_order: OrderRequest | None = None
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)


class HealthStatus(QtsModel):
    status: HealthState
    checked_at: datetime
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SessionTimes(QtsModel):
    session_date: date
    regular_open: datetime
    regular_close: datetime
    pre_market_open: datetime | None = None
    after_hours_close: datetime | None = None


class HistoricalWindow(QtsModel):
    symbol: str
    fields: list[str]
    timeframe: str
    start: datetime
    end: datetime
    bars: list[Bar] = Field(default_factory=list)


class DataAvailabilityReport(QtsModel):
    symbols: list[str]
    start: datetime
    end: datetime
    timeframe: str
    available: bool
    missing_symbols: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FillResult(QtsModel):
    order_id: str
    status_after_fill: OrderStatus
    fills: list[Fill] = Field(default_factory=list)
    remaining_qty: Decimal
    reason: str | None = None
    reserved_buying_power_delta: Decimal = Decimal("0")


class CommissionBreakdown(QtsModel):
    commission: Decimal
    fees: Decimal = Decimal("0")
    total: Decimal | None = None
    currency: str = "USD"

    @model_validator(mode="after")
    def _default_total(self) -> Self:
        if self.total is None:
            self.total = self.commission + self.fees
        return self


class ReconciliationReport(QtsModel):
    timestamp: datetime
    matched: bool
    discrepancies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderFilters(QtsModel):
    symbol: str | None = None
    status: OrderStatus | None = None
    start: datetime | None = None
    end: datetime | None = None
    open_only: bool = False


class ReplaceOrderRequest(QtsModel):
    qty: Decimal | None = None
    notional: Decimal | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortfolioSnapshot(QtsModel):
    account_id: str
    timestamp: datetime
    positions: list[Position] = Field(default_factory=list)
    total_market_value: Decimal = Decimal("0")
    metadata: dict[str, Any] = Field(default_factory=dict)
