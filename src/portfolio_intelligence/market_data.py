"""Provider-independent market-data contracts and deterministic local fixtures."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol


class MarketDataProviderError(RuntimeError):
    """Raised when an external provider cannot return usable market data."""


@dataclass(frozen=True, slots=True, order=True)
class PricePoint:
    """A security's adjusted closing price for one trading date."""

    date: date
    adjusted_close: float

    def __post_init__(self) -> None:
        if self.adjusted_close <= 0:
            raise ValueError("Adjusted close must be greater than zero")


@dataclass(frozen=True, slots=True)
class PriceSeries:
    """A validated, chronological series of adjusted closing prices."""

    ticker: str
    points: tuple[PricePoint, ...]

    def __post_init__(self) -> None:
        normalized_ticker = self.ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker cannot be empty")
        if len(self.points) < 2:
            raise ValueError("Price series must contain at least two points")

        dates = [point.date for point in self.points]
        if dates != sorted(dates):
            raise ValueError("Price points must be in chronological order")
        if len(dates) != len(set(dates)):
            raise ValueError("Price series cannot contain duplicate dates")
        object.__setattr__(self, "ticker", normalized_ticker)


class MarketDataProvider(Protocol):
    """Contract implemented by any market-data source."""

    def get_daily_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        """Return adjusted daily closes in the inclusive date range."""


class InMemoryMarketDataProvider:
    """Deterministic provider for tests, demos and offline development."""

    def __init__(self, series_by_ticker: Mapping[str, PriceSeries]) -> None:
        self._series = {
            ticker.strip().upper(): series for ticker, series in series_by_ticker.items()
        }

    def get_daily_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        if start > end:
            raise ValueError("Start date must not be after end date")

        normalized_ticker = ticker.strip().upper()
        try:
            source = self._series[normalized_ticker]
        except KeyError as error:
            raise LookupError(f"No market data configured for {normalized_ticker}") from error

        points = tuple(point for point in source.points if start <= point.date <= end)
        if len(points) < 2:
            raise ValueError(
                f"Date range must contain at least two prices for {normalized_ticker}"
            )
        return PriceSeries(ticker=normalized_ticker, points=points)
