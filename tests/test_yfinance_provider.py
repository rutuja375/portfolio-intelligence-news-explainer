import unittest
from datetime import date, datetime

from portfolio_intelligence import MarketDataProviderError, YFinanceMarketDataProvider


class FakeSeries:
    def __init__(self, values: dict[datetime, object]) -> None:
        self._values = values

    def items(self):
        return self._values.items()


class FakeFrame:
    def __init__(self, close_values: dict[datetime, object] | None = None) -> None:
        self.empty = not close_values
        self._close_values = close_values

    def __getitem__(self, key: str):
        if key != "Close" or self._close_values is None:
            raise KeyError(key)
        return FakeSeries(self._close_values)


class YFinanceProviderTests(unittest.TestCase):
    def test_requests_adjusted_daily_data_and_converts_response(self) -> None:
        received = {}

        def download(ticker: str, **kwargs):
            received["ticker"] = ticker
            received.update(kwargs)
            return FakeFrame(
                {
                    datetime(2026, 1, 2): 100.0,
                    datetime(2026, 1, 5): 102.5,
                    datetime(2026, 1, 6): 103.0,
                }
            )

        provider = YFinanceMarketDataProvider(download=download)
        result = provider.get_daily_prices(" nvda ", date(2026, 1, 2), date(2026, 1, 5))

        self.assertEqual(received["ticker"], "NVDA")
        self.assertEqual(received["start"], "2026-01-02")
        self.assertEqual(received["end"], "2026-01-06")
        self.assertTrue(received["auto_adjust"])
        self.assertTrue(received["repair"])
        self.assertEqual(result.ticker, "NVDA")
        self.assertEqual([point.adjusted_close for point in result.points], [100.0, 102.5])

    def test_wraps_downloader_failure_without_exposing_provider_details(self) -> None:
        def download(*args, **kwargs):
            raise OSError("network unavailable")

        provider = YFinanceMarketDataProvider(download=download)

        with self.assertRaisesRegex(MarketDataProviderError, "request failed"):
            provider.get_daily_prices("NVDA", date(2026, 1, 2), date(2026, 1, 5))

    def test_rejects_empty_provider_response(self) -> None:
        provider = YFinanceMarketDataProvider(download=lambda *args, **kwargs: FakeFrame())

        with self.assertRaisesRegex(LookupError, "no prices"):
            provider.get_daily_prices("NVDA", date(2026, 1, 2), date(2026, 1, 5))

    def test_rejects_invalid_close_values(self) -> None:
        provider = YFinanceMarketDataProvider(
            download=lambda *args, **kwargs: FakeFrame(
                {
                    datetime(2026, 1, 2): 100.0,
                    datetime(2026, 1, 5): float("nan"),
                }
            )
        )

        with self.assertRaisesRegex(MarketDataProviderError, "invalid close"):
            provider.get_daily_prices("NVDA", date(2026, 1, 2), date(2026, 1, 5))


if __name__ == "__main__":
    unittest.main()
