"""Strategy context model."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from qts.core.models import QtsModel


class StrategyContext(QtsModel):
    """Read-only strategy runtime context."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    strategy_id: str
    account_id: str
    clock: Any
    data: Any
    portfolio_view: Any
    config: dict[str, Any] = Field(default_factory=dict)
    state_store: Any = None
    logger: Any = None

