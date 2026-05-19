"""Paper/live runner scaffolding."""

from __future__ import annotations

from dataclasses import dataclass

from qts.brokers.base import Broker
from qts.core.models import Order, OrderRequest
from qts.core.result import Rejection
from qts.core.time import utc_now
from qts.risk.live_safety import LiveSafetyService


@dataclass
class PaperTradingRunner:
    """Minimal paper runner holder for Phase 5 wiring."""

    broker: Broker
    dry_run: bool = False

    def health_check(self) -> bool:
        return self.broker.health_check().status.value == "ok"


@dataclass
class LiveTradingRunner:
    """Safety-aware live runner submission facade."""

    broker: Broker
    safety: LiveSafetyService

    def submit_order_request(self, order_request: OrderRequest) -> Order | Rejection:
        if not self.safety.can_submit_orders():
            return Rejection(
                rejection_id=f"live-reject-{utc_now().timestamp()}",
                timestamp=utc_now(),
                reason="live safety blocked order submission",
                order_request=order_request,
            )
        self.safety.audit(
            "live_order_submit",
            {
                "client_order_id": order_request.client_order_id,
                "symbol": order_request.symbol,
            },
        )
        return self.broker.submit_order(order_request)
