import unittest

from portfolio_intelligence import ContextClassification, EvidenceTiming
from portfolio_intelligence.demo import build_demo_investigation


class DemoInvestigationTests(unittest.TestCase):
    def test_demo_runs_through_complete_offline_pipeline(self) -> None:
        demo = build_demo_investigation()

        self.assertTrue(demo.movement.is_abnormal)
        self.assertEqual(demo.context.classification, ContextClassification.COMPANY_SPECIFIC)
        self.assertTrue(demo.event.investigation_required)
        self.assertFalse(demo.readiness.should_abstain)
        self.assertFalse(demo.explanation.abstained)

    def test_demo_preserves_temporal_evidence_order_and_penalty(self) -> None:
        demo = build_demo_investigation()

        self.assertEqual(demo.ranked_evidence[0].timing, EvidenceTiming.PRE_MOVEMENT)
        post = next(
            item
            for item in demo.ranked_evidence
            if item.timing is EvidenceTiming.POST_MOVEMENT
        )
        self.assertIn("POST_MOVEMENT_EVIDENCE_PENALIZED", post.ranking_reasons)

    def test_demo_claims_only_cite_selected_evidence(self) -> None:
        demo = build_demo_investigation()
        selected_ids = {
            item.item.evidence_id for item in demo.readiness.selected_evidence
        }

        for claim in demo.explanation.claims:
            self.assertTrue(set(claim.citation_ids).issubset(selected_ids))


if __name__ == "__main__":
    unittest.main()
