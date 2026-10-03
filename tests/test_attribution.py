import unittest

from portfolio_intelligence import Holding, PortfolioSnapshot, calculate_attribution


class AttributionTests(unittest.TestCase):
    def test_calculates_portfolio_return_and_ranks_contributors(self) -> None:
        portfolio = PortfolioSnapshot(
            holdings=(
                Holding("nvda", 0.50),
                Holding("MSFT", 0.30),
                Holding("JPM", 0.20),
            )
        )

        result = calculate_attribution(
            portfolio,
            {"NVDA": -0.052, "MSFT": -0.021, "JPM": 0.007},
        )

        self.assertAlmostEqual(result.portfolio_return, -0.0309)
        self.assertEqual(
            [item.ticker for item in result.contributors_by_impact],
            ["NVDA", "MSFT", "JPM"],
        )
        self.assertAlmostEqual(result.contributors_by_impact[0].contribution, -0.026)

    def test_requires_fully_invested_portfolio(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            PortfolioSnapshot(holdings=(Holding("AAPL", 0.75),))

    def test_rejects_duplicate_tickers_after_normalization(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            PortfolioSnapshot(holdings=(Holding("aapl", 0.5), Holding("AAPL", 0.5)))

    def test_requires_return_for_every_holding(self) -> None:
        portfolio = PortfolioSnapshot(
            holdings=(Holding("AAPL", 0.6), Holding("MSFT", 0.4))
        )

        with self.assertRaisesRegex(ValueError, "MSFT"):
            calculate_attribution(portfolio, {"AAPL": 0.01})


if __name__ == "__main__":
    unittest.main()
