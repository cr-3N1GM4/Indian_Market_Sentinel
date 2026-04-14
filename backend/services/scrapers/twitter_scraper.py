# ARCHITECTURE NOTE:
# Twitter scraper uses API v2 with bearer token auth. Dual sentiment
# scoring: VADER for speed (rule-based, zero cost), FinBERT for
# financial domain accuracy. Weighted blend configurable in config.py.
# Mock fallback generates realistic synthetic tweets when API unavailable.

from __future__ import annotations

import asyncio
import os
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import structlog

from backend.config import settings
from backend.db.timescale_client import db
from backend.models.sentiment_models import SentimentLabel

logger = structlog.get_logger(__name__)

# Lazy-load heavy NLP models
_vader = None
_finbert_pipeline = None


def _get_vader():
    global _vader
    if _vader is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _vader = SentimentIntensityAnalyzer()
    return _vader


def _get_finbert():
    global _finbert_pipeline
    if _finbert_pipeline is None:
        try:
            from transformers import pipeline
            _finbert_pipeline = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                truncation=True,
                max_length=512,
            )
        except Exception as e:
            logger.warning("finbert_load_failed", error=str(e))
            _finbert_pipeline = None
    return _finbert_pipeline


def score_sentiment_vader(text: str) -> float:
    """VADER compound score in [-1, +1]."""
    analyzer = _get_vader()
    return analyzer.polarity_scores(text)["compound"]


def score_sentiment_finbert(text: str) -> float:
    """FinBERT score mapped to [-1, +1]. Falls back to VADER on error."""
    pipe = _get_finbert()
    if pipe is None:
        return score_sentiment_vader(text)
    try:
        result = pipe(text[:512])[0]
        label = result["label"].lower()
        score = result["score"]
        if label == "positive":
            return score
        elif label == "negative":
            return -score
        return 0.0
    except Exception:
        return score_sentiment_vader(text)


def compute_blended_score(text: str) -> float:
    """Weighted blend: 0.4 * VADER + 0.6 * FinBERT."""
    w = settings.sentiment
    vader = score_sentiment_vader(text)
    finbert = score_sentiment_finbert(text)
    return w.vader_weight * vader + w.finbert_weight * finbert


def score_to_label(score: float) -> SentimentLabel:
    if score > 0.15:
        return SentimentLabel.POSITIVE
    elif score < -0.15:
        return SentimentLabel.NEGATIVE
    return SentimentLabel.NEUTRAL


def _extract_tickers(text: str, keywords: List[str]) -> List[str]:
    """Extract ticker symbols mentioned in tweet text."""
    tickers = []
    text_upper = text.upper()
    for kw in keywords:
        clean = kw.lstrip("$#")
        if clean in text_upper or kw in text:
            tickers.append(clean)
    return list(set(tickers))


class TwitterScraper:
    """Fetches tweets via Twitter API v2 and scores sentiment."""

    def __init__(self) -> None:
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "")
        self.base_url = "https://api.twitter.com/2/tweets/search/recent"
        self.all_keywords = (
            settings.twitter_keywords.energy
            + settings.twitter_keywords.pharma
            + settings.twitter_keywords.textile
            + settings.twitter_keywords.broad_market
        )

    async def fetch_tweets(self, query: str, max_results: int = 50) -> List[Dict]:
        """Fetch recent tweets matching query. Returns raw tweet data."""
        if not self.bearer_token:
            logger.warning("twitter_no_token", msg="Using mock data")
            return self._generate_mock_tweets(query, max_results)

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,author_id,text",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    self.base_url, headers=headers, params=params
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("retry-after", "60"))
                    logger.warning("twitter_rate_limited", retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    return []

                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])

        except Exception as e:
            logger.error("twitter_fetch_error", error=str(e), query=query)
            return self._generate_mock_tweets(query, max_results)

    async def run_pipeline(self) -> int:
        """Full scraping pipeline: fetch → score → store. Returns count."""
        total_stored = 0

        # Build queries by sector
        queries = [
            " OR ".join(settings.twitter_keywords.energy[:3]),
            " OR ".join(settings.twitter_keywords.pharma[:3]),
            " OR ".join(settings.twitter_keywords.textile[:3]),
            " OR ".join(settings.twitter_keywords.broad_market[:3]),
        ]

        for query in queries:
            tweets = await self.fetch_tweets(query, max_results=50)

            for tweet in tweets:
                text = tweet.get("text", "")
                if not text:
                    continue

                tickers = _extract_tickers(text, self.all_keywords)
                if not tickers:
                    tickers = ["MARKET"]

                score = compute_blended_score(text)
                label = score_to_label(score)

                metrics = tweet.get("public_metrics", {})
                engagement = (
                    metrics.get("like_count", 0)
                    + metrics.get("retweet_count", 0) * 2
                )

                created = tweet.get("created_at")
                if created:
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                else:
                    ts = datetime.now(timezone.utc)

                for ticker in tickers:
                    try:
                        await db.insert_social_sentiment(
                            time=ts,
                            ticker=ticker,
                            source="twitter",
                            raw_text=text[:500],
                            sentiment_score=score,
                            sentiment_label=label.value,
                            engagement_weight=float(engagement),
                            url=f"https://twitter.com/i/status/{tweet.get('id', '')}",
                        )
                        total_stored += 1
                    except Exception as e:
                        logger.error("twitter_store_error", error=str(e), ticker=ticker)

            # Rate limit courtesy
            await asyncio.sleep(2)

        logger.info("twitter_pipeline_complete", tweets_stored=total_stored)
        return total_stored

    # ----------------------------------------------------------
    # MOCK_FALLBACK: generates synthetic tweets for development
    # ----------------------------------------------------------
    def _generate_mock_tweets(self, query: str, count: int) -> List[Dict]:
        """Generate realistic synthetic tweets for testing."""
        templates = [
            "{ticker} looking strong! Target 🎯 {price} 🚀 #NSE #IndianStocks",
            "Bearish on {ticker}, management guidance weak. Avoid for now. #DalalStreet",
            "{ticker} results tomorrow, expecting beat based on channel checks #NSE",
            "FIIs dumping {ticker}, but I think this is a buying opportunity 💎🙌",
            "{ticker} breaking out above key resistance. Volume confirming. #Nifty50",
            "Worried about {ticker} — supply chain issues from China could hit margins",
            "Promoter pledge increase in {ticker} — red flag ⚠️ #IndianStocks",
            "{ticker} dividend yield at 52-week high. Income play? #NSE",
        ]

        tickers = ["RELIANCE", "SUNPHARMA", "ONGC", "DRREDDY", "PAGEIND", "NTPC"]
        mock_tweets = []

        for i in range(min(count, 20)):
            ticker = random.choice(tickers)
            template = random.choice(templates)
            text = template.format(ticker=ticker, price=random.randint(500, 5000))

            mock_tweets.append({
                "id": f"mock_{i}_{random.randint(1000, 9999)}",
                "text": text,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "public_metrics": {
                    "like_count": random.randint(1, 500),
                    "retweet_count": random.randint(0, 100),
                    "reply_count": random.randint(0, 50),
                },
            })

        return mock_tweets


# Module-level instance
twitter_scraper = TwitterScraper()
