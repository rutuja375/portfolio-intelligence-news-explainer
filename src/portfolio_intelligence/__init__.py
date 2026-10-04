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
from .market_data import InMemoryMarketDataProvider, MarketDataProvider, PricePoint, PriceSeries
from .models import Holding, HoldingPerformance, PortfolioAttribution, PortfolioSnapshot
from .movement import (
    DailyReturn,
    MovementDetectorConfig,
    MovementSignal,
    calculate_daily_returns,
    detect_latest_movement,
)

__all__ = [
    "Holding",
    "HoldingPerformance",
    "ContextClassification",
    "ContextConfig",
    "EvidenceItem",
    "EvidenceRankingConfig",
    "EvidenceTiming",
    "EvidenceWindow",
    "InMemoryMarketDataProvider",
    "InvestigationEvent",
    "InvestigationEventConfig",
    "InMemoryNewsProvider",
    "MarketDataProvider",
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
    "calculate_daily_returns",
    "classify_evidence_timing",
    "compare_latest_context",
    "build_investigation_event",
    "detect_latest_movement",
    "rank_evidence",
    "DailyReturn",
]
