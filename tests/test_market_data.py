import unittest
from datetime import date

from portfolio_intelligence import InMemoryMarketDataProvider, PricePoint, PriceSeries


class MarketDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.series = PriceSeries(
            ticker="nvda",
            points=(
                PricePoint(date(2026, 1, 2), 100.0),
                PricePoint(date(2026, 1, 5), 101.0),
                PricePoint(date(2026, 1, 6), 102.0),
            ),
        )

    def test_normalizes_ticker_and_filters_inclusive_date_range(self) -> None:
        provider = InMemoryMarketDataProvider({"NVDA": self.series})

        result = provider.get_daily_prices(
            " nvda ", date(2026, 1, 2), date(2026, 1, 5)
        )

        self.assertEqual(result.ticker, "NVDA")
        self.assertEqual([point.adjusted_close for point in result.points], [100.0, 101.0])

    def test_rejects_non_chronological_series(self) -> None:
        with self.assertRaisesRegex(ValueError, "chronological"):
            PriceSeries(
                ticker="AAPL",
                points=(
                    PricePoint(date(2026, 1, 6), 102.0),
                    PricePoint(date(2026, 1, 5), 101.0),
                ),
            )

    def test_rejects_unknown_ticker(self) -> None:
        provider = InMemoryMarketDataProvider({"NVDA": self.series})

        with self.assertRaisesRegex(LookupError, "MSFT"):
            provider.get_daily_prices("MSFT", date(2026, 1, 2), date(2026, 1, 6))


if __name__ == "__main__":
    unittest.main()
