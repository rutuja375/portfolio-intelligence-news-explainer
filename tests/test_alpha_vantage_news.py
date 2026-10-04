import unittest
from datetime import datetime, timezone

from portfolio_intelligence import AlphaVantageNewsError, AlphaVantageNewsProvider

UTC = timezone.utc
START = datetime(2026, 1, 6, 14, 0, tzinfo=UTC)
END = datetime(2026, 1, 6, 18, 0, tzinfo=UTC)


def article(
    url: str = "https://example.com/nvda-news",
    published: str = "20260106T153000",
) -> dict:
    return {
        "title": "Nvidia announces a material business update",
        "url": url,
        "time_published": published,
        "summary": "A timestamped summary from the source.",
        "source": "Example Wire",
        "topics": [{"topic": "Technology", "relevance_score": "0.82"}],
        "ticker_sentiment": [
            {
                "ticker": "NVDA",
                "relevance_score": "0.91",
                "ticker_sentiment_score": "-0.35",
            }
        ],
    }


class AlphaVantageNewsProviderTests(unittest.TestCase):
    def test_normalizes_and_filters_news_using_exact_window(self) -> None:
        captured = {}

        def transport(params, timeout):
            captured.update(params)
            return {
                "feed": [
                    article(),
                    article("https://example.com/too-late", "20260106T180001"),
                ]
            }

        provider = AlphaVantageNewsProvider("secret", transport=transport)
        results = provider.search(" nvda ", START, END)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].related_tickers, ("NVDA",))
        self.assertEqual(results[0].semantic_relevance, 0.91)
        self.assertEqual(results[0].financial_relevance, 0.82)
        self.assertEqual(results[0].source_quality, 0.5)
        self.assertEqual(results[0].sentiment, -0.35)
        self.assertEqual(captured["function"], "NEWS_SENTIMENT")
        self.assertEqual(captured["tickers"], "NVDA")

    def test_deduplicates_articles_by_url(self) -> None:
        provider = AlphaVantageNewsProvider(
            "secret",
            transport=lambda params, timeout: {"feed": [article(), article()]},
        )

        self.assertEqual(len(provider.search("NVDA", START, END)), 1)

    def test_excludes_articles_without_explicit_requested_ticker_metadata(self) -> None:
        unrelated = article("https://example.com/unrelated")
        unrelated["ticker_sentiment"] = [
            {
                "ticker": "KO",
                "relevance_score": "0.95",
                "ticker_sentiment_score": "0.2",
            }
        ]
        provider = AlphaVantageNewsProvider(
            "secret",
            transport=lambda params, timeout: {"feed": [unrelated, article()]},
        )

        results = provider.search("NVDA", START, END)

        self.assertEqual([item.url for item in results], ["https://example.com/nvda-news"])

    def test_enforces_result_limit_when_provider_returns_more_items(self) -> None:
        provider = AlphaVantageNewsProvider(
            "secret",
            result_limit=1,
            transport=lambda params, timeout: {
                "feed": [
                    article("https://example.com/first", "20260106T150000"),
                    article("https://example.com/second", "20260106T160000"),
                ]
            },
        )

        results = provider.search("NVDA", START, END)

        self.assertEqual(len(results), 1)

    def test_excludes_incidental_low_relevance_ticker_mentions(self) -> None:
        incidental = article("https://example.com/incidental")
        incidental["ticker_sentiment"][0]["relevance_score"] = "0.49"
        provider = AlphaVantageNewsProvider(
            "secret",
            transport=lambda params, timeout: {"feed": [incidental, article()]},
        )

        results = provider.search("NVDA", START, END)

        self.assertEqual([item.url for item in results], ["https://example.com/nvda-news"])

    def test_surfaces_provider_limit_message(self) -> None:
        provider = AlphaVantageNewsProvider(
            "secret",
            transport=lambda params, timeout: {"Note": "Daily request limit reached"},
        )

        with self.assertRaisesRegex(AlphaVantageNewsError, "request limit"):
            provider.search("NVDA", START, END)

    def test_rejects_naive_search_times(self) -> None:
        provider = AlphaVantageNewsProvider(
            "secret", transport=lambda params, timeout: {"feed": []}
        )

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            provider.search("NVDA", datetime(2026, 1, 6), END)


if __name__ == "__main__":
    unittest.main()
