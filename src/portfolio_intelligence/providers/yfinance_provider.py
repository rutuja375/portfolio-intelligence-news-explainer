"""yfinance adapter for adjusted daily prices in development and demos."""

from collections.abc import Callable
from datetime import date, timedelta
from math import isfinite
from typing import Any

from ..market_data import MarketDataProviderError, PricePoint, PriceSeries


class YFinanceMarketDataProvider:
    """Retrieve auto-adjusted daily closes through the yfinance package.

    yfinance is an unofficial research/educational client for Yahoo Finance.
    This adapter is suitable for local demonstrations, not production market
    data or investment decision-making.
    """

    def __init__(
        self,
        download: Callable[..., Any] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if download is None:
            try:
                import yfinance as yf
            except ImportError as error:
                raise RuntimeError(
                    'yfinance is not installed; install the live extra with '
                    '`python -m pip install -e ".[live]"`'
                ) from error
            download = yf.download
        self._download = download
        self._timeout_seconds = timeout_seconds

    def get_daily_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        if start > end:
            raise ValueError("Start date must not be after end date")
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker cannot be empty")

        try:
            frame = self._download(
                normalized_ticker,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=True,
                repair=False,
                progress=False,
                threads=False,
                timeout=self._timeout_seconds,
                multi_level_index=False,
            )
        except Exception as error:
            raise MarketDataProviderError(
                f"yfinance request failed for {normalized_ticker}"
            ) from error

        if frame is None or getattr(frame, "empty", True):
            raise LookupError(f"yfinance returned no prices for {normalized_ticker}")
        try:
            close_values = frame["Close"]
        except (KeyError, TypeError) as error:
            raise MarketDataProviderError(
                f"yfinance response for {normalized_ticker} did not contain Close prices"
            ) from error

        points = []
        for index, raw_value in close_values.items():
            price_date = index.date() if hasattr(index, "date") else date.fromisoformat(str(index))
            if not start <= price_date <= end:
                continue
            try:
                adjusted_close = float(raw_value)
            except (TypeError, ValueError) as error:
                raise MarketDataProviderError(
                    f"yfinance returned a non-numeric close for {normalized_ticker} on {price_date}"
                ) from error
            if not isfinite(adjusted_close) or adjusted_close <= 0:
                raise MarketDataProviderError(
                    f"yfinance returned an invalid close for {normalized_ticker} on {price_date}"
                )
            points.append(PricePoint(price_date, adjusted_close))

        points.sort(key=lambda point: point.date)
        if len(points) < 2:
            raise LookupError(
                f"yfinance returned fewer than two usable prices for {normalized_ticker}"
            )
        return PriceSeries(ticker=normalized_ticker, points=tuple(points))
