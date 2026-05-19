"""Broker capability model."""

from __future__ import annotations

from qts.core.enums import AssetClass, OrderType, TimeInForce
from qts.core.models import QtsModel


class BrokerCapabilities(QtsModel):
    supported_asset_classes: list[AssetClass]
    supported_order_types: list[OrderType]
    supported_time_in_force: list[TimeInForce]
    supports_fractional: bool
    supports_short: bool
    supports_extended_hours: bool
    supports_order_replace: bool
    supports_streaming_order_updates: bool
    max_client_order_id_length: int

