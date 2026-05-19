"""Universe interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import Field

from qts.core.models import Instrument, QtsModel


class UniverseValidationReport(QtsModel):
    universe_id: str
    timestamp: datetime
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    symbol_count: int = 0


class Universe(ABC):
    """Abstract instrument universe."""

    universe_id: str

    @abstractmethod
    def get_instruments(self, timestamp: datetime) -> list[Instrument]:
        """Return universe members for a timestamp."""

    @abstractmethod
    def validate_universe(self, timestamp: datetime) -> UniverseValidationReport:
        """Validate universe membership for a timestamp."""
