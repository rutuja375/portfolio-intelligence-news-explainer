"""Alpha Vantage adapter for timestamped financial-news evidence."""

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import isfinite
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from ..evidence import EvidenceItem


class AlphaVantageNewsError(RuntimeError):
    """Raised when Alpha Vantage cannot provide a trustworthy news response."""


JsonTransport = Callable[[Mapping[str, str], float], Mapping[str, Any]]


class AlphaVantageNewsProvider:
    """Retrieve and normalize Alpha Vantage News & Sentiment results."""

    endpoint = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str,
        transport: JsonTransport | None = None,
        timeout_seconds: float = 10.0,
        result_limit: int = 200,
        minimum_ticker_relevance: float = 0.5,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Alpha Vantage API key cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if not 1 <= result_limit <= 1000:
            raise ValueError("Result limit must be between 1 and 1000")
        if not 0 <= minimum_ticker_relevance <= 1:
            raise ValueError("Minimum ticker relevance must be between 0 and 1")
        self._api_key = api_key.strip()
        self._transport = transport or self._request_json
        self._timeout_seconds = timeout_seconds
        self._result_limit = result_limit
        self._minimum_ticker_relevance = minimum_ticker_relevance

    def _request_json(
        self, params: Mapping[str, str], timeout_seconds: float
    ) -> Mapping[str, Any]:
        url = f"{self.endpoint}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
                payload = json.load(response)
        except Exception as error:
            raise AlphaVantageNewsError("Alpha Vantage news request failed") from error
        if not isinstance(payload, Mapping):
            raise AlphaVantageNewsError("Alpha Vantage returned an invalid JSON response")
        return payload

    def search(
        self,
        ticker: str,
        published_from: datetime,
        published_to: datetime,
    ) -> tuple[EvidenceItem, ...]:
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker cannot be empty")
        for value, label in (
            (published_from, "Published from"),
            (published_to, "Published to"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if published_from > published_to:
            raise ValueError("Published-from time must not be after published-to time")

        start_utc = published_from.astimezone(timezone.utc)
        end_utc = published_to.astimezone(timezone.utc)
        # Alpha Vantage accepts minute precision. Round the remote upper bound up,
        # then apply our exact inclusive window after parsing each result.
        remote_end = end_utc
        if end_utc.second or end_utc.microsecond:
            remote_end = end_utc.replace(second=0, microsecond=0) + timedelta(minutes=1)
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": normalized_ticker,
            "time_from": start_utc.strftime("%Y%m%dT%H%M"),
            "time_to": remote_end.strftime("%Y%m%dT%H%M"),
            "sort": "RELEVANCE",
            "limit": str(self._result_limit),
            "apikey": self._api_key,
        }
        try:
            payload = self._transport(params, self._timeout_seconds)
        except AlphaVantageNewsError:
            raise
        except Exception as error:
            raise AlphaVantageNewsError("Alpha Vantage news request failed") from error

        for error_key in ("Error Message", "Note", "Information"):
            if payload.get(error_key):
                raise AlphaVantageNewsError(str(payload[error_key]))
        feed = payload.get("feed")
        if not isinstance(feed, list):
            raise AlphaVantageNewsError("Alpha Vantage response did not contain a news feed")

        by_url: dict[str, EvidenceItem] = {}
        for raw_item in feed:
            item = self._normalize_item(raw_item, normalized_ticker)
            if item is None:
                continue
            if item.semantic_relevance < self._minimum_ticker_relevance:
                continue
            if start_utc <= item.published_at <= end_utc:
                existing = by_url.get(item.url)
                if existing is None or item.semantic_relevance > existing.semantic_relevance:
                    by_url[item.url] = item
        ordered = sorted(by_url.values(), key=lambda item: item.published_at)
        return tuple(ordered[: self._result_limit])

    @staticmethod
    def _normalize_item(
        raw_item: Any, requested_ticker: str
    ) -> EvidenceItem | None:
        if not isinstance(raw_item, Mapping):
            raise AlphaVantageNewsError("Alpha Vantage returned a malformed news item")
        try:
            title = str(raw_item["title"]).strip()
            url = str(raw_item["url"]).strip()
            source = str(raw_item["source"]).strip()
            published_at = datetime.strptime(
                str(raw_item["time_published"]), "%Y%m%dT%H%M%S"
            ).replace(tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError) as error:
            raise AlphaVantageNewsError(
                "Alpha Vantage returned a news item with invalid required fields"
            ) from error

        ticker_signals = raw_item.get("ticker_sentiment", [])
        related_tickers = []
        requested_signal: Mapping[str, Any] | None = None
        if isinstance(ticker_signals, list):
            for signal in ticker_signals:
                if not isinstance(signal, Mapping):
                    continue
                symbol = str(signal.get("ticker", "")).strip().upper()
                if symbol:
                    related_tickers.append(symbol)
                if symbol == requested_ticker:
                    requested_signal = signal
        # Provider-side ticker filtering is not sufficient: Alpha Vantage can
        # include broad-feed results. Require its item-level metadata to name
        # the requested security before admitting an article as evidence.
        if requested_signal is None:
            return None

        semantic_relevance = _unit_score(
            None if requested_signal is None else requested_signal.get("relevance_score"),
            default=0.5,
        )
        topics = raw_item.get("topics", [])
        topic_scores = (
            [_unit_score(topic.get("relevance_score"), default=0.0) for topic in topics
             if isinstance(topic, Mapping)]
            if isinstance(topics, list)
            else []
        )
        financial_relevance = max(topic_scores, default=semantic_relevance)
        sentiment = _sentiment_score(
            None
            if requested_signal is None
            else requested_signal.get("ticker_sentiment_score")
        )
        summary = str(raw_item.get("summary", "")).strip()
        evidence_id = "av-" + sha256(url.encode("utf-8")).hexdigest()[:16]
        return EvidenceItem(
            evidence_id=evidence_id,
            title=title,
            summary=summary,
            url=url,
            source=source,
            published_at=published_at,
            related_tickers=tuple(related_tickers),
            semantic_relevance=semantic_relevance,
            financial_relevance=financial_relevance,
            # Source quality is deliberately neutral until we have an explicit,
            # auditable source-quality policy of our own.
            source_quality=0.5,
            sentiment=sentiment,
        )


def _unit_score(raw_value: Any, default: float) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default
    if not isfinite(value):
        return default
    return min(1.0, max(0.0, value))


def _sentiment_score(raw_value: Any) -> float | None:
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    if not isfinite(value):
        return None
    return min(1.0, max(-1.0, value))
