"""Typed domain models for deterministic portfolio analytics."""

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True, slots=True)
class Holding:
    """A security and its normalized portfolio weight."""

    ticker: str
    weight: float

    def __post_init__(self) -> None:
        normalized_ticker = self.ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker cannot be empty")
        if not 0 <= self.weight <= 1:
            raise ValueError("Holding weight must be between 0 and 1")
        object.__setattr__(self, "ticker", normalized_ticker)


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """A fully invested portfolio at a point in time."""

    holdings: tuple[Holding, ...]

    def __post_init__(self) -> None:
        if not self.holdings:
            raise ValueError("Portfolio must contain at least one holding")
        tickers = [holding.ticker for holding in self.holdings]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Portfolio cannot contain duplicate tickers")
        total_weight = sum(holding.weight for holding in self.holdings)
        if not isclose(total_weight, 1.0, abs_tol=1e-9):
            raise ValueError(f"Portfolio weights must sum to 1.0; received {total_weight:.6f}")


@dataclass(frozen=True, slots=True)
class HoldingPerformance:
    """Period performance and contribution for one holding."""

    ticker: str
    weight: float
    period_return: float
    contribution: float


@dataclass(frozen=True, slots=True)
class PortfolioAttribution:
    """Portfolio-level return and security-level contribution detail."""

    portfolio_return: float
    holdings: tuple[HoldingPerformance, ...]

    @property
    def contributors_by_impact(self) -> tuple[HoldingPerformance, ...]:
        """Return holdings ordered by absolute contribution, largest first."""

        return tuple(sorted(self.holdings, key=lambda item: abs(item.contribution), reverse=True))
