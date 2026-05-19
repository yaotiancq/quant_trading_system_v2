"""Performance metric calculation."""

from __future__ import annotations

from decimal import Decimal
from statistics import mean, pstdev

from qts.core.models import AccountSnapshot, Fill, Order, QtsModel


class PerformanceSummary(QtsModel):
    total_return: Decimal
    annualized_return: Decimal
    volatility: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    max_drawdown: Decimal
    calmar_ratio: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    average_trade_return: Decimal
    median_trade_return: Decimal
    turnover: Decimal
    exposure_time: Decimal
    average_slippage: Decimal
    total_commission: Decimal
    rejected_order_count: int
    fill_rate: Decimal
    partial_fill_rate: Decimal


class PerformanceEngine:
    """Compute deterministic summary metrics from standardized artifacts."""

    def summarize(
        self,
        *,
        account_snapshots: list[AccountSnapshot],
        orders: list[Order],
        fills: list[Fill],
        initial_cash: Decimal,
    ) -> PerformanceSummary:
        final_value = account_snapshots[-1].portfolio_value if account_snapshots else initial_cash
        total_return = (final_value - initial_cash) / initial_cash if initial_cash else Decimal("0")
        returns = _equity_returns(account_snapshots)
        volatility = Decimal(str(pstdev(returns))) if len(returns) > 1 else Decimal("0")
        average_return = Decimal(str(mean(returns))) if returns else Decimal("0")
        sharpe = average_return / volatility if volatility != Decimal("0") else Decimal("0")
        max_drawdown = _max_drawdown(account_snapshots)
        total_commission = sum((fill.commission + fill.fees for fill in fills), Decimal("0"))
        filled_orders = [order for order in orders if order.filled_qty > Decimal("0")]
        partial_orders = [
            order
            for order in orders
            if order.filled_qty > Decimal("0") and order.remaining_qty > Decimal("0")
        ]
        total_orders = len(orders)
        fill_rate = (
            Decimal(len(filled_orders)) / Decimal(total_orders)
            if total_orders
            else Decimal("0")
        )
        partial_fill_rate = (
            Decimal(len(partial_orders)) / Decimal(total_orders) if total_orders else Decimal("0")
        )
        average_slippage = _average_slippage(fills)
        turnover = sum((fill.qty * fill.price for fill in fills), Decimal("0")) / initial_cash
        rejected_order_count = sum(1 for order in orders if order.status.value == "rejected")
        return PerformanceSummary(
            total_return=total_return,
            annualized_return=total_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sharpe,
            max_drawdown=max_drawdown,
            calmar_ratio=total_return / max_drawdown.copy_abs()
            if max_drawdown != Decimal("0")
            else Decimal("0"),
            win_rate=Decimal("0"),
            profit_factor=Decimal("0"),
            average_trade_return=Decimal("0"),
            median_trade_return=Decimal("0"),
            turnover=turnover,
            exposure_time=Decimal("0"),
            average_slippage=average_slippage,
            total_commission=total_commission,
            rejected_order_count=rejected_order_count,
            fill_rate=fill_rate,
            partial_fill_rate=partial_fill_rate,
        )


def _equity_returns(account_snapshots: list[AccountSnapshot]) -> list[float]:
    returns = []
    for previous, current in zip(account_snapshots, account_snapshots[1:], strict=False):
        if previous.portfolio_value == Decimal("0"):
            continue
        returns.append(
            float((current.portfolio_value - previous.portfolio_value) / previous.portfolio_value)
        )
    return returns


def _max_drawdown(account_snapshots: list[AccountSnapshot]) -> Decimal:
    peak: Decimal | None = None
    max_drawdown = Decimal("0")
    for snapshot in account_snapshots:
        value = snapshot.portfolio_value
        if peak is None or value > peak:
            peak = value
        if peak and peak != Decimal("0"):
            drawdown = (value - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
    return max_drawdown


def _average_slippage(fills: list[Fill]) -> Decimal:
    values = [fill.slippage for fill in fills if fill.slippage is not None]
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))
