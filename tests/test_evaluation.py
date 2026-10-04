import unittest
from datetime import datetime, timezone

from portfolio_intelligence import (
    EvidenceItem,
    EvidenceTiming,
    GroundedClaim,
    RankedEvidence,
    binary_classification_metrics,
    evaluate_claim_support,
    precision_at_k,
    temporal_validity_rate,
)


def ranked(evidence_id: str, timing: EvidenceTiming) -> RankedEvidence:
    item = EvidenceItem(
        evidence_id=evidence_id,
        title=f"Evidence {evidence_id}",
        summary="Synthetic evaluation evidence.",
        url=f"https://example.com/{evidence_id}",
        source="Example Wire",
        published_at=datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc),
        related_tickers=("NVDA",),
        semantic_relevance=0.8,
        financial_relevance=0.8,
        source_quality=0.8,
    )
    return RankedEvidence(
        item=item,
        timing=timing,
        temporal_relevance=0.9,
        combined_score=0.8,
        ranking_reasons=(f"TIMING_{timing.value}",),
    )


class EvaluationTests(unittest.TestCase):
    def test_calculates_binary_classification_metrics(self) -> None:
        metrics = binary_classification_metrics(
            expected=(True, True, False, False),
            actual=(True, False, True, False),
        )

        self.assertEqual(metrics.true_positive, 1)
        self.assertEqual(metrics.true_negative, 1)
        self.assertEqual(metrics.false_positive, 1)
        self.assertEqual(metrics.false_negative, 1)
        self.assertAlmostEqual(metrics.accuracy, 0.5)
        self.assertAlmostEqual(metrics.precision, 0.5)
        self.assertAlmostEqual(metrics.recall, 0.5)
        self.assertAlmostEqual(metrics.f1_score, 0.5)

    def test_rejects_empty_binary_evaluation(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one"):
            binary_classification_metrics((), ())

    def test_precision_at_k_uses_requested_rank_positions(self) -> None:
        evidence = (
            ranked("relevant-1", EvidenceTiming.PRE_MOVEMENT),
            ranked("irrelevant", EvidenceTiming.DURING_MOVEMENT),
            ranked("relevant-2", EvidenceTiming.POST_MOVEMENT),
        )

        result = precision_at_k(evidence, {"relevant-1", "relevant-2"}, k=3)

        self.assertAlmostEqual(result, 2 / 3)

    def test_precision_at_k_penalizes_unfilled_positions(self) -> None:
        evidence = (ranked("relevant", EvidenceTiming.PRE_MOVEMENT),)

        result = precision_at_k(evidence, {"relevant"}, k=3)

        self.assertAlmostEqual(result, 1 / 3)

    def test_temporal_validity_excludes_post_movement_evidence(self) -> None:
        evidence = (
            ranked("pre", EvidenceTiming.PRE_MOVEMENT),
            ranked("during", EvidenceTiming.DURING_MOVEMENT),
            ranked("post", EvidenceTiming.POST_MOVEMENT),
        )

        self.assertAlmostEqual(temporal_validity_rate(evidence), 2 / 3)
        self.assertEqual(temporal_validity_rate(()), 0.0)

    def test_evaluates_citation_correctness_and_unsupported_claims(self) -> None:
        claims = (
            GroundedClaim("Supported claim", ("valid-1", "invalid")),
            GroundedClaim("Unsupported claim", ("missing",)),
        )

        metrics = evaluate_claim_support(claims, {"valid-1", "valid-2"})

        self.assertEqual(metrics.citation_count, 3)
        self.assertEqual(metrics.valid_citation_count, 1)
        self.assertAlmostEqual(metrics.citation_correctness, 1 / 3)
        self.assertEqual(metrics.unsupported_claim_count, 1)
        self.assertAlmostEqual(metrics.unsupported_claim_rate, 0.5)

    def test_empty_claim_set_is_not_reported_as_perfect_citation_quality(self) -> None:
        metrics = evaluate_claim_support((), {"valid"})

        self.assertEqual(metrics.citation_correctness, 0.0)
        self.assertEqual(metrics.unsupported_claim_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
