"""Identifier helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create a stable, human-readable unique identifier."""

    normalized = prefix.strip().lower().replace("_", "-")
    return f"{normalized}-{uuid4().hex}"


def make_client_order_id(
    strategy_id: str,
    timestamp: datetime,
    nonce: str | None = None,
    max_length: int = 48,
) -> str:
    """Create a compact client order id suitable for broker idempotency keys."""

    stamp = timestamp.strftime("%Y%m%d%H%M%S")
    suffix = nonce or uuid4().hex[:8]
    raw = f"qts-{strategy_id}-{stamp}-{suffix}"
    return raw[:max_length]

