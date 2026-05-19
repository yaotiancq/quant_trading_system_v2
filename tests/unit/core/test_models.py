from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from qts.core.enums import (
    AccountStatus,
    AdjustmentType,
    AssetClass,
    OrderSide,
    OrderType,
    PositionSide,
    RiskDecisionStatus,
    RuleOutcome,
    SignalDirection,
    SignalType,
    TimeInForce,
)
from qts.core.models import (
    AccountSnapshot,
    Bar,
    CommissionBreakdown,
    Instrument,
    OrderRequest,
    Position,
    RiskDecision,
    RuleResult,
    Signal,
    TargetPosition,
)


def aware_now() -> datetime:
    return datetime(2024, 1, 2, 14, 30, tzinfo=UTC)


def test_instrument_serializes_to_json_compatible_dict() -> None:
    instrument = Instrument(
        instrument_id="US.EQUITY.AAPL",
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency="USD",
        tradable=True,
        fractionable=True,
        min_qty=Decimal("0.0001"),
        timezone="America/New_York",
    )

    payload = instrument.to_dict()

    assert payload["asset_class"] == "equity"
    assert payload["min_qty"] == "0.0001"
    json.dumps(payload)


def test_bar_rejects_timezone_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Bar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 14, 30),
            timeframe="1m",
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100.5"),
            volume=Decimal("1000"),
            source="fixture",
            adjusted=True,
            adjustment_type=AdjustmentType.ALL,
            is_complete=True,
        )


def test_signal_confidence_and_strength_are_bounded() -> None:
    with pytest.raises(ValidationError):
        Signal(
            signal_id="sig-1",
            strategy_id="strategy-1",
            symbol="AAPL",
            timestamp=aware_now(),
            direction=SignalDirection.LONG,
            strength=1.5,
            confidence=0.5,
            signal_type=SignalType.RULE_BASED,
        )


def test_target_position_requires_a_sizing_field() -> None:
    with pytest.raises(ValidationError, match="at least one target sizing field"):
        TargetPosition(
            target_id="target-1",
            strategy_id="strategy-1",
            symbol="AAPL",
            timestamp=aware_now(),
        )


def test_order_request_requires_exactly_one_qty_or_notional() -> None:
    with pytest.raises(ValidationError, match="exactly one of qty or notional"):
        OrderRequest(
            client_order_id="client-1",
            strategy_id="strategy-1",
            account_id="acct-1",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=Decimal("10"),
            notional=Decimal("1000"),
            time_in_force=TimeInForce.DAY,
            extended_hours=False,
        )


def test_order_request_requires_limit_price_for_limit_order() -> None:
    with pytest.raises(ValidationError, match="limit_price is required"):
        OrderRequest(
            client_order_id="client-1",
            strategy_id="strategy-1",
            account_id="acct-1",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            qty=Decimal("10"),
            time_in_force=TimeInForce.DAY,
            extended_hours=False,
        )


def test_order_request_requires_stop_price_for_stop_order() -> None:
    with pytest.raises(ValidationError, match="stop_price is required"):
        OrderRequest(
            client_order_id="client-1",
            strategy_id="strategy-1",
            account_id="acct-1",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            qty=Decimal("10"),
            time_in_force=TimeInForce.DAY,
            extended_hours=False,
        )


def test_order_request_preserves_decimal_values_on_model() -> None:
    request = OrderRequest(
        client_order_id="client-1",
        strategy_id="strategy-1",
        account_id="acct-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("10.25"),
        time_in_force=TimeInForce.DAY,
        extended_hours=False,
    )

    assert request.qty == Decimal("10.25")
    payload = request.to_dict()
    assert payload["qty"] == "10.25"
    json.dumps(payload)


def test_account_position_and_risk_decision_models_serialize() -> None:
    ts = aware_now()
    position = Position(
        account_id="acct-1",
        symbol="AAPL",
        qty=Decimal("3"),
        avg_entry_price=Decimal("100"),
        cost_basis=Decimal("300"),
        side=PositionSide.LONG,
        updated_at=ts,
    )
    account = AccountSnapshot(
        account_id="acct-1",
        timestamp=ts,
        cash=Decimal("99700"),
        equity=Decimal("100000"),
        buying_power=Decimal("99700"),
        portfolio_value=Decimal("100000"),
        long_market_value=Decimal("300"),
        short_market_value=Decimal("0"),
        reserved_buying_power=Decimal("0"),
        status=AccountStatus.ACTIVE,
    )
    decision = RiskDecision(
        decision_id="risk-1",
        timestamp=ts,
        status=RiskDecisionStatus.APPROVED,
        reasons=["within limits"],
        rule_results=[
            RuleResult(
                rule_name="max_order_notional",
                status=RuleOutcome.PASSED,
                passed=True,
            )
        ],
    )

    payload = {
        "position": position.to_dict(),
        "account": account.to_dict(),
        "decision": decision.to_dict(),
    }

    assert payload["account"]["cash"] == "99700"
    assert payload["decision"]["status"] == "approved"
    json.dumps(payload)


def test_commission_breakdown_defaults_total() -> None:
    breakdown = CommissionBreakdown(commission=Decimal("1.25"), fees=Decimal("0.25"))

    assert breakdown.total == Decimal("1.50")
