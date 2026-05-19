"""Static universe implementation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from qts.core.enums import AssetClass
from qts.core.models import Instrument
from qts.core.time import ensure_timezone_aware
from qts.universe.universe import Universe, UniverseValidationReport


class StaticUniverse(Universe):
    """Fixed list of instruments."""

    def __init__(self, universe_id: str, instruments: list[Instrument]) -> None:
        self.universe_id = universe_id
        self._instruments = list(instruments)

    @classmethod
    def from_symbols(
        cls,
        universe_id: str,
        symbols: list[str],
        *,
        currency: str = "USD",
        timezone: str = "America/New_York",
    ) -> StaticUniverse:
        instruments = [
            Instrument(
                instrument_id=f"US.EQUITY.{symbol}",
                symbol=symbol,
                asset_class=AssetClass.EQUITY,
                currency=currency,
                tradable=True,
                shortable=False,
                fractionable=True,
                min_qty=Decimal("0.0001"),
                qty_increment=Decimal("0.0001"),
                price_increment=Decimal("0.01"),
                timezone=timezone,
            )
            for symbol in symbols
        ]
        return cls(universe_id, instruments)

    def get_instruments(self, timestamp: datetime) -> list[Instrument]:
        ensure_timezone_aware(timestamp)
        return list(self._instruments)

    def validate_universe(self, timestamp: datetime) -> UniverseValidationReport:
        ensure_timezone_aware(timestamp)
        symbols = [instrument.symbol for instrument in self._instruments]
        duplicate_symbols = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
        reasons = [f"duplicate symbol: {symbol}" for symbol in duplicate_symbols]
        return UniverseValidationReport(
            universe_id=self.universe_id,
            timestamp=timestamp,
            valid=not reasons,
            reasons=reasons,
            symbol_count=len(self._instruments),
        )
