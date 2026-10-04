import unittest
from datetime import datetime, timezone

from portfolio_intelligence import (
    EvidenceItem,
    EvidenceTiming,
    ExplanationConfidence,
    GroundedClaim,
    RankedEvidence,
    assess_explanation_readiness,
    build_abstention,
    build_grounded_explanation,
)


PUBLISHED_AT = datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc)


def ranked(
    evidence_id: str,
    score: float,
    *,
    timing: EvidenceTiming = EvidenceTiming.PRE_MOVEMENT,
    sentiment: float | None = -0.5,
) -> RankedEvidence:
    item = EvidenceItem(
        evidence_id=evidence_id,
        title=f"Evidence {evidence_id}",
        summary="Synthetic evidence for explanation safeguards.",
        url=f"https://example.com/{evidence_id}",
        source="Example Wire",
        published_at=PUBLISHED_AT,
        related_tickers=("NVDA",),
        semantic_relevance=0.9,
        financial_relevance=0.9,
        source_quality=0.9,
        sentiment=sentiment,
    )
    return RankedEvidence(
        item=item,
        timing=timing,
        temporal_relevance=0.9,
        combined_score=score,
        ranking_reasons=(f"TIMING_{timing.value}",),
    )


class ExplanationTests(unittest.TestCase):
    def test_abstains_when_too_few_items_clear_the_score_threshold(self) -> None:
        readiness = assess_explanation_readiness(
            (ranked("eligible", 0.8), ranked("weak", 0.4))
        )

        self.assertTrue(readiness.should_abstain)
        self.assertEqual(readiness.confidence, ExplanationConfidence.LOW)
        self.assertIn("INSUFFICIENT_ELIGIBLE_EVIDENCE", readiness.reasons)

    def test_abstains_when_all_selected_evidence_is_post_movement(self) -> None:
        readiness = assess_explanation_readiness(
            (
                ranked("post-1", 0.8, timing=EvidenceTiming.POST_MOVEMENT),
                ranked("post-2", 0.75, timing=EvidenceTiming.POST_MOVEMENT),
            )
        )

        self.assertTrue(readiness.should_abstain)
        self.assertIn("NO_PRE_OR_DURING_MOVEMENT_EVIDENCE", readiness.reasons)

    def test_assigns_high_confidence_to_multiple_strong_sources(self) -> None:
        readiness = assess_explanation_readiness(
            (ranked("one", 0.9), ranked("two", 0.85), ranked("three", 0.82))
        )

        self.assertFalse(readiness.should_abstain)
        self.assertEqual(readiness.confidence, ExplanationConfidence.HIGH)

    def test_directional_conflict_reduces_confidence(self) -> None:
        readiness = assess_explanation_readiness(
            (
                ranked("negative", 0.9, sentiment=-0.7),
                ranked("positive", 0.86, sentiment=0.7),
                ranked("neutral", 0.84, sentiment=0.0),
            )
        )

        self.assertTrue(readiness.conflict_detected)
        self.assertEqual(readiness.confidence, ExplanationConfidence.MEDIUM)
        self.assertIn("CONFIDENCE_REDUCED_FOR_CONFLICT", readiness.reasons)

    def test_builds_explanation_when_claims_cite_selected_evidence(self) -> None:
        readiness = assess_explanation_readiness(
            (ranked("filing", 0.9), ranked("wire", 0.8))
        )
        claims = (
            GroundedClaim(
                "The company released updated guidance before the movement.",
                ("filing",),
            ),
            GroundedClaim(
                "Contemporaneous reporting discussed the revised outlook.",
                ("wire", "filing"),
            ),
        )

        explanation = build_grounded_explanation(
            "Selected evidence identifies a potential company-specific factor.",
            claims,
            readiness,
        )

        self.assertFalse(explanation.abstained)
        self.assertEqual(explanation.evidence_ids, ("filing", "wire"))

    def test_rejects_claim_citing_unselected_evidence(self) -> None:
        readiness = assess_explanation_readiness(
            (ranked("selected-1", 0.9), ranked("selected-2", 0.8))
        )

        with self.assertRaisesRegex(ValueError, "not selected"):
            build_grounded_explanation(
                "Draft summary",
                (GroundedClaim("Unsupported claim", ("unknown",)),),
                readiness,
            )

    def test_builds_standard_abstention(self) -> None:
        readiness = assess_explanation_readiness((ranked("only", 0.8),))

        explanation = build_abstention(readiness)

        self.assertTrue(explanation.abstained)
        self.assertEqual(explanation.confidence, ExplanationConfidence.LOW)
        self.assertEqual(explanation.claims, ())


if __name__ == "__main__":
    unittest.main()
