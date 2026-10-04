"""Use one Alpha Vantage request to verify the local news configuration."""

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from portfolio_intelligence import AlphaVantageNewsProvider


def main() -> None:
    load_dotenv()
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Add ALPHA_VANTAGE_API_KEY to the local .env file first")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=3)
    articles = AlphaVantageNewsProvider(api_key, result_limit=10).search(
        "NVDA", start, end
    )
    print(f"Received {len(articles)} timestamped NVDA article(s).")
    strongest = sorted(
        articles,
        key=lambda article: article.semantic_relevance,
        reverse=True,
    )
    for article in strongest[:3]:
        print(
            f"- relevance {article.semantic_relevance:.3f} | "
            f"{article.published_at.isoformat()} | {article.source} | {article.title}"
        )


if __name__ == "__main__":
    main()
