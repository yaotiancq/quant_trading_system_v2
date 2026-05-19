"""Shared exception hierarchy."""


class QtsError(Exception):
    """Base exception for QTS errors."""


class ValidationError(QtsError):
    """Raised when domain validation fails outside model construction."""


class UnsupportedOperationError(QtsError):
    """Raised when a requested operation is not supported by a component."""


class BrokerError(QtsError):
    """Raised by broker implementations."""


class DataAccessError(QtsError):
    """Raised by market data components."""


class RiskRejectedError(QtsError):
    """Raised when risk checks reject a request."""

