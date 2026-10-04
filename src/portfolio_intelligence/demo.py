"""Coherent synthetic investigation used by the analyst-interface demo."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .attribution import calculate_attribution
from .context import MovementContext, compare_latest_context
from .events import InvestigationEvent, build_investigation_event
from .evidence import EvidenceItem, EvidenceWindow, RankedEvidence, rank_evidence
from .explanation import (
    ExplanationReadiness,
    GroundedClaim,
    GroundedExplanation,
    assess_explanation_readiness,
    build_grounded_explanation,
)
from .market_data import PricePoint, PriceSeries
from .models import Holding, PortfolioAttribution, PortfolioSnapshot
from .movement import MovementDetectorConfig, MovementSignal, detect_latest_movement


@dataclass(frozen=True, slots=True)
class DemoInvestigation:
    """All stages required to render one end-to-end analyst investigation."""

    attribution: PortfolioAttribution
    movement: MovementSignal
    context: MovementContext
    event: InvestigationEvent
    ranked_evidence: tuple[RankedEvidence, ...]
    readiness: ExplanationReadiness
    explanation: GroundedExplanation
    evidence_window: EvidenceWindow


def _series(ticker: str, prices: tuple[float, ...], start: date) -> PriceSeries:
    return PriceSeries(
        ticker=ticker,
        points=tuple(
            PricePoint(start + timedelta(days=index), price)
            for index, price in enumerate(prices)
        ),
    )


def _evidence_items(window: EvidenceWindow) -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem(
            evidence_id="nvda-guidance-filing",
            title="Company files updated near-term revenue outlook",
            summary=(
                "A synthetic company filing updates the near-term revenue outlook before "
                "the detected movement."
            ),
            url="https://example.com/nvda-guidance-filing",
            source="Company filing",
            published_at=window.movement_start - timedelta(hours=1),
            related_tickers=("NVDA",),
            semantic_relevance=0.96,
            financial_relevance=0.97,
            source_quality=0.98,
            sentiment=-0.75,
        ),
        EvidenceItem(
            evidence_id="nvda-wire-report",
            title="Reporting highlights revised company outlook",
            summary=(
                "A synthetic wire report published during the movement discusses the "
                "revised outlook and investor reaction."
            ),
            url="https://example.com/nvda-wire-report",
            source="Financial wire",
            published_at=window.movement_start + timedelta(minutes=6),
            related_tickers=("NVDA",),
            semantic_relevance=0.90,
            financial_relevance=0.91,
            source_quality=0.90,
            sentiment=-0.65,
        ),
        EvidenceItem(
            evidence_id="nvda-market-recap",
            title="Post-close recap summarizes the trading session",
            summary=(
                "A synthetic recap published after the movement summarizes price action "
                "but was not available contemporaneously."
            ),
            url="https://example.com/nvda-market-recap",
            source="Market recap",
            published_at=window.movement_end + timedelta(hours=2),
            related_tickers=("NVDA",),
            semantic_relevance=0.74,
            financial_relevance=0.68,
            source_quality=0.72,
            sentiment=-0.45,
        ),
    )


def build_demo_investigation() -> DemoInvestigation:
    """Execute the real deterministic pipeline over a synthetic NVDA scenario."""

    event_date = date(2026, 1, 6)
    portfolio = PortfolioSnapshot(
        holdings=(
            Holding("NVDA", 0.40),
            Holding("MSFT", 0.25),
            Holding("AAPL", 0.15),
            Holding("AMZN", 0.10),
            Holding("JPM", 0.10),
        )
    )
    period_returns = {
        "NVDA": -0.05,
        "MSFT": -0.012,
        "AAPL": -0.008,
        "AMZN": -0.015,
        "JPM": 0.006,
    }
    attribution = calculate_attribution(portfolio, period_returns)

    movement_series = _series(
        "NVDA",
        (100.0, 101.0, 100.0, 101.0, 100.0, 95.0),
        date(2026, 1, 1),
    )
    movement = detect_latest_movement(
        movement_series,
        MovementDetectorConfig(
            lookback_periods=4,
            minimum_history=4,
            absolute_return_threshold=0.03,
            z_score_threshold=2.0,
        ),
    )

    comparison_start = event_date - timedelta(days=1)
    context = compare_latest_context(
        security=_series("NVDA", (100.0, 95.0), comparison_start),
        market=_series("SPY", (100.0, 99.5), comparison_start),
        sector=_series("SOXX", (100.0, 98.8), comparison_start),
        peers=(
            _series("AMD", (100.0, 99.0), comparison_start),
            _series("AVGO", (100.0, 99.2), comparison_start),
        ),
    )
    nvda_performance = next(
        item for item in attribution.holdings if item.ticker == "NVDA"
    )
    event = build_investigation_event(nvda_performance, movement, context)

    window = EvidenceWindow(
        movement_start=datetime(2026, 1, 6, 15, 30, tzinfo=timezone.utc),
        movement_end=datetime(2026, 1, 6, 15, 45, tzinfo=timezone.utc),
    )
    ranked = rank_evidence(_evidence_items(window), window)
    readiness = assess_explanation_readiness(ranked)
    explanation = build_grounded_explanation(
        summary=(
            "Selected evidence suggests a potential company-specific factor coincided "
            "with the movement; the available evidence supports association, not causation."
        ),
        claims=(
            GroundedClaim(
                "The company released an updated outlook before the detected movement.",
                ("nvda-guidance-filing",),
            ),
            GroundedClaim(
                "Contemporaneous reporting discussed the revised outlook during the move.",
                ("nvda-wire-report", "nvda-guidance-filing"),
            ),
        ),
        readiness=readiness,
    )
    return DemoInvestigation(
        attribution=attribution,
        movement=movement,
        context=context,
        event=event,
        ranked_evidence=ranked,
        readiness=readiness,
        explanation=explanation,
        evidence_window=window,
    )
