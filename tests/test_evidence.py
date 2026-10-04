import unittest
from datetime import datetime, timedelta, timezone

from portfolio_intelligence import (
    EvidenceItem,
    EvidenceRankingConfig,
    EvidenceTiming,
    EvidenceWindow,
    InMemoryNewsProvider,
    classify_evidence_timing,
    rank_evidence,
)


UTC = timezone.utc
START = datetime(2026, 1, 6, 15, 30, tzinfo=UTC)
END = datetime(2026, 1, 6, 15, 45, tzinfo=UTC)
WINDOW = EvidenceWindow(START, END)


def evidence(
    evidence_id: str,
    published_at: datetime,
    *,
    ticker: str = "NVDA",
    semantic: float = 0.8,
    financial: float = 0.8,
    quality: float = 0.8,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        title=f"Evidence {evidence_id}",
        summary="Synthetic evidence used for deterministic testing.",
        url=f"https://example.com/{evidence_id}",
        source="Example Wire",
        published_at=published_at,
        related_tickers=(ticker,),
        semantic_relevance=semantic,
        financial_relevance=financial,
        source_quality=quality,
        sentiment=-0.4,
    )


class EvidenceTests(unittest.TestCase):
    def test_requires_timezone_aware_publication_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            evidence("naive", datetime(2026, 1, 6, 15, 0))

    def test_provider_filters_by_ticker_and_inclusive_window(self) -> None:
        before = evidence("before", START - timedelta(hours=2))
        first = evidence("first", START)
        second = evidence("second", END)
        unrelated = evidence("other", START, ticker="MSFT")
        provider = InMemoryNewsProvider((second, unrelated, before, first))

        results = provider.search(" nvda ", START, END)

        self.assertEqual([item.evidence_id for item in results], ["first", "second"])

    def test_classifies_pre_during_and_post_movement_evidence(self) -> None:
        self.assertEqual(
            classify_evidence_timing(START - timedelta(seconds=1), WINDOW),
            EvidenceTiming.PRE_MOVEMENT,
        )
        self.assertEqual(
            classify_evidence_timing(START, WINDOW), EvidenceTiming.DURING_MOVEMENT
        )
        self.assertEqual(
            classify_evidence_timing(END, WINDOW), EvidenceTiming.DURING_MOVEMENT
        )
        self.assertEqual(
            classify_evidence_timing(END + timedelta(seconds=1), WINDOW),
            EvidenceTiming.POST_MOVEMENT,
        )

    def test_ranks_strong_relevant_evidence_above_weak_mentions(self) -> None:
        strong = evidence(
            "strong",
            START - timedelta(hours=1),
            semantic=0.95,
            financial=0.95,
            quality=0.9,
        )
        weak = evidence(
            "weak",
            START + timedelta(minutes=5),
            semantic=0.2,
            financial=0.1,
            quality=0.4,
        )

        results = rank_evidence((weak, strong), WINDOW)

        self.assertEqual(results[0].item.evidence_id, "strong")
        self.assertIn("HIGH_SOURCE_QUALITY", results[0].ranking_reasons)

    def test_penalizes_equivalent_post_movement_reporting(self) -> None:
        pre = evidence("pre", START - timedelta(hours=1))
        post = evidence("post", END + timedelta(hours=1))

        results = rank_evidence((post, pre), WINDOW)
        by_id = {result.item.evidence_id: result for result in results}

        self.assertGreater(by_id["pre"].combined_score, by_id["post"].combined_score)
        self.assertIn(
            "POST_MOVEMENT_EVIDENCE_PENALIZED", by_id["post"].ranking_reasons
        )

    def test_applies_result_limit_after_ranking(self) -> None:
        items = (
            evidence("low", START, semantic=0.2),
            evidence("high", START, semantic=0.9),
            evidence("medium", START, semantic=0.6),
        )

        results = rank_evidence(items, WINDOW, limit=2)

        self.assertEqual([result.item.evidence_id for result in results], ["high", "medium"])

    def test_rejects_ranking_weights_that_do_not_sum_to_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            EvidenceRankingConfig(
                semantic_weight=0.5,
                temporal_weight=0.5,
                financial_weight=0.5,
                source_quality_weight=0.5,
            )


if __name__ == "__main__":
    unittest.main()
