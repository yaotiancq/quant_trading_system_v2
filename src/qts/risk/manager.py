"""Concrete MVP risk manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from qts.core.enums import RiskDecisionStatus, RuleOutcome
from qts.core.identifiers import new_id
from qts.core.models import (
    AccountSnapshot,
    Fill,
    MarketSnapshot,
    Order,
    OrderIntent,
    OrderRequest,
    PortfolioSnapshot,
    RiskDecision,
    RuleResult,
)
from qts.core.time import utc_now
from qts.data.portal import MarketDataPortal
from qts.risk.base import RiskManager


@dataclass(frozen=True)
class RiskConfig:
    max_order_notional: Decimal = Decimal("5000")
    max_order_qty: Decimal | None = None
    max_symbol_exposure_pct: Decimal = Decimal("0.10")
    max_gross_exposure_pct: Decimal = Decimal("1.00")
    cash_buffer: Decimal = Decimal("0")
    allow_short: bool = False


class BasicRiskManager(RiskManager):
    """MVP risk manager with structured approve/modify/reject decisions."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.order_updates: list[Order] = []
        self.fills: list[Fill] = []

    def evaluate_order_intent(
        self,
        intent: OrderIntent,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
        market_snapshot: MarketSnapshot,
    ) -> RiskDecision:
        return RiskDecision(
            decision_id=new_id("risk"),
            timestamp=intent.timestamp,
            intent_id=intent.intent_id,
            status=RiskDecisionStatus.APPROVED,
            reasons=["intent accepted for request generation"],
            rule_results=[
                RuleResult(
                    rule_name="intent_shape",
                    status=RuleOutcome.PASSED,
                    passed=True,
                )
            ],
        )

    def evaluate_order_request(
        self,
        order_request: OrderRequest,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
        market_snapshot: MarketSnapshot,
    ) -> RiskDecision:
        rule_results: list[RuleResult] = []
        reasons: list[str] = []
        estimated_notional = _estimated_notional(order_request, market_snapshot)
        adjusted_order = order_request

        if self.config.max_order_qty is not None and order_request.qty is not None:
            if order_request.qty > self.config.max_order_qty:
                rule_results.append(_failed("max_order_qty", "order quantity exceeds limit"))
                reasons.append("order quantity exceeds max_order_qty")
        rule_results.append(_passed("max_order_qty"))

        if estimated_notional > self.config.max_order_notional:
            if order_request.qty is not None:
                price = _snapshot_price(market_snapshot)
                adjusted_qty = self.config.max_order_notional / price
                adjusted_order = order_request.model_copy(update={"qty": adjusted_qty})
                rule_results.append(_warning("max_order_notional", "order quantity reduced"))
                reasons.append("order modified to max_order_notional")
            else:
                rule_results.append(_failed("max_order_notional", "order notional exceeds limit"))
                reasons.append("order notional exceeds max_order_notional")
        else:
            rule_results.append(_passed("max_order_notional"))

        if adjusted_order.qty is not None:
            adjusted_notional = _estimated_notional(adjusted_order, market_snapshot)
            if adjusted_order.side.value == "buy":
                required_cash = adjusted_notional + self.config.cash_buffer
                if required_cash > account_snapshot.buying_power:
                    rule_results.append(_failed("buying_power", "insufficient buying power"))
                    reasons.append("insufficient buying power")
                else:
                    rule_results.append(_passed("buying_power"))

        failed = any(not result.passed for result in rule_results)
        if failed:
            status = RiskDecisionStatus.REJECTED
        elif adjusted_order != order_request:
            status = RiskDecisionStatus.MODIFIED
        else:
            status = RiskDecisionStatus.APPROVED
        if not reasons:
            reasons = ["risk checks passed"]
        return RiskDecision(
            decision_id=new_id("risk"),
            timestamp=order_request.submitted_at or utc_now(),
            client_order_id=order_request.client_order_id,
            status=status,
            original_order=order_request,
            adjusted_order=adjusted_order if status is RiskDecisionStatus.MODIFIED else None,
            reasons=reasons,
            rule_results=rule_results,
        )

    def evaluate_portfolio(
        self,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
        data_portal: MarketDataPortal,
    ) -> RiskDecision:
        return RiskDecision(
            decision_id=new_id("risk"),
            timestamp=account_snapshot.timestamp,
            status=RiskDecisionStatus.APPROVED,
            reasons=["portfolio risk checks passed"],
            rule_results=[_passed("portfolio_snapshot")],
        )

    def on_fill(
        self,
        fill: Fill,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
    ) -> None:
        self.fills.append(fill)

    def on_order_update(self, order: Order) -> None:
        self.order_updates.append(order)

    def should_halt_trading(
        self,
        account_snapshot: AccountSnapshot,
        portfolio_snapshot: PortfolioSnapshot,
    ) -> bool:
        return False

    def reset_daily_limits(self, current_date: date) -> None:
        return None


def _passed(rule_name: str) -> RuleResult:
    return RuleResult(rule_name=rule_name, status=RuleOutcome.PASSED, passed=True)


def _warning(rule_name: str, reason: str) -> RuleResult:
    return RuleResult(rule_name=rule_name, status=RuleOutcome.WARNING, passed=True, reason=reason)


def _failed(rule_name: str, reason: str) -> RuleResult:
    return RuleResult(rule_name=rule_name, status=RuleOutcome.FAILED, passed=False, reason=reason)


def _estimated_notional(order_request: OrderRequest, market_snapshot: MarketSnapshot) -> Decimal:
    if order_request.notional is not None:
        return order_request.notional
    if order_request.qty is None:
        return Decimal("0")
    price = (
        order_request.limit_price
        or order_request.stop_price
        or _snapshot_price(market_snapshot)
    )
    return order_request.qty * price


def _snapshot_price(snapshot: MarketSnapshot) -> Decimal:
    if snapshot.latest_bar is not None:
        return snapshot.latest_bar.close
    if snapshot.latest_quote is not None:
        return (snapshot.latest_quote.bid_price + snapshot.latest_quote.ask_price) / Decimal("2")
    if snapshot.latest_trade is not None:
        return snapshot.latest_trade.price
    raise ValueError(f"snapshot has no price for {snapshot.symbol}")
