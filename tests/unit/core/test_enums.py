from qts.core.enums import OrderStatus, OrderType, RiskDecisionStatus


def test_required_order_status_values_exist() -> None:
    assert OrderStatus.CREATED.value == "created"
    assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert OrderStatus.UNKNOWN.value == "unknown"


def test_required_order_type_values_exist() -> None:
    assert {item.value for item in OrderType} >= {
        "market",
        "limit",
        "stop",
        "stop_limit",
        "trailing_stop",
    }


def test_risk_decision_status_values_are_structured() -> None:
    assert {item.value for item in RiskDecisionStatus} == {
        "approved",
        "rejected",
        "modified",
        "warning",
    }

