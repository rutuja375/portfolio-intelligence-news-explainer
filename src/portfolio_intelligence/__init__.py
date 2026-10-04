"""Portfolio Intelligence domain package."""

from .attribution import calculate_attribution
from .context import (
    ContextClassification,
    ContextConfig,
    MovementContext,
    compare_latest_context,
)
from .events import InvestigationEvent, InvestigationEventConfig, build_investigation_event
from .evidence import (
    EvidenceItem,
    EvidenceRankingConfig,
    EvidenceTiming,
    EvidenceWindow,
    InMemoryNewsProvider,
    NewsProvider,
    RankedEvidence,
    classify_evidence_timing,
    rank_evidence,
)
from .explanation import (
    ExplanationConfidence,
    ExplanationPolicy,
    ExplanationReadiness,
    GroundedClaim,
    GroundedExplanation,
    assess_explanation_readiness,
    build_abstention,
    build_grounded_explanation,
)
from .evaluation import (
    BinaryClassificationMetrics,
    ExplanationQualityMetrics,
    binary_classification_metrics,
    evaluate_claim_support,
    evaluate_explanation,
    precision_at_k,
    temporal_validity_rate,
)
from .market_data import (
    InMemoryMarketDataProvider,
    MarketDataProvider,
    MarketDataProviderError,
    PricePoint,
    PriceSeries,
)
from .models import Holding, HoldingPerformance, PortfolioAttribution, PortfolioSnapshot
from .movement import (
    DailyReturn,
    MovementDetectorConfig,
    MovementSignal,
    calculate_daily_returns,
    detect_latest_movement,
)
from .providers import YFinanceMarketDataProvider

__all__ = [
    "Holding",
    "HoldingPerformance",
    "ContextClassification",
    "ContextConfig",
    "EvidenceItem",
    "EvidenceRankingConfig",
    "EvidenceTiming",
    "EvidenceWindow",
    "BinaryClassificationMetrics",
    "ExplanationConfidence",
    "ExplanationPolicy",
    "ExplanationReadiness",
    "ExplanationQualityMetrics",
    "GroundedClaim",
    "GroundedExplanation",
    "InMemoryMarketDataProvider",
    "InvestigationEvent",
    "InvestigationEventConfig",
    "InMemoryNewsProvider",
    "MarketDataProvider",
    "MarketDataProviderError",
    "MovementDetectorConfig",
    "MovementContext",
    "MovementSignal",
    "NewsProvider",
    "PortfolioAttribution",
    "PortfolioSnapshot",
    "PricePoint",
    "PriceSeries",
    "RankedEvidence",
    "calculate_attribution",
    "assess_explanation_readiness",
    "binary_classification_metrics",
    "build_abstention",
    "build_grounded_explanation",
    "evaluate_claim_support",
    "evaluate_explanation",
    "calculate_daily_returns",
    "classify_evidence_timing",
    "compare_latest_context",
    "build_investigation_event",
    "detect_latest_movement",
    "rank_evidence",
    "precision_at_k",
    "temporal_validity_rate",
    "YFinanceMarketDataProvider",
    "DailyReturn",
]
