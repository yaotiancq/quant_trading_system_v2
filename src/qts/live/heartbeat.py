"""Heartbeat monitoring."""

from __future__ import annotations

from qts.brokers.base import Broker
from qts.core.enums import HealthState


class BrokerHeartbeatMonitor:
    """Check broker health through the broker interface."""

    def __init__(self, broker: Broker) -> None:
        self.broker = broker

    def is_healthy(self) -> bool:
        return self.broker.health_check().status is HealthState.OK
