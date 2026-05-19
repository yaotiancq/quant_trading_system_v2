"""Portfolio construction interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
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


class SignalWeightedPortfolioConstruction(PortfolioConstruction):
    """Convert suggested signal weights into target weights."""

    def build_targets(
        self,
        signals: list[Signal],
        portfolio_snapshot: PortfolioSnapshot,
        market_data: Any,
    ) -> list[TargetPosition]:
        from qts.core.enums import SignalDirection
        from qts.core.identifiers import new_id

        targets = []
        for signal in signals:
            if signal.direction is SignalDirection.FLAT:
                targets.append(
                    TargetPosition(
                        target_id=new_id("target"),
                        strategy_id=signal.strategy_id,
                        symbol=signal.symbol,
                        timestamp=signal.timestamp,
                        target_qty=Decimal("0"),
                        reason="flat signal",
                        source_signal_ids=[signal.signal_id],
                    )
                )
                continue
            if signal.suggested_weight is not None:
                targets.append(
                    TargetPosition(
                        target_id=new_id("target"),
                        strategy_id=signal.strategy_id,
                        symbol=signal.symbol,
                        timestamp=signal.timestamp,
                        target_weight=signal.suggested_weight,
                        reason="signal-weighted target",
                        source_signal_ids=[signal.signal_id],
                    )
                )
        return targets

    def resolve_conflicts(self, targets: list[TargetPosition]) -> list[TargetPosition]:
        return targets

    def size_positions(
        self,
        targets: list[TargetPosition],
        account_snapshot: AccountSnapshot,
        risk_budget: Any,
    ) -> list[TargetPosition]:
        return targets
