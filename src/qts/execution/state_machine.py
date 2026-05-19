"""Order lifecycle state machine."""

from __future__ import annotations

from qts.core.enums import OrderStatus
from qts.core.errors import ValidationError

VALID_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.SUBMITTED, OrderStatus.REJECTED},
    OrderStatus.SUBMITTED: {OrderStatus.ACCEPTED, OrderStatus.REJECTED},
    OrderStatus.ACCEPTED: {OrderStatus.NEW, OrderStatus.REJECTED},
    OrderStatus.NEW: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.PENDING_REPLACE,
        OrderStatus.DONE_FOR_DAY,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.FILLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PENDING_CANCEL: {OrderStatus.CANCELED},
    OrderStatus.PENDING_REPLACE: {OrderStatus.REPLACED},
    OrderStatus.REPLACED: {OrderStatus.NEW},
    OrderStatus.DONE_FOR_DAY: {OrderStatus.NEW, OrderStatus.EXPIRED, OrderStatus.CANCELED},
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELED: set(),
    OrderStatus.EXPIRED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.SUSPENDED: {OrderStatus.NEW, OrderStatus.CANCELED},
    OrderStatus.UNKNOWN: set(OrderStatus),
}


TERMINAL_ORDER_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}


def validate_order_transition(current: OrderStatus, target: OrderStatus) -> None:
    """Raise if an order status transition is not allowed."""

    if target == current:
        return
    allowed = VALID_ORDER_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValidationError(f"invalid order transition: {current.value} -> {target.value}")


def is_terminal_status(status: OrderStatus) -> bool:
    """Return whether an order status is terminal."""

    return status in TERMINAL_ORDER_STATUSES
