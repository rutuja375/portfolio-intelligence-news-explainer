"""Deterministic portfolio-attribution calculations."""

from collections.abc import Mapping

from .models import HoldingPerformance, PortfolioAttribution, PortfolioSnapshot


def calculate_attribution(
    portfolio: PortfolioSnapshot,
    period_returns: Mapping[str, float],
) -> PortfolioAttribution:
    """Calculate weighted portfolio return and each holding's contribution.

    Returns use decimal representation: ``-0.052`` means ``-5.2%``.
    Every portfolio holding must have a corresponding period return.
    """

    normalized_returns = {ticker.strip().upper(): value for ticker, value in period_returns.items()}
    missing = sorted(
        holding.ticker for holding in portfolio.holdings if holding.ticker not in normalized_returns
    )
    if missing:
        raise ValueError(f"Missing period returns for: {', '.join(missing)}")

    results = tuple(
        HoldingPerformance(
            ticker=holding.ticker,
            weight=holding.weight,
            period_return=normalized_returns[holding.ticker],
            contribution=holding.weight * normalized_returns[holding.ticker],
        )
        for holding in portfolio.holdings
    )
    return PortfolioAttribution(
        portfolio_return=sum(item.contribution for item in results),
        holdings=results,
    )
