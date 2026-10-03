"""Portfolio Intelligence domain package."""

from .attribution import calculate_attribution
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
    "InMemoryMarketDataProvider",
    "MarketDataProvider",
    "MovementDetectorConfig",
    "MovementSignal",
    "PortfolioAttribution",
    "PortfolioSnapshot",
    "PricePoint",
    "PriceSeries",
    "calculate_attribution",
    "calculate_daily_returns",
    "detect_latest_movement",
    "DailyReturn",
]
