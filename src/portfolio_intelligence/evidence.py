"""Provider contracts, temporal validation and transparent evidence ranking."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _validate_unit_interval(value: float, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be between 0 and 1")


class EvidenceTiming(str, Enum):
    """Position of publication time relative to the movement window."""

    PRE_MOVEMENT = "PRE_MOVEMENT"
    DURING_MOVEMENT = "DURING_MOVEMENT"
    POST_MOVEMENT = "POST_MOVEMENT"


@dataclass(frozen=True, slots=True)
class EvidenceWindow:
    """Timezone-aware movement interval used for temporal classification."""

    movement_start: datetime
    movement_end: datetime

    def __post_init__(self) -> None:
        _require_aware(self.movement_start, "Movement start")
        _require_aware(self.movement_end, "Movement end")
        if self.movement_start > self.movement_end:
            raise ValueError("Movement start must not be after movement end")


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Normalized article or filing plus independently calculated ranking signals."""

    evidence_id: str
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    related_tickers: tuple[str, ...]
    semantic_relevance: float
    financial_relevance: float
    source_quality: float
    sentiment: float | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("Evidence ID cannot be empty")
        if not self.title.strip():
            raise ValueError("Evidence title cannot be empty")
        if not self.url.strip():
            raise ValueError("Evidence URL cannot be empty")
        if not self.source.strip():
            raise ValueError("Evidence source cannot be empty")
        _require_aware(self.published_at, "Publication time")
        if not self.related_tickers:
            raise ValueError("Evidence must reference at least one ticker")
        normalized_tickers = tuple(
            dict.fromkeys(ticker.strip().upper() for ticker in self.related_tickers if ticker.strip())
        )
        if not normalized_tickers:
            raise ValueError("Evidence must reference at least one non-empty ticker")
        object.__setattr__(self, "related_tickers", normalized_tickers)
        _validate_unit_interval(self.semantic_relevance, "Semantic relevance")
        _validate_unit_interval(self.financial_relevance, "Financial relevance")
        _validate_unit_interval(self.source_quality, "Source quality")
        if self.sentiment is not None and not -1 <= self.sentiment <= 1:
            raise ValueError("Sentiment must be between -1 and 1")


class NewsProvider(Protocol):
    """Contract implemented by news, filing or announcement sources."""

    def search(
        self,
        ticker: str,
        published_from: datetime,
        published_to: datetime,
    ) -> tuple[EvidenceItem, ...]:
        """Return normalized evidence in the inclusive publication window."""


class InMemoryNewsProvider:
    """Deterministic evidence source for tests and offline development."""

    def __init__(self, items: Iterable[EvidenceItem]) -> None:
        self._items = tuple(items)
        identifiers = [item.evidence_id for item in self._items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Evidence IDs must be unique")

    def search(
        self,
        ticker: str,
        published_from: datetime,
        published_to: datetime,
    ) -> tuple[EvidenceItem, ...]:
        _require_aware(published_from, "Published from")
        _require_aware(published_to, "Published to")
        if published_from > published_to:
            raise ValueError("Published-from time must not be after published-to time")
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker cannot be empty")

        return tuple(
            sorted(
                (
                    item
                    for item in self._items
                    if normalized_ticker in item.related_tickers
                    and published_from <= item.published_at <= published_to
                ),
                key=lambda item: item.published_at,
            )
        )


@dataclass(frozen=True, slots=True)
class EvidenceRankingConfig:
    """Weights and safeguards used to calculate the composite evidence score."""

    semantic_weight: float = 0.35
    temporal_weight: float = 0.30
    financial_weight: float = 0.20
    source_quality_weight: float = 0.15
    post_movement_penalty: float = 0.65
    temporal_decay_hours: float = 24.0

    def __post_init__(self) -> None:
        weights = (
            self.semantic_weight,
            self.temporal_weight,
            self.financial_weight,
            self.source_quality_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("Evidence-ranking weights cannot be negative")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("Evidence-ranking weights must sum to 1.0")
        if not 0 < self.post_movement_penalty <= 1:
            raise ValueError("Post-movement penalty must be greater than 0 and at most 1")
        if self.temporal_decay_hours <= 0:
            raise ValueError("Temporal decay hours must be positive")


@dataclass(frozen=True, slots=True)
class RankedEvidence:
    """Evidence item enriched with timing, score and auditable ranking reasons."""

    item: EvidenceItem
    timing: EvidenceTiming
    temporal_relevance: float
    combined_score: float
    ranking_reasons: tuple[str, ...]


def classify_evidence_timing(
    published_at: datetime,
    window: EvidenceWindow,
) -> EvidenceTiming:
    """Classify publication relative to the detected movement interval."""

    _require_aware(published_at, "Publication time")
    if published_at < window.movement_start:
        return EvidenceTiming.PRE_MOVEMENT
    if published_at <= window.movement_end:
        return EvidenceTiming.DURING_MOVEMENT
    return EvidenceTiming.POST_MOVEMENT


def _temporal_relevance(
    published_at: datetime,
    timing: EvidenceTiming,
    window: EvidenceWindow,
    decay_hours: float,
) -> float:
    if timing is EvidenceTiming.DURING_MOVEMENT:
        return 1.0
    boundary = (
        window.movement_start
        if timing is EvidenceTiming.PRE_MOVEMENT
        else window.movement_end
    )
    distance_hours = abs((published_at - boundary).total_seconds()) / 3600
    return 1 / (1 + distance_hours / decay_hours)


def rank_evidence(
    items: Sequence[EvidenceItem],
    window: EvidenceWindow,
    config: EvidenceRankingConfig | None = None,
    limit: int | None = None,
) -> tuple[RankedEvidence, ...]:
    """Rank evidence using relevance, time, financial materiality and source quality."""

    if limit is not None and limit <= 0:
        raise ValueError("Evidence limit must be positive")
    resolved_config = config or EvidenceRankingConfig()
    ranked = []
    for item in items:
        timing = classify_evidence_timing(item.published_at, window)
        temporal_relevance = _temporal_relevance(
            item.published_at,
            timing,
            window,
            resolved_config.temporal_decay_hours,
        )
        score = (
            item.semantic_relevance * resolved_config.semantic_weight
            + temporal_relevance * resolved_config.temporal_weight
            + item.financial_relevance * resolved_config.financial_weight
            + item.source_quality * resolved_config.source_quality_weight
        )
        reasons = [f"TIMING_{timing.value}"]
        if timing is EvidenceTiming.POST_MOVEMENT:
            score *= resolved_config.post_movement_penalty
            reasons.append("POST_MOVEMENT_EVIDENCE_PENALIZED")
        if item.semantic_relevance >= 0.8:
            reasons.append("HIGH_SEMANTIC_RELEVANCE")
        if item.financial_relevance >= 0.8:
            reasons.append("HIGH_FINANCIAL_RELEVANCE")
        if item.source_quality >= 0.8:
            reasons.append("HIGH_SOURCE_QUALITY")
        ranked.append(
            RankedEvidence(
                item=item,
                timing=timing,
                temporal_relevance=temporal_relevance,
                combined_score=score,
                ranking_reasons=tuple(reasons),
            )
        )

    ordered = tuple(
        sorted(
            ranked,
            key=lambda evidence: (
                -evidence.combined_score,
                evidence.item.published_at,
                evidence.item.evidence_id,
            ),
        )
    )
    return ordered[:limit] if limit is not None else ordered
