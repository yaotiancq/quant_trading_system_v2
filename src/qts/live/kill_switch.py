"""Live trading kill switch."""

from __future__ import annotations

from datetime import datetime

from qts.core.time import utc_now


class KillSwitch:
    """Manual/system kill switch that blocks new orders when engaged."""

    def __init__(self) -> None:
        self.enabled = False
        self.reason: str | None = None
        self.engaged_at: datetime | None = None

    def engage(self, reason: str) -> None:
        self.enabled = True
        self.reason = reason
        self.engaged_at = utc_now()

    def release(self) -> None:
        self.enabled = False
        self.reason = None
        self.engaged_at = None

    def can_submit_orders(self) -> bool:
        return not self.enabled
