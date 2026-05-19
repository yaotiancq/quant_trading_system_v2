"""Risk manager interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from qts.core.models import (
    AccountSnapshot,
    Fill,
    MarketSnapshot,
    Order,
    OrderIntent,
    OrderRequest,
    PortfolioSnapshot,
    RiskDecision,
)
from qts.data.portal import MarketDataPortal


class RiskManager(ABC):
    """Abstract risk manager contract."""

    @abstractmethod
    def evaluate_order_intent(
        self,
        intent: OrderIntent,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
        market_snapshot: MarketSnapshot,
    ) -> RiskDecision:
        """Evaluate an order intent before request creation."""

    @abstractmethod
    def evaluate_order_request(
        self,
        order_request: OrderRequest,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
        market_snapshot: MarketSnapshot,
    ) -> RiskDecision:
        """Evaluate a final broker order request."""

    @abstractmethod
    def evaluate_portfolio(
        self,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
        data_portal: MarketDataPortal,
    ) -> RiskDecision:
        """Evaluate whole-portfolio risk."""

    @abstractmethod
    def on_fill(
        self,
        fill: Fill,
        portfolio_snapshot: PortfolioSnapshot,
        account_snapshot: AccountSnapshot,
    ) -> None:
        """Handle fill updates."""

    @abstractmethod
    def on_order_update(self, order: Order) -> None:
        """Handle broker order updates."""

    @abstractmethod
    def should_halt_trading(
        self,
        account_snapshot: AccountSnapshot,
        portfolio_snapshot: PortfolioSnapshot,
    ) -> bool:
        """Return whether trading should halt."""

    @abstractmethod
    def reset_daily_limits(self, current_date: date) -> None:
        """Reset day-scoped risk state."""

