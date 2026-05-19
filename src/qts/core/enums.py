"""Shared enumerations used by all runtime modes."""

from enum import StrEnum


class QtsEnum(StrEnum):
    """String enum base with stable JSON values."""

    def __str__(self) -> str:
        return self.value


class AssetClass(QtsEnum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"


class AdjustmentType(QtsEnum):
    RAW = "raw"
    SPLIT = "split"
    DIVIDEND = "dividend"
    ALL = "all"


class MarketSession(QtsEnum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    OVERNIGHT = "overnight"
    CLOSED = "closed"


class SignalDirection(QtsEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalType(QtsEnum):
    RULE_BASED = "rule_based"
    ML_BASED = "ml_based"
    NEWS_BASED = "news_based"
    MANUAL = "manual"
    HYBRID = "hybrid"


class OrderAction(QtsEnum):
    OPEN = "open"
    CLOSE = "close"
    INCREASE = "increase"
    REDUCE = "reduce"
    REBALANCE = "rebalance"


class OrderSide(QtsEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(QtsEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class TimeInForce(QtsEnum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    OPG = "opg"
    CLS = "cls"


class OrderUrgency(QtsEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class OrderStatus(QtsEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    PENDING_CANCEL = "pending_cancel"
    CANCELED = "canceled"
    PENDING_REPLACE = "pending_replace"
    REPLACED = "replaced"
    EXPIRED = "expired"
    DONE_FOR_DAY = "done_for_day"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class LiquidityFlag(QtsEnum):
    MAKER = "maker"
    TAKER = "taker"
    UNKNOWN = "unknown"


class FillSource(QtsEnum):
    SIMULATED = "simulated"
    ALPACA_PAPER = "alpaca_paper"
    ALPACA_LIVE = "alpaca_live"


class PositionSide(QtsEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class AccountStatus(QtsEnum):
    ACTIVE = "active"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class RiskDecisionStatus(QtsEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    WARNING = "warning"


class RuleOutcome(QtsEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


class HealthState(QtsEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class EventType(QtsEnum):
    CLOCK = "clock"
    MARKET_DATA = "market_data"
    BAR = "bar"
    QUOTE = "quote"
    TRADE = "trade"
    SIGNAL = "signal"
    TARGET_POSITION = "target_position"
    ORDER_INTENT = "order_intent"
    RISK_DECISION = "risk_decision"
    ORDER = "order"
    FILL = "fill"
    PORTFOLIO = "portfolio"
    ACCOUNT = "account"
    SYSTEM = "system"
