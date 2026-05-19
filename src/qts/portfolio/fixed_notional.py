"""Fixed-notional portfolio construction."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from qts.core.enums import SignalDirection
from qts.core.identifiers import new_id
from qts.core.models import AccountSnapshot, PortfolioSnapshot, Signal, TargetPosition
from qts.portfolio.construction_base import PortfolioConstruction


class FixedNotionalPortfolioConstruction(PortfolioConstruction):
    """Convert directional signals to fixed-notional targets."""

    def __init__(self, default_notional: Decimal) -> None:
        self.default_notional = default_notional

    def build_targets(
        self,
        signals: list[Signal],
        portfolio_snapshot: PortfolioSnapshot,
        market_data: Any,
    ) -> list[TargetPosition]:
        return self.resolve_conflicts(
            [
                TargetPosition(
                    target_id=new_id("target"),
                    strategy_id=signal.strategy_id,
                    symbol=signal.symbol,
                    timestamp=signal.timestamp,
                    target_notional=self._target_notional_for_signal(signal),
                    target_qty=Decimal("0") if signal.direction is SignalDirection.FLAT else None,
                    reason=f"{signal.direction.value} fixed-notional target",
                    source_signal_ids=[signal.signal_id],
                )
                for signal in signals
            ]
        )

    def resolve_conflicts(self, targets: list[TargetPosition]) -> list[TargetPosition]:
        by_symbol: dict[str, TargetPosition] = {}
        for target in targets:
            by_symbol[target.symbol] = target
        return list(by_symbol.values())

    def size_positions(
        self,
        targets: list[TargetPosition],
        account_snapshot: AccountSnapshot,
        risk_budget: Any,
    ) -> list[TargetPosition]:
        return targets

    def _target_notional_for_signal(self, signal: Signal) -> Decimal:
        if signal.direction is SignalDirection.FLAT:
            return Decimal("0")
        if signal.suggested_notional is not None:
            return signal.suggested_notional
        return self.default_notional * Decimal(str(signal.strength))
