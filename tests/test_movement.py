import unittest
from datetime import date, timedelta

from portfolio_intelligence import (
    MovementDetectorConfig,
    PricePoint,
    PriceSeries,
    calculate_daily_returns,
    detect_latest_movement,
)


def make_series(ticker: str, prices: list[float]) -> PriceSeries:
    start = date(2026, 1, 1)
    return PriceSeries(
        ticker=ticker,
        points=tuple(
            PricePoint(start + timedelta(days=index), price)
            for index, price in enumerate(prices)
        ),
    )


class MovementTests(unittest.TestCase):
    def test_calculates_close_to_close_returns(self) -> None:
        series = make_series("AAPL", [100.0, 105.0, 102.9])

        returns = calculate_daily_returns(series)

        self.assertAlmostEqual(returns[0].value, 0.05)
        self.assertAlmostEqual(returns[1].value, -0.02)

    def test_flags_large_latest_move_using_absolute_threshold(self) -> None:
        series = make_series("NVDA", [100.0, 101.0, 102.0, 103.0, 104.0, 98.0])
        config = MovementDetectorConfig(
            lookback_periods=4,
            minimum_history=4,
            absolute_return_threshold=0.03,
            z_score_threshold=2.0,
        )

        signal = detect_latest_movement(series, config)

        self.assertTrue(signal.is_abnormal)
        self.assertIn("ABSOLUTE_RETURN_THRESHOLD", signal.reasons)
        self.assertAlmostEqual(signal.observed_return, (98.0 / 104.0) - 1)
        self.assertEqual(signal.history_periods, 4)

    def test_does_not_flag_normal_move(self) -> None:
        series = make_series("MSFT", [100.0, 101.0, 100.5, 101.5, 101.0, 102.0])
        config = MovementDetectorConfig(
            lookback_periods=4,
            minimum_history=4,
            absolute_return_threshold=0.03,
            z_score_threshold=5.0,
        )

        signal = detect_latest_movement(series, config)

        self.assertFalse(signal.is_abnormal)
        self.assertEqual(signal.reasons, ())

    def test_flags_statistical_outlier_below_absolute_threshold(self) -> None:
        series = make_series("AAPL", [100.0, 101.0, 100.0, 101.0, 100.0, 102.5])
        config = MovementDetectorConfig(
            lookback_periods=4,
            minimum_history=4,
            absolute_return_threshold=0.03,
            z_score_threshold=2.0,
        )

        signal = detect_latest_movement(series, config)

        self.assertTrue(signal.is_abnormal)
        self.assertNotIn("ABSOLUTE_RETURN_THRESHOLD", signal.reasons)
        self.assertIn("Z_SCORE_THRESHOLD", signal.reasons)
        self.assertIsNotNone(signal.z_score)

    def test_requires_enough_baseline_history(self) -> None:
        series = make_series("JPM", [100.0, 101.0, 99.0])
        config = MovementDetectorConfig(
            lookback_periods=5,
            minimum_history=3,
            absolute_return_threshold=0.03,
            z_score_threshold=2.0,
        )

        with self.assertRaisesRegex(ValueError, "Insufficient"):
            detect_latest_movement(series, config)

    def test_zero_volatility_still_supports_absolute_threshold(self) -> None:
        series = make_series("JPM", [100.0, 100.0, 100.0, 100.0, 100.0, 95.0])
        config = MovementDetectorConfig(
            lookback_periods=4,
            minimum_history=4,
            absolute_return_threshold=0.03,
            z_score_threshold=2.0,
        )

        signal = detect_latest_movement(series, config)

        self.assertIsNone(signal.z_score)
        self.assertTrue(signal.is_abnormal)


if __name__ == "__main__":
    unittest.main()
