"""Portfolio construction interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from qts.core.models import AccountSnapshot, PortfolioSnapshot, Signal, TargetPosition


class PortfolioConstruction(ABC):
    """Abstract signal-to-target conversion contract."""

    @abstractmethod
    def build_targets(
        self,
        signals: list[Signal],
        portfolio_snapshot: PortfolioSnapshot,
        market_data: Any,
    ) -> list[TargetPosition]:
        """Build target positions from signals."""

    @abstractmethod
    def resolve_conflicts(self, targets: list[TargetPosition]) -> list[TargetPosition]:
        """Resolve conflicting targets."""

    @abstractmethod
    def size_positions(
        self,
        targets: list[TargetPosition],
        account_snapshot: AccountSnapshot,
        risk_budget: Any,
    ) -> list[TargetPosition]:
        """Apply sizing rules to targets."""

