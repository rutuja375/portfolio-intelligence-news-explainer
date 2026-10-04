"""Deterministic evaluation metrics for the investigation pipeline."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from .evidence import EvidenceTiming, RankedEvidence
from .explanation import GroundedClaim, GroundedExplanation


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


@dataclass(frozen=True, slots=True)
class BinaryClassificationMetrics:
    """Confusion counts and derived quality metrics for a Boolean decision."""

    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float


@dataclass(frozen=True, slots=True)
class ExplanationQualityMetrics:
    """Citation and support quality for one explanation."""

    claim_count: int
    citation_count: int
    valid_citation_count: int
    citation_correctness: float
    unsupported_claim_count: int
    unsupported_claim_rate: float


def binary_classification_metrics(
    expected: Sequence[bool],
    actual: Sequence[bool],
) -> BinaryClassificationMetrics:
    """Evaluate movement detection or abstention as a binary decision."""

    if len(expected) != len(actual):
        raise ValueError("Expected and actual labels must have the same length")
    if not expected:
        raise ValueError("At least one labeled example is required")

    true_positive = sum(wanted and received for wanted, received in zip(expected, actual))
    true_negative = sum(
        not wanted and not received for wanted, received in zip(expected, actual)
    )
    false_positive = sum(
        not wanted and received for wanted, received in zip(expected, actual)
    )
    false_negative = sum(
        wanted and not received for wanted, received in zip(expected, actual)
    )
    accuracy = _safe_ratio(true_positive + true_negative, len(expected))
    precision = _safe_ratio(true_positive, true_positive + false_positive)
    recall = _safe_ratio(true_positive, true_positive + false_negative)
    f1_score = _safe_ratio(2 * precision * recall, precision + recall)
    return BinaryClassificationMetrics(
        true_positive=true_positive,
        true_negative=true_negative,
        false_positive=false_positive,
        false_negative=false_negative,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
    )


def precision_at_k(
    ranked_evidence: Sequence[RankedEvidence],
    relevant_evidence_ids: Collection[str],
    k: int,
) -> float:
    """Measure the proportion of the first k positions containing relevant evidence."""

    if k <= 0:
        raise ValueError("k must be positive")
    relevant = set(relevant_evidence_ids)
    relevant_retrieved = sum(
        ranked.item.evidence_id in relevant for ranked in ranked_evidence[:k]
    )
    return relevant_retrieved / k


def temporal_validity_rate(ranked_evidence: Sequence[RankedEvidence]) -> float:
    """Measure the share of evidence published before or during the movement."""

    if not ranked_evidence:
        return 0.0
    temporally_valid = sum(
        ranked.timing in (EvidenceTiming.PRE_MOVEMENT, EvidenceTiming.DURING_MOVEMENT)
        for ranked in ranked_evidence
    )
    return temporally_valid / len(ranked_evidence)


def evaluate_claim_support(
    claims: Sequence[GroundedClaim],
    available_evidence_ids: Collection[str],
) -> ExplanationQualityMetrics:
    """Measure citation validity and claims lacking any valid supporting evidence."""

    available = set(available_evidence_ids)
    citations = [citation for claim in claims for citation in claim.citation_ids]
    valid_citation_count = sum(citation in available for citation in citations)
    unsupported_claim_count = sum(
        not any(citation in available for citation in claim.citation_ids)
        for claim in claims
    )
    return ExplanationQualityMetrics(
        claim_count=len(claims),
        citation_count=len(citations),
        valid_citation_count=valid_citation_count,
        citation_correctness=_safe_ratio(valid_citation_count, len(citations)),
        unsupported_claim_count=unsupported_claim_count,
        unsupported_claim_rate=_safe_ratio(unsupported_claim_count, len(claims)),
    )


def evaluate_explanation(
    explanation: GroundedExplanation,
    available_evidence_ids: Collection[str],
) -> ExplanationQualityMetrics:
    """Evaluate a completed explanation against the evidence available to the system."""

    return evaluate_claim_support(explanation.claims, available_evidence_ids)
