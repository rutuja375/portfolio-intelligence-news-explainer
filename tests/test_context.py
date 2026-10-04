import unittest
from datetime import date, timedelta

from portfolio_intelligence import (
    ContextClassification,
    ContextConfig,
    PricePoint,
    PriceSeries,
    compare_latest_context,
)


def series_for_return(ticker: str, result: float, day_offset: int = 0) -> PriceSeries:
    end_date = date(2026, 1, 6) + timedelta(days=day_offset)
    return PriceSeries(
        ticker=ticker,
        points=(
            PricePoint(end_date - timedelta(days=1), 100.0),
            PricePoint(end_date, 100.0 * (1 + result)),
        ),
    )


class ContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ContextConfig(
            broad_move_threshold=0.01,
            similarity_tolerance=0.015,
            company_specific_threshold=0.02,
        )

    def test_classifies_market_wide_move(self) -> None:
        result = compare_latest_context(
            security=series_for_return("NVDA", -0.032),
            market=series_for_return("SPY", -0.025),
            sector=series_for_return("SOXX", -0.028),
            config=self.config,
        )

        self.assertEqual(result.classification, ContextClassification.MARKET_WIDE)
        self.assertIn("SECTOR_ALSO_ALIGNED", result.reasons)

    def test_classifies_sector_and_peer_move(self) -> None:
        result = compare_latest_context(
            security=series_for_return("NVDA", -0.041),
            market=series_for_return("SPY", -0.003),
            sector=series_for_return("SOXX", -0.034),
            peers=(
                series_for_return("AMD", -0.036),
                series_for_return("AVGO", -0.032),
            ),
            config=self.config,
        )

        self.assertEqual(result.classification, ContextClassification.SECTOR_WIDE)
        self.assertAlmostEqual(result.peer_average_return or 0, -0.034)
        self.assertIn("SECURITY_ALIGNED_WITH_PEER_GROUP", result.reasons)

    def test_classifies_company_specific_move(self) -> None:
        result = compare_latest_context(
            security=series_for_return("NVDA", -0.052),
            market=series_for_return("SPY", -0.004),
            sector=series_for_return("SOXX", -0.011),
            peers=(series_for_return("AMD", -0.009),),
            config=self.config,
        )

        self.assertEqual(result.classification, ContextClassification.COMPANY_SPECIFIC)
        self.assertAlmostEqual(result.security_excess_vs_market, -0.048)
        self.assertIn("SECURITY_DIVERGED_FROM_PEER_GROUP", result.reasons)

    def test_classifies_ambiguous_move_as_mixed(self) -> None:
        result = compare_latest_context(
            security=series_for_return("NVDA", -0.029),
            market=series_for_return("SPY", -0.012),
            sector=series_for_return("SOXX", 0.002),
            config=self.config,
        )

        self.assertEqual(result.classification, ContextClassification.MIXED)

    def test_rejects_misaligned_latest_dates(self) -> None:
        with self.assertRaisesRegex(ValueError, "mismatched series: SPY"):
            compare_latest_context(
                security=series_for_return("NVDA", -0.04),
                market=series_for_return("SPY", -0.02, day_offset=-1),
                sector=series_for_return("SOXX", -0.03),
                config=self.config,
            )


if __name__ == "__main__":
    unittest.main()
