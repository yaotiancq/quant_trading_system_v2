"""Execution engine interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from qts.core.events import FillEvent, OrderEvent
from qts.core.models import Order, OrderFilters, OrderIntent, OrderRequest, ReconciliationReport
from qts.core.result import Rejection


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

