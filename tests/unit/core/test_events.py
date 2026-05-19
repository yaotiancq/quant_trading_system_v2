from datetime import UTC, datetime
from decimal import Decimal

from qts.core.enums import AdjustmentType, EventType
from qts.core.events import BarEvent
from qts.core.models import Bar


def test_bar_event_has_stable_event_type_and_serializes() -> None:
    ts = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    bar = Bar(
        symbol="AAPL",
        timestamp=ts,
        timeframe="1m",
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("1000"),
        source="fixture",
        adjusted=True,
        adjustment_type=AdjustmentType.ALL,
        is_complete=True,
    )
    event = BarEvent(event_id="event-1", timestamp=ts, source="fixture", bar=bar)

    assert event.event_type is EventType.BAR
    payload = event.to_dict()
    assert payload["event_type"] == "bar"
    assert payload["bar"]["close"] == "100.5"

