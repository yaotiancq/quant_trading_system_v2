"""Result helper models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from qts.core.models import OrderRequest, QtsModel


class Rejection(QtsModel):
    """Structured rejection result for execution and broker boundaries."""

    rejection_id: str
    timestamp: datetime
    reason: str
    order_request: OrderRequest | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

