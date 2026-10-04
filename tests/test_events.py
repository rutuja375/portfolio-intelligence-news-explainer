import unittest
from datetime import date

from portfolio_intelligence import (
    ContextClassification,
    HoldingPerformance,
    InvestigationEventConfig,
    MovementContext,
    MovementSignal,
    build_investigation_event,
)


EVENT_DATE = date(2026, 1, 6)


def movement(
    *, ticker: str = "NVDA", observed_return: float = -0.05, abnormal: bool = True
) -> MovementSignal:
    return MovementSignal(
        ticker=ticker,
        date=EVENT_DATE,
        observed_return=observed_return,
        historical_mean=0.001,
        historical_volatility=0.012,
        z_score=-4.25 if abnormal else -0.5,
        is_abnormal=abnormal,
        reasons=("Z_SCORE_THRESHOLD",) if abnormal else (),
        history_periods=20,
    )


def context(
    *,
    ticker: str = "NVDA",
    security_return: float = -0.05,
    event_date: date = EVENT_DATE,
) -> MovementContext:
    return MovementContext(
        date=event_date,
        security_ticker=ticker,
        market_ticker="SPY",
        sector_ticker="SOXX",
        peer_tickers=("AMD",),
        security_return=security_return,
        market_return=-0.005,
        sector_return=-0.012,
        peer_average_return=-0.01,
        security_excess_vs_market=-0.045,
        security_excess_vs_sector=-0.038,
        security_excess_vs_peers=-0.04,
        classification=ContextClassification.COMPANY_SPECIFIC,
        reasons=("SECURITY_DIVERGED_FROM_MARKET_AND_SECTOR",),
    )


def holding(
    *, ticker: str = "NVDA", weight: float = 0.20, period_return: float = -0.05
) -> HoldingPerformance:
    return HoldingPerformance(
        ticker=ticker,
        weight=weight,
        period_return=period_return,
        contribution=weight * period_return,
    )


class InvestigationEventTests(unittest.TestCase):
    def test_requires_investigation_for_abnormal_material_contributor(self) -> None:
        event = build_investigation_event(holding(), movement(), context())

        self.assertEqual(event.event_id, "NVDA-20260106")
        self.assertTrue(event.investigation_required)
        self.assertIn("ABNORMAL_SECURITY_MOVEMENT", event.decision_reasons)
        self.assertIn("MATERIAL_PORTFOLIO_CONTRIBUTION", event.decision_reasons)
        self.assertIn("CONTEXT_COMPANY_SPECIFIC", event.decision_reasons)

    def test_skips_immaterial_portfolio_contributor(self) -> None:
        event = build_investigation_event(
            holding(weight=0.02),
            movement(),
            context(),
            InvestigationEventConfig(minimum_absolute_contribution=0.005),
        )

        self.assertFalse(event.investigation_required)
        self.assertIn("CONTRIBUTION_BELOW_THRESHOLD", event.decision_reasons)

    def test_skips_movement_that_is_not_abnormal(self) -> None:
        event = build_investigation_event(
            holding(),
            movement(abnormal=False),
            context(),
        )

        self.assertFalse(event.investigation_required)
        self.assertIn("MOVEMENT_NOT_ABNORMAL", event.decision_reasons)

    def test_rejects_mismatched_ticker(self) -> None:
        with self.assertRaisesRegex(ValueError, "same ticker"):
            build_investigation_event(holding(), movement(ticker="MSFT"), context())

    def test_rejects_misaligned_return(self) -> None:
        with self.assertRaisesRegex(ValueError, "Movement and context"):
            build_investigation_event(
                holding(),
                movement(),
                context(security_return=-0.04),
            )

    def test_rejects_invalid_contribution(self) -> None:
        invalid_holding = HoldingPerformance(
            ticker="NVDA",
            weight=0.20,
            period_return=-0.05,
            contribution=-0.02,
        )

        with self.assertRaisesRegex(ValueError, "weight multiplied"):
            build_investigation_event(invalid_holding, movement(), context())


if __name__ == "__main__":
    unittest.main()
