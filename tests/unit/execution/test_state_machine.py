import pytest

from qts.core.enums import OrderStatus
from qts.core.errors import ValidationError
from qts.execution.state_machine import validate_order_transition


def test_order_state_machine_rejects_invalid_transition() -> None:
    with pytest.raises(ValidationError, match="invalid order transition"):
        validate_order_transition(OrderStatus.FILLED, OrderStatus.NEW)


def test_order_state_machine_allows_expected_submit_flow() -> None:
    validate_order_transition(OrderStatus.CREATED, OrderStatus.SUBMITTED)
    validate_order_transition(OrderStatus.SUBMITTED, OrderStatus.ACCEPTED)
    validate_order_transition(OrderStatus.ACCEPTED, OrderStatus.NEW)

