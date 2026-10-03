"""Deterministic return calculations and abnormal-movement detection."""

from dataclasses import dataclass
from datetime import date
from statistics import fmean, pstdev

from .market_data import PriceSeries


@dataclass(frozen=True, slots=True)
class DailyReturn:
    """Simple close-to-close return for one trading date."""

    date: date
    value: float


@dataclass(frozen=True, slots=True)
class MovementDetectorConfig:
    """Thresholds controlling when a movement is flagged for investigation."""

    lookback_periods: int = 20
    minimum_history: int = 5
    absolute_return_threshold: float = 0.03
    z_score_threshold: float = 2.0

    def __post_init__(self) -> None:
        if self.lookback_periods < 2:
            raise ValueError("Lookback periods must be at least 2")
        if not 2 <= self.minimum_history <= self.lookback_periods:
            raise ValueError("Minimum history must be between 2 and the lookback periods")
        if self.absolute_return_threshold <= 0:
            raise ValueError("Absolute-return threshold must be positive")
        if self.z_score_threshold <= 0:
            raise ValueError("Z-score threshold must be positive")


@dataclass(frozen=True, slots=True)
class MovementSignal:
    """Auditable result of evaluating the latest security return."""

    ticker: str
    date: date
    observed_return: float
    historical_mean: float
    historical_volatility: float
    z_score: float | None
    is_abnormal: bool
    reasons: tuple[str, ...]
    history_periods: int


def calculate_daily_returns(series: PriceSeries) -> tuple[DailyReturn, ...]:
    """Calculate simple close-to-close returns from adjusted prices."""

    return tuple(
        DailyReturn(
            date=current.date,
            value=(current.adjusted_close / previous.adjusted_close) - 1,
        )
        for previous, current in zip(series.points, series.points[1:])
    )


def detect_latest_movement(
    series: PriceSeries,
    config: MovementDetectorConfig | None = None,
) -> MovementSignal:
    """Evaluate the latest return against its preceding historical window.

    The latest return is never included in its own baseline. A movement is
    abnormal when it crosses either the absolute-return or z-score threshold.
    """

    resolved_config = config or MovementDetectorConfig()
    returns = calculate_daily_returns(series)
    latest = returns[-1]
    history = returns[-(resolved_config.lookback_periods + 1) : -1]
    if len(history) < resolved_config.minimum_history:
        raise ValueError(
            "Insufficient return history: "
            f"need at least {resolved_config.minimum_history}, received {len(history)}"
        )

    historical_values = [item.value for item in history]
    historical_mean = fmean(historical_values)
    historical_volatility = pstdev(historical_values)
    z_score = (
        (latest.value - historical_mean) / historical_volatility
        if historical_volatility > 0
        else None
    )

    reasons = []
    if abs(latest.value) >= resolved_config.absolute_return_threshold:
        reasons.append("ABSOLUTE_RETURN_THRESHOLD")
    if z_score is not None and abs(z_score) >= resolved_config.z_score_threshold:
        reasons.append("Z_SCORE_THRESHOLD")

    return MovementSignal(
        ticker=series.ticker,
        date=latest.date,
        observed_return=latest.value,
        historical_mean=historical_mean,
        historical_volatility=historical_volatility,
        z_score=z_score,
        is_abnormal=bool(reasons),
        reasons=tuple(reasons),
        history_periods=len(history),
    )
