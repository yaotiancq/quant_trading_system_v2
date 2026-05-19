"""Equal-weight portfolio construction."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from qts.core.enums import SignalDirection
from qts.core.identifiers import new_id
from qts.core.models import AccountSnapshot, PortfolioSnapshot, Signal, TargetPosition
from qts.portfolio.construction_base import PortfolioConstruction


class EqualWeightPortfolioConstruction(PortfolioConstruction):
    """Assign equal target weights to active long signals."""

    def build_targets(
        self,
        signals: list[Signal],
        portfolio_snapshot: PortfolioSnapshot,
        market_data: Any,
    ) -> list[TargetPosition]:
        active = [signal for signal in signals if signal.direction is SignalDirection.LONG]
        if not active:
            return []
        weight = Decimal("1") / Decimal(len(active))
        return [
            TargetPosition(
                target_id=new_id("target"),
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                timestamp=signal.timestamp,
                target_weight=weight,
                reason="equal-weight target",
                source_signal_ids=[signal.signal_id],
            )
            for signal in active
        ]

    def resolve_conflicts(self, targets: list[TargetPosition]) -> list[TargetPosition]:
        return targets

    def size_positions(
        self,
        targets: list[TargetPosition],
        account_snapshot: AccountSnapshot,
        risk_budget: Any,
    ) -> list[TargetPosition]:
        return targets
