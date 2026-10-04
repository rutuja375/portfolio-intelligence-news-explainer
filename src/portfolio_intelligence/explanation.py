"""Deterministic safeguards for grounded explanations and abstention."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from .evidence import EvidenceTiming, RankedEvidence


class ExplanationConfidence(StrEnum):
    """Evidence-based confidence in the explanation, not market certainty."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class ExplanationPolicy:
    """Minimum evidence requirements applied before any LLM synthesis."""

    minimum_evidence_count: int = 2
    maximum_evidence_count: int = 5
    minimum_evidence_score: float = 0.60
    high_confidence_score: float = 0.80
    high_confidence_evidence_count: int = 3
    require_pre_or_during_evidence: bool = True
    sentiment_conflict_threshold: float = 0.30

    def __post_init__(self) -> None:
        if self.minimum_evidence_count < 1:
            raise ValueError("Minimum evidence count must be at least 1")
        if self.maximum_evidence_count < self.minimum_evidence_count:
            raise ValueError("Maximum evidence count cannot be below the minimum")
        if self.high_confidence_evidence_count < self.minimum_evidence_count:
            raise ValueError("High-confidence evidence count cannot be below the minimum")
        for value, name in (
            (self.minimum_evidence_score, "Minimum evidence score"),
            (self.high_confidence_score, "High-confidence score"),
            (self.sentiment_conflict_threshold, "Sentiment-conflict threshold"),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.high_confidence_score < self.minimum_evidence_score:
            raise ValueError("High-confidence score cannot be below the minimum score")


@dataclass(frozen=True, slots=True)
class ExplanationReadiness:
    """Selected evidence and the deterministic decision to explain or abstain."""

    selected_evidence: tuple[RankedEvidence, ...]
    confidence: ExplanationConfidence
    should_abstain: bool
    conflict_detected: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    """Material natural-language claim and the evidence IDs supporting it."""

    text: str
    citation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Grounded claim text cannot be empty")
        normalized_citations = tuple(dict.fromkeys(self.citation_ids))
        if not normalized_citations or any(not citation.strip() for citation in normalized_citations):
            raise ValueError("Every grounded claim must include at least one citation")
        object.__setattr__(self, "citation_ids", normalized_citations)


@dataclass(frozen=True, slots=True)
class GroundedExplanation:
    """Validated explanation or explicit abstention returned to the user."""

    summary: str
    claims: tuple[GroundedClaim, ...]
    confidence: ExplanationConfidence
    abstained: bool
    evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...]


def _detect_directional_conflict(
    evidence: Sequence[RankedEvidence],
    threshold: float,
) -> bool:
    sentiments = [
        ranked.item.sentiment
        for ranked in evidence
        if ranked.item.sentiment is not None
    ]
    has_positive = any(value >= threshold for value in sentiments)
    has_negative = any(value <= -threshold for value in sentiments)
    return has_positive and has_negative


def assess_explanation_readiness(
    evidence: Sequence[RankedEvidence],
    policy: ExplanationPolicy | None = None,
) -> ExplanationReadiness:
    """Select eligible evidence and determine confidence or abstention."""

    resolved_policy = policy or ExplanationPolicy()
    selected = tuple(
        ranked
        for ranked in evidence
        if ranked.combined_score >= resolved_policy.minimum_evidence_score
    )[: resolved_policy.maximum_evidence_count]
    conflict_detected = _detect_directional_conflict(
        selected, resolved_policy.sentiment_conflict_threshold
    )
    reasons = []

    if len(selected) < resolved_policy.minimum_evidence_count:
        reasons.append("INSUFFICIENT_ELIGIBLE_EVIDENCE")
    has_contemporaneous = any(
        ranked.timing in (EvidenceTiming.PRE_MOVEMENT, EvidenceTiming.DURING_MOVEMENT)
        for ranked in selected
    )
    if resolved_policy.require_pre_or_during_evidence and not has_contemporaneous:
        reasons.append("NO_PRE_OR_DURING_MOVEMENT_EVIDENCE")
    if conflict_detected:
        reasons.append("CONFLICTING_DIRECTIONAL_EVIDENCE")

    should_abstain = any(
        reason in {"INSUFFICIENT_ELIGIBLE_EVIDENCE", "NO_PRE_OR_DURING_MOVEMENT_EVIDENCE"}
        for reason in reasons
    )
    if should_abstain:
        confidence = ExplanationConfidence.LOW
    else:
        average_score = fmean(ranked.combined_score for ranked in selected)
        confidence = (
            ExplanationConfidence.HIGH
            if len(selected) >= resolved_policy.high_confidence_evidence_count
            and average_score >= resolved_policy.high_confidence_score
            else ExplanationConfidence.MEDIUM
        )
        if conflict_detected:
            confidence = (
                ExplanationConfidence.MEDIUM
                if confidence is ExplanationConfidence.HIGH
                else ExplanationConfidence.LOW
            )
            reasons.append("CONFIDENCE_REDUCED_FOR_CONFLICT")

    reasons.append(f"SELECTED_EVIDENCE_COUNT_{len(selected)}")
    return ExplanationReadiness(
        selected_evidence=selected,
        confidence=confidence,
        should_abstain=should_abstain,
        conflict_detected=conflict_detected,
        reasons=tuple(reasons),
    )


def build_grounded_explanation(
    summary: str,
    claims: Sequence[GroundedClaim],
    readiness: ExplanationReadiness,
) -> GroundedExplanation:
    """Validate that every material claim cites only selected evidence."""

    if readiness.should_abstain:
        raise ValueError("Cannot build an explanation when policy requires abstention")
    if not summary.strip():
        raise ValueError("Explanation summary cannot be empty")
    if not claims:
        raise ValueError("Explanation must contain at least one grounded claim")

    selected_ids = {
        ranked.item.evidence_id for ranked in readiness.selected_evidence
    }
    cited_ids = {citation for claim in claims for citation in claim.citation_ids}
    unknown_ids = sorted(cited_ids - selected_ids)
    if unknown_ids:
        raise ValueError(
            "Claims cite evidence that was not selected: " + ", ".join(unknown_ids)
        )

    return GroundedExplanation(
        summary=summary.strip(),
        claims=tuple(claims),
        confidence=readiness.confidence,
        abstained=False,
        evidence_ids=tuple(
            ranked.item.evidence_id for ranked in readiness.selected_evidence
        ),
        reasons=readiness.reasons,
    )


def build_abstention(readiness: ExplanationReadiness) -> GroundedExplanation:
    """Return a standard, transparent response when evidence is insufficient."""

    if not readiness.should_abstain:
        raise ValueError("Abstention is only valid when the readiness policy requires it")
    return GroundedExplanation(
        summary=(
            "Available sources do not provide sufficient temporally appropriate evidence "
            "to support a grounded explanation for this movement."
        ),
        claims=(),
        confidence=ExplanationConfidence.LOW,
        abstained=True,
        evidence_ids=tuple(
            ranked.item.evidence_id for ranked in readiness.selected_evidence
        ),
        reasons=readiness.reasons,
    )
