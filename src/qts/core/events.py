"""Event models for event-driven execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from qts.core.enums import EventType
from qts.core.models import (
    AccountSnapshot,
    Bar,
    Fill,
    MarketSnapshot,
    Order,
    OrderIntent,
    PortfolioSnapshot,
    Position,
    QtsModel,
    Quote,
    RiskDecision,
    Signal,
    TargetPosition,
    Trade,
)


class BaseEvent(QtsModel):
    event_id: str
    event_type: EventType
    timestamp: datetime
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClockEvent(BaseEvent):
    event_type: EventType = EventType.CLOCK


class MarketDataEvent(BaseEvent):
    event_type: EventType = EventType.MARKET_DATA
    snapshot: MarketSnapshot


class BarEvent(BaseEvent):
    event_type: EventType = EventType.BAR
    bar: Bar


class QuoteEvent(BaseEvent):
    event_type: EventType = EventType.QUOTE
    quote: Quote


class TradeEvent(BaseEvent):
    event_type: EventType = EventType.TRADE
    trade: Trade


class SignalEvent(BaseEvent):
    event_type: EventType = EventType.SIGNAL
    signals: list[Signal] = Field(default_factory=list)


class TargetPositionEvent(BaseEvent):
    event_type: EventType = EventType.TARGET_POSITION
    targets: list[TargetPosition] = Field(default_factory=list)


class OrderIntentEvent(BaseEvent):
    event_type: EventType = EventType.ORDER_INTENT
    order_intents: list[OrderIntent] = Field(default_factory=list)


class RiskDecisionEvent(BaseEvent):
    event_type: EventType = EventType.RISK_DECISION
    risk_decisions: list[RiskDecision] = Field(default_factory=list)


class OrderEvent(BaseEvent):
    event_type: EventType = EventType.ORDER
    order: Order


class FillEvent(BaseEvent):
    event_type: EventType = EventType.FILL
    fill: Fill


class PortfolioEvent(BaseEvent):
    event_type: EventType = EventType.PORTFOLIO
    portfolio: PortfolioSnapshot
    positions: list[Position] = Field(default_factory=list)


class AccountEvent(BaseEvent):
    event_type: EventType = EventType.ACCOUNT
    account: AccountSnapshot


class SystemEvent(BaseEvent):
    event_type: EventType = EventType.SYSTEM
    message: str

