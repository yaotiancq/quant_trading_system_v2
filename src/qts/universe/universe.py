"""Universe interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from qts.core.models import Instrument


class Universe(ABC):
    """Abstract instrument universe."""

    @abstractmethod
    def get_instruments(self, timestamp: datetime) -> list[Instrument]:
        """Return universe members for a timestamp."""

