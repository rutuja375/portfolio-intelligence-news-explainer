"""Small manual smoke check for the optional yfinance adapter."""

from datetime import date, timedelta

from portfolio_intelligence import YFinanceMarketDataProvider, calculate_daily_returns


def main() -> None:
    end = date.today()
    start = end - timedelta(days=45)
    series = YFinanceMarketDataProvider().get_daily_prices("NVDA", start, end)
    latest_return = calculate_daily_returns(series)[-1]
    print(f"Ticker: {series.ticker}")
    print(f"Observations: {len(series.points)}")
    print(f"Latest date: {latest_return.date.isoformat()}")
    print(f"Latest return: {latest_return.value:+.2%}")


if __name__ == "__main__":
    main()
