"""Portfolio-first live analysis built on provider-independent market data."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .context import MovementContext, compare_latest_context
from .events import InvestigationEvent, InvestigationEventConfig, build_investigation_event
from .evidence import EvidenceWindow, NewsProvider, RankedEvidence, rank_evidence
from .explanation import ExplanationReadiness, assess_explanation_readiness
from .market_data import MarketDataProvider, PriceSeries
from .models import Holding, HoldingPerformance, PortfolioSnapshot
from .movement import MovementDetectorConfig, MovementSignal, detect_latest_movement


@dataclass(frozen=True, slots=True)
class PortfolioPositionInput:
    """User-supplied holding requiring only a ticker and number of shares."""

    ticker: str
    shares: float

    def __post_init__(self) -> None:
        normalized_ticker = self.ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker cannot be empty")
        if self.shares <= 0:
            raise ValueError("Shares must be greater than zero")
        object.__setattr__(self, "ticker", normalized_ticker)


@dataclass(frozen=True, slots=True)
class LiveHoldingAnalysis:
    """Price, value, attribution and movement result for one live holding."""

    ticker: str
    shares: float
    previous_adjusted_close: float
    latest_adjusted_close: float
    previous_market_value: float
    current_market_value: float
    attribution_weight: float
    current_weight: float
    period_return: float
    contribution: float
    movement: MovementSignal | None
    movement_error: str | None
    investigation_candidate: bool
    prices: PriceSeries


@dataclass(frozen=True, slots=True)
class LivePortfolioAnalysis:
    """Portfolio analysis calculated from user shares and live adjusted prices."""

    start_date: date
    requested_end_date: date
    as_of_date: date
    previous_total_value: float
    current_total_value: float
    portfolio_return: float
    holdings: tuple[LiveHoldingAnalysis, ...]

    @property
    def holdings_by_impact(self) -> tuple[LiveHoldingAnalysis, ...]:
        return tuple(sorted(self.holdings, key=lambda item: abs(item.contribution), reverse=True))

    @property
    def investigation_candidates(self) -> tuple[LiveHoldingAnalysis, ...]:
        return tuple(item for item in self.holdings_by_impact if item.investigation_candidate)


@dataclass(frozen=True, slots=True)
class ContextDefinition:
    """Curated market, sector and peer benchmarks for a security."""

    market_ticker: str
    sector_ticker: str
    peer_tickers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiveInvestigationDetail:
    """Detailed context and investigation event for a flagged live holding."""

    holding: LiveHoldingAnalysis
    context: MovementContext
    event: InvestigationEvent


@dataclass(frozen=True, slots=True)
class LiveEvidenceAssessment:
    """Ranked live evidence and the deterministic explain-or-abstain decision."""

    ticker: str
    evidence_window: EvidenceWindow
    search_start: datetime
    search_end: datetime
    ranked_evidence: tuple[RankedEvidence, ...]
    readiness: ExplanationReadiness


DEFAULT_CONTEXT_DEFINITIONS: Mapping[str, ContextDefinition] = {
    "NVDA": ContextDefinition("SPY", "SOXX", ("AMD", "AVGO")),
    "AMD": ContextDefinition("SPY", "SOXX", ("NVDA", "AVGO")),
    "AVGO": ContextDefinition("SPY", "SOXX", ("NVDA", "AMD")),
    "MSFT": ContextDefinition("SPY", "XLK", ("AAPL", "ORCL")),
    "AAPL": ContextDefinition("SPY", "XLK", ("MSFT", "QCOM")),
    "AMZN": ContextDefinition("SPY", "XLY", ("WMT", "TGT")),
    "JPM": ContextDefinition("SPY", "XLF", ("BAC", "C")),
}


def analyze_live_portfolio(
    positions: Sequence[PortfolioPositionInput],
    provider: MarketDataProvider,
    start: date,
    end: date,
    movement_config: MovementDetectorConfig | None = None,
    minimum_absolute_contribution: float = 0.005,
) -> LivePortfolioAnalysis:
    """Fetch prices and calculate a portfolio analysis from ticker/share inputs."""

    if not positions:
        raise ValueError("Portfolio must contain at least one position")
    tickers = [position.ticker for position in positions]
    if len(tickers) != len(set(tickers)):
        raise ValueError("Portfolio cannot contain duplicate tickers")
    if start >= end:
        raise ValueError("Start date must be before end date")
    if minimum_absolute_contribution < 0:
        raise ValueError("Minimum absolute contribution cannot be negative")

    series_by_ticker = {
        position.ticker: provider.get_daily_prices(position.ticker, start, end)
        for position in positions
    }
    latest_dates = {series.points[-1].date for series in series_by_ticker.values()}
    previous_dates = {series.points[-2].date for series in series_by_ticker.values()}
    if len(latest_dates) != 1 or len(previous_dates) != 1:
        raise ValueError("All holdings must share aligned latest and previous trading dates")

    raw = []
    for position in positions:
        series = series_by_ticker[position.ticker]
        previous_close = series.points[-2].adjusted_close
        latest_close = series.points[-1].adjusted_close
        previous_value = position.shares * previous_close
        current_value = position.shares * latest_close
        period_return = latest_close / previous_close - 1
        raw.append(
            (
                position,
                series,
                previous_close,
                latest_close,
                previous_value,
                current_value,
                period_return,
            )
        )

    previous_total = sum(item[4] for item in raw)
    current_total = sum(item[5] for item in raw)
    portfolio = PortfolioSnapshot(
        holdings=tuple(
            Holding(item[0].ticker, item[4] / previous_total) for item in raw
        )
    )
    weights = {holding.ticker: holding.weight for holding in portfolio.holdings}
    resolved_movement_config = movement_config or MovementDetectorConfig()

    holdings = []
    for (
        position,
        series,
        previous_close,
        latest_close,
        previous_value,
        current_value,
        period_return,
    ) in raw:
        weight = weights[position.ticker]
        contribution = weight * period_return
        try:
            movement = detect_latest_movement(series, resolved_movement_config)
            movement_error = None
        except ValueError as error:
            movement = None
            movement_error = str(error)
        investigation_candidate = (
            movement is not None
            and movement.is_abnormal
            and abs(contribution) >= minimum_absolute_contribution
        )
        holdings.append(
            LiveHoldingAnalysis(
                ticker=position.ticker,
                shares=position.shares,
                previous_adjusted_close=previous_close,
                latest_adjusted_close=latest_close,
                previous_market_value=previous_value,
                current_market_value=current_value,
                attribution_weight=weight,
                current_weight=current_value / current_total,
                period_return=period_return,
                contribution=contribution,
                movement=movement,
                movement_error=movement_error,
                investigation_candidate=investigation_candidate,
                prices=series,
            )
        )

    return LivePortfolioAnalysis(
        start_date=start,
        requested_end_date=end,
        as_of_date=next(iter(latest_dates)),
        previous_total_value=previous_total,
        current_total_value=current_total,
        portfolio_return=sum(item.contribution for item in holdings),
        holdings=tuple(holdings),
    )


def build_live_investigation_detail(
    analysis: LivePortfolioAnalysis,
    ticker: str,
    provider: MarketDataProvider,
    definitions: Mapping[str, ContextDefinition] = DEFAULT_CONTEXT_DEFINITIONS,
    event_config: InvestigationEventConfig | None = None,
) -> LiveInvestigationDetail:
    """Open market, sector and peer context for one flagged portfolio holding."""

    normalized_ticker = ticker.strip().upper()
    holding = next(
        (item for item in analysis.holdings if item.ticker == normalized_ticker),
        None,
    )
    if holding is None:
        raise LookupError(f"Portfolio does not contain {normalized_ticker}")
    if not holding.investigation_candidate or holding.movement is None:
        raise ValueError(f"{normalized_ticker} is not currently flagged for investigation")
    try:
        definition = definitions[normalized_ticker]
    except KeyError as error:
        raise LookupError(
            f"No curated sector and peer context is configured for {normalized_ticker}"
        ) from error

    market = provider.get_daily_prices(
        definition.market_ticker, analysis.start_date, analysis.requested_end_date
    )
    sector = provider.get_daily_prices(
        definition.sector_ticker, analysis.start_date, analysis.requested_end_date
    )
    peers = tuple(
        provider.get_daily_prices(peer, analysis.start_date, analysis.requested_end_date)
        for peer in definition.peer_tickers
    )
    context = compare_latest_context(holding.prices, market, sector, peers)
    performance = HoldingPerformance(
        ticker=holding.ticker,
        weight=holding.attribution_weight,
        period_return=holding.period_return,
        contribution=holding.contribution,
    )
    event = build_investigation_event(
        performance,
        holding.movement,
        context,
        event_config,
    )
    return LiveInvestigationDetail(holding=holding, context=context, event=event)


def build_live_evidence_assessment(
    detail: LiveInvestigationDetail,
    provider: NewsProvider,
    surrounding_hours: float = 24.0,
    evidence_limit: int = 10,
) -> LiveEvidenceAssessment:
    """Retrieve, time-align and rank news for a live investigation event."""

    if not detail.event.investigation_required:
        raise ValueError("Live evidence can only be retrieved for an investigation event")
    if surrounding_hours < 0:
        raise ValueError("Surrounding hours cannot be negative")
    if evidence_limit <= 0:
        raise ValueError("Evidence limit must be positive")

    points = detail.holding.prices.points
    if len(points) < 2:
        raise ValueError("At least two price observations are required")
    market_timezone = ZoneInfo("America/New_York")
    movement_start = datetime.combine(points[-2].date, time(16, 0), market_timezone)
    movement_end = datetime.combine(points[-1].date, time(16, 0), market_timezone)
    window = EvidenceWindow(
        movement_start=movement_start.astimezone(timezone.utc),
        movement_end=movement_end.astimezone(timezone.utc),
    )
    padding = timedelta(hours=surrounding_hours)
    search_start = window.movement_start - padding
    search_end = window.movement_end + padding
    items = provider.search(detail.holding.ticker, search_start, search_end)
    ranked = rank_evidence(items, window, limit=evidence_limit)
    readiness = assess_explanation_readiness(ranked)
    return LiveEvidenceAssessment(
        ticker=detail.holding.ticker,
        evidence_window=window,
        search_start=search_start,
        search_end=search_end,
        ranked_evidence=ranked,
        readiness=readiness,
    )
