"""Broker reconciliation service."""

from __future__ import annotations

from qts.brokers.base import Broker
from qts.core.models import Position, ReconciliationReport


class ReconciliationService:
    """Compare local state against broker state through the broker interface."""

    def __init__(self, broker: Broker) -> None:
        self.broker = broker

    def reconcile_positions(self, local_positions: list[Position]) -> ReconciliationReport:
        return self.broker.reconcile_state({"positions": local_positions})
