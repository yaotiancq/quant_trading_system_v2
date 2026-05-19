"""Live safety and safe-mode services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from qts.core.models import HealthStatus, ReconciliationReport
from qts.core.time import ensure_timezone_aware, utc_now
from qts.live.kill_switch import KillSwitch


@dataclass(frozen=True)
class LiveSafetyConfig:
    data_staleness_limit_seconds: int = 5
    safe_mode_on_reconciliation_mismatch: bool = True
    kill_switch_enabled: bool = True
    dry_run: bool = False


class LiveSafetyService:
    """Central live safety state machine."""

    def __init__(
        self,
        config: LiveSafetyConfig | None = None,
        *,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.config = config or LiveSafetyConfig()
        self.kill_switch = kill_switch or KillSwitch()
        self.safe_mode = False
        self.safe_mode_reason: str | None = None
        self.audit_events: list[dict[str, Any]] = []

    def can_submit_orders(self) -> bool:
        if self.config.dry_run:
            return False
        if self.config.kill_switch_enabled and not self.kill_switch.can_submit_orders():
            return False
        return not self.safe_mode

    def enter_safe_mode(self, reason: str) -> None:
        self.safe_mode = True
        self.safe_mode_reason = reason
        self.audit("safe_mode_entered", {"reason": reason})

    def exit_safe_mode(self) -> None:
        self.audit("safe_mode_exited", {"reason": self.safe_mode_reason})
        self.safe_mode = False
        self.safe_mode_reason = None

    def check_data_freshness(
        self,
        latest_data_timestamp: datetime,
        now: datetime | None = None,
    ) -> bool:
        latest = ensure_timezone_aware(latest_data_timestamp)
        current = ensure_timezone_aware(now or utc_now())
        stale_seconds = (current - latest).total_seconds()
        if stale_seconds > self.config.data_staleness_limit_seconds:
            self.enter_safe_mode(f"data stale for {stale_seconds:.0f}s")
            return False
        self.audit("data_freshness_ok", {"stale_seconds": stale_seconds})
        return True

    def check_broker_health(self, health: HealthStatus) -> bool:
        if health.status.value != "ok":
            self.enter_safe_mode(f"broker health {health.status.value}")
            return False
        self.audit("broker_health_ok", {"status": health.status.value})
        return True

    def handle_reconciliation(self, report: ReconciliationReport) -> bool:
        if not report.matched and self.config.safe_mode_on_reconciliation_mismatch:
            self.enter_safe_mode("reconciliation mismatch")
            return False
        self.audit("reconciliation_ok", {"matched": report.matched})
        return True

    def engage_kill_switch(self, reason: str) -> None:
        self.kill_switch.engage(reason)
        self.audit("kill_switch_engaged", {"reason": reason})

    def audit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.audit_events.append(
            {
                "timestamp": utc_now().isoformat(),
                "event_type": event_type,
                "payload": sanitize_audit_payload(payload),
            }
        )


def sanitize_audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    for key, value in payload.items():
        secret_words = ("secret", "token", "key", "password")
        if any(secret_word in key.lower() for secret_word in secret_words):
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized
