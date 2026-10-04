import unittest
from datetime import date, timedelta

from portfolio_intelligence import (
    ContextClassification,
    ContextDefinition,
    InMemoryMarketDataProvider,
    MovementDetectorConfig,
    PortfolioPositionInput,
    PricePoint,
    PriceSeries,
    analyze_live_portfolio,
    build_live_investigation_detail,
)


START = date(2026, 1, 1)
END = date(2026, 1, 6)


def series(ticker: str, prices: tuple[float, ...], day_offset: int = 0) -> PriceSeries:
    return PriceSeries(
        ticker=ticker,
        points=tuple(
            PricePoint(START + timedelta(days=index + day_offset), price)
            for index, price in enumerate(prices)
        ),
    )


class LivePortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = InMemoryMarketDataProvider(
            {
                "NVDA": series("NVDA", (100, 101, 100, 101, 100, 95)),
                "MSFT": series("MSFT", (100, 100.5, 100, 100.5, 100, 101)),
                "SPY": series("SPY", (100, 100, 100, 100, 100, 99.5)),
                "SOXX": series("SOXX", (100, 100, 100, 100, 100, 98.8)),
                "AMD": series("AMD", (100, 100, 100, 100, 100, 99)),
                "AVGO": series("AVGO", (100, 100, 100, 100, 100, 99.2)),
            }
        )
        self.config = MovementDetectorConfig(
            lookback_periods=4,
            minimum_history=4,
            absolute_return_threshold=0.03,
            z_score_threshold=2.0,
        )

    def test_calculates_weights_from_shares_and_prices(self) -> None:
        analysis = analyze_live_portfolio(
            (
                PortfolioPositionInput("NVDA", 10),
                PortfolioPositionInput("MSFT", 5),
            ),
            self.provider,
            START,
            END,
            self.config,
        )

        nvda = next(item for item in analysis.holdings if item.ticker == "NVDA")
        self.assertAlmostEqual(nvda.previous_market_value, 1000.0)
        self.assertAlmostEqual(nvda.attribution_weight, 2 / 3)
        self.assertAlmostEqual(nvda.current_market_value, 950.0)
        self.assertAlmostEqual(analysis.portfolio_return, (-0.05 * 2 / 3) + (0.01 / 3))

    def test_flags_abnormal_material_contributor(self) -> None:
        analysis = analyze_live_portfolio(
            (
                PortfolioPositionInput("NVDA", 10),
                PortfolioPositionInput("MSFT", 5),
            ),
            self.provider,
            START,
            END,
            self.config,
        )

        self.assertEqual(
            [item.ticker for item in analysis.investigation_candidates],
            ["NVDA"],
        )

    def test_opens_curated_context_for_flagged_holding(self) -> None:
        analysis = analyze_live_portfolio(
            (
                PortfolioPositionInput("NVDA", 10),
                PortfolioPositionInput("MSFT", 5),
            ),
            self.provider,
            START,
            END,
            self.config,
        )

        detail = build_live_investigation_detail(
            analysis,
            "NVDA",
            self.provider,
            {"NVDA": ContextDefinition("SPY", "SOXX", ("AMD", "AVGO"))},
        )

        self.assertEqual(detail.context.classification, ContextClassification.COMPANY_SPECIFIC)
        self.assertTrue(detail.event.investigation_required)

    def test_rejects_duplicate_tickers(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            analyze_live_portfolio(
                (
                    PortfolioPositionInput("NVDA", 10),
                    PortfolioPositionInput("nvda", 5),
                ),
                self.provider,
                START,
                END,
                self.config,
            )

    def test_rejects_misaligned_trading_dates(self) -> None:
        provider = InMemoryMarketDataProvider(
            {
                "NVDA": series("NVDA", (100, 101, 100, 101, 100, 95)),
                "MSFT": series("MSFT", (100, 100.5, 100, 100.5, 100)),
            }
        )

        with self.assertRaisesRegex(ValueError, "aligned"):
            analyze_live_portfolio(
                (
                    PortfolioPositionInput("NVDA", 10),
                    PortfolioPositionInput("MSFT", 5),
                ),
                provider,
                START,
                END,
                self.config,
            )


if __name__ == "__main__":
    unittest.main()
