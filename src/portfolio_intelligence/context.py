"""Deterministic market, sector and peer context for a security movement."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from statistics import fmean

from .market_data import PriceSeries
from .movement import calculate_daily_returns


class ContextClassification(StrEnum):
    """High-level interpretation of a security's latest movement."""

    MARKET_WIDE = "MARKET_WIDE"
    SECTOR_WIDE = "SECTOR_WIDE"
    COMPANY_SPECIFIC = "COMPANY_SPECIFIC"
    MIXED = "MIXED"


@dataclass(frozen=True, slots=True)
class ContextConfig:
    """Transparent thresholds used to classify movement context."""

    broad_move_threshold: float = 0.01
    similarity_tolerance: float = 0.015
    company_specific_threshold: float = 0.02

    def __post_init__(self) -> None:
        if self.broad_move_threshold <= 0:
            raise ValueError("Broad-move threshold must be positive")
        if self.similarity_tolerance <= 0:
            raise ValueError("Similarity tolerance must be positive")
        if self.company_specific_threshold <= 0:
            raise ValueError("Company-specific threshold must be positive")


@dataclass(frozen=True, slots=True)
class MovementContext:
    """Auditable comparison of a security with its relevant benchmarks."""

    date: date
    security_ticker: str
    market_ticker: str
    sector_ticker: str
    peer_tickers: tuple[str, ...]
    security_return: float
    market_return: float
    sector_return: float
    peer_average_return: float | None
    security_excess_vs_market: float
    security_excess_vs_sector: float
    security_excess_vs_peers: float | None
    classification: ContextClassification
    reasons: tuple[str, ...]


def _latest_return(series: PriceSeries) -> tuple[date, float]:
    latest = calculate_daily_returns(series)[-1]
    return latest.date, latest.value


def _same_direction(first: float, second: float) -> bool:
    return first * second > 0


def compare_latest_context(
    security: PriceSeries,
    market: PriceSeries,
    sector: PriceSeries,
    peers: Sequence[PriceSeries] = (),
    config: ContextConfig | None = None,
) -> MovementContext:
    """Classify the latest security move relative to aligned benchmarks.

    The classification describes association, not causation. All series must
    have a latest return on the same date to avoid misleading comparisons.
    """

    resolved_config = config or ContextConfig()
    security_date, security_return = _latest_return(security)
    market_date, market_return = _latest_return(market)
    sector_date, sector_return = _latest_return(sector)
    peer_results = [(*_latest_return(peer), peer.ticker) for peer in peers]

    dated_series = [(market.ticker, market_date), (sector.ticker, sector_date)]
    dated_series.extend((ticker, peer_date) for peer_date, _, ticker in peer_results)
    mismatched = [ticker for ticker, result_date in dated_series if result_date != security_date]
    if mismatched:
        raise ValueError(
            "Latest return dates must align; mismatched series: " + ", ".join(mismatched)
        )

    peer_average = fmean(result[1] for result in peer_results) if peer_results else None
    excess_market = security_return - market_return
    excess_sector = security_return - sector_return
    excess_peers = security_return - peer_average if peer_average is not None else None

    market_material = abs(market_return) >= resolved_config.broad_move_threshold
    sector_material = abs(sector_return) >= resolved_config.broad_move_threshold
    market_aligned = (
        market_material
        and _same_direction(security_return, market_return)
        and abs(excess_market) <= resolved_config.similarity_tolerance
    )
    sector_aligned = (
        sector_material
        and _same_direction(security_return, sector_return)
        and abs(excess_sector) <= resolved_config.similarity_tolerance
    )
    peer_aligned = (
        peer_average is not None
        and abs(peer_average) >= resolved_config.broad_move_threshold
        and _same_direction(security_return, peer_average)
        and abs(excess_peers) <= resolved_config.similarity_tolerance
    )
    company_divergence = (
        abs(excess_market) >= resolved_config.company_specific_threshold
        and abs(excess_sector) >= resolved_config.company_specific_threshold
        and (
            excess_peers is None
            or abs(excess_peers) >= resolved_config.company_specific_threshold
        )
    )

    if market_aligned:
        classification = ContextClassification.MARKET_WIDE
        reasons = ["SECURITY_ALIGNED_WITH_MATERIAL_MARKET_MOVE"]
        if sector_aligned:
            reasons.append("SECTOR_ALSO_ALIGNED")
    elif sector_aligned or peer_aligned:
        classification = ContextClassification.SECTOR_WIDE
        reasons = []
        if sector_aligned:
            reasons.append("SECURITY_ALIGNED_WITH_MATERIAL_SECTOR_MOVE")
        if peer_aligned:
            reasons.append("SECURITY_ALIGNED_WITH_PEER_GROUP")
    elif company_divergence:
        classification = ContextClassification.COMPANY_SPECIFIC
        reasons = ["SECURITY_DIVERGED_FROM_MARKET_AND_SECTOR"]
        if excess_peers is not None:
            reasons.append("SECURITY_DIVERGED_FROM_PEER_GROUP")
    else:
        classification = ContextClassification.MIXED
        reasons = ["CONTEXT_SIGNALS_DO_NOT_SUPPORT_A_SINGLE_CLASSIFICATION"]

    return MovementContext(
        date=security_date,
        security_ticker=security.ticker,
        market_ticker=market.ticker,
        sector_ticker=sector.ticker,
        peer_tickers=tuple(peer.ticker for peer in peers),
        security_return=security_return,
        market_return=market_return,
        sector_return=sector_return,
        peer_average_return=peer_average,
        security_excess_vs_market=excess_market,
        security_excess_vs_sector=excess_sector,
        security_excess_vs_peers=excess_peers,
        classification=classification,
        reasons=tuple(reasons),
    )
