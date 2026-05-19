"""Execution engine interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime

from qts.brokers.base import Broker
from qts.core.enums import RiskDecisionStatus
from qts.core.events import FillEvent, OrderEvent
from qts.core.identifiers import make_client_order_id, new_id
from qts.core.models import (
    AccountSnapshot,
    MarketSnapshot,
    Order,
    OrderFilters,
    OrderIntent,
    OrderRequest,
    PortfolioSnapshot,
    ReconciliationReport,
    ReplaceOrderRequest,
    RiskDecision,
)
from qts.core.result import Rejection
from qts.core.time import utc_now
from qts.risk.base import RiskManager


class ExecutionEngine(ABC):
    """Abstract execution engine contract."""

    @abstractmethod
    def submit_order_intent(self, intent: OrderIntent) -> Order | Rejection:
        """Submit an order intent through risk and broker layers."""

    @abstractmethod
    def submit_order_request(self, order_request: OrderRequest) -> Order:
        """Submit a risk-approved order request."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order:
        """Cancel an order."""

    @abstractmethod
    def replace_order(self, order_id: str, new_params: dict[str, object]) -> Order:
        """Replace an order."""

    @abstractmethod
    def reconcile(self) -> ReconciliationReport:
        """Reconcile local execution state with broker state."""

    @abstractmethod
    def handle_order_update(self, order_event: OrderEvent) -> None:
        """Handle an order update."""

    @abstractmethod
    def handle_fill(self, fill_event: FillEvent) -> None:
        """Handle a fill update."""

    @abstractmethod
    def get_open_orders(self, filters: OrderFilters | None = None) -> list[Order]:
        """Return open orders."""


class DefaultExecutionEngine(ExecutionEngine):
    """Risk-aware execution engine that routes all orders through the broker interface."""

    def __init__(
        self,
        *,
        broker: Broker,
        risk_manager: RiskManager,
        market_snapshot_provider: Callable[[str], MarketSnapshot],
        portfolio_snapshot_provider: Callable[[], PortfolioSnapshot],
        environment: str = "bt",
    ) -> None:
        self.broker = broker
        self.risk_manager = risk_manager
        self.market_snapshot_provider = market_snapshot_provider
        self.portfolio_snapshot_provider = portfolio_snapshot_provider
        self.environment = environment
        self.orders: list[Order] = []
        self.rejections: list[Rejection] = []
        self.risk_decisions: list[RiskDecision] = []

    def submit_order_intent(self, intent: OrderIntent) -> Order | Rejection:
        account = self.broker.get_account()
        portfolio = self.portfolio_snapshot_provider()
        market_snapshot = self.market_snapshot_provider(intent.symbol)
        intent_decision = self.risk_manager.evaluate_order_intent(
            intent,
            portfolio,
            account,
            market_snapshot,
        )
        self.risk_decisions.append(intent_decision)
        if intent_decision.status is RiskDecisionStatus.REJECTED:
            rejection = Rejection(
                rejection_id=new_id("rejection"),
                timestamp=intent.timestamp,
                reason="order intent rejected by risk manager",
            )
            self.rejections.append(rejection)
            return rejection
        order_request = self._intent_to_request(intent, account, intent.timestamp)
        request_decision = self.risk_manager.evaluate_order_request(
            order_request,
            portfolio,
            account,
            market_snapshot,
        )
        self.risk_decisions.append(request_decision)
        if request_decision.status is RiskDecisionStatus.REJECTED:
            rejection = Rejection(
                rejection_id=new_id("rejection"),
                timestamp=order_request.submitted_at or utc_now(),
                reason="order request rejected by risk manager",
                order_request=order_request,
                metadata={"reasons": request_decision.reasons},
            )
            self.rejections.append(rejection)
            return rejection
        approved_request = request_decision.adjusted_order or order_request
        return self.submit_order_request(approved_request)

    def submit_order_request(self, order_request: OrderRequest) -> Order:
        order = self.broker.submit_order(order_request)
        self.orders.append(order)
        self.risk_manager.on_order_update(order)
        return order

    def cancel_order(self, order_id: str) -> Order:
        order = self.broker.cancel_order(order_id)
        self.risk_manager.on_order_update(order)
        return order

    def replace_order(self, order_id: str, new_params: dict[str, object]) -> Order:
        order = self.broker.replace_order(order_id, ReplaceOrderRequest.model_validate(new_params))
        self.risk_manager.on_order_update(order)
        return order

    def reconcile(self) -> ReconciliationReport:
        return self.broker.reconcile_state({"orders": self.orders})

    def handle_order_update(self, order_event: OrderEvent) -> None:
        self.risk_manager.on_order_update(order_event.order)

    def handle_fill(self, fill_event: FillEvent) -> None:
        self.risk_manager.on_fill(
            fill_event.fill,
            self.portfolio_snapshot_provider(),
            self.broker.get_account(),
        )

    def get_open_orders(self, filters: OrderFilters | None = None) -> list[Order]:
        if filters is None:
            return self.broker.list_open_orders()
        return self.broker.list_orders(filters.model_copy(update={"open_only": True}))

    def _intent_to_request(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        submitted_at: datetime,
    ) -> OrderRequest:
        client_order_id = make_client_order_id(
            f"{self.environment}-{intent.strategy_id}",
            submitted_at,
        )
        return OrderRequest(
            client_order_id=client_order_id,
            strategy_id=intent.strategy_id,
            account_id=account.account_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            qty=intent.desired_qty,
            notional=intent.desired_notional,
            limit_price=intent.limit_price,
            stop_price=intent.stop_price,
            time_in_force=intent.time_in_force,
            extended_hours=intent.extended_hours,
            submitted_at=submitted_at,
            metadata=dict(intent.metadata),
        )
