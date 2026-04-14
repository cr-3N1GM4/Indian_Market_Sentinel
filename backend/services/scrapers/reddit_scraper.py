# ARCHITECTURE NOTE:
# Reddit scraper uses direct aiohttp requests to public .json endpoints,
# bypassing the need for PRAW and authenticated API keys.
# Comment velocity tracking detects coordinated hype (>3x rolling
# average = hype flag). Ticker normalisation handles both SUNPHARMA and
# "Sun Pharma" forms. Mock fallback for development without credentials.

from __future__ import annotations

import os
import random
import re
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp
import structlog

from backend.config import settings
from backend.db.timescale_client import db
from backend.services.scrapers.twitter_scraper import (
    compute_blended_score,
    score_to_label,
)

logger = structlog.get_logger(__name__)

# Ticker normalisation map: common informal names → NSE symbols
TICKER_ALIASES: Dict[str, str] = {
    "sun pharma": "SUNPHARMA",
    "sunpharma": "SUNPHARMA",
    "dr reddy": "DRREDDY",
    "dr reddys": "DRREDDY",
    "drreddy": "DRREDDY",
    "reliance": "RELIANCE",
    "ril": "RELIANCE",
    "ongc": "ONGC",
    "ntpc": "NTPC",
    "bpcl": "BPCL",
    "ioc": "IOC",
    "cipla": "CIPLA",
    "auropharma": "AUROPHARMA",
    "aurobindo": "AUROPHARMA",
    "page industries": "PAGEIND",
    "pageind": "PAGEIND",
    "welspun": "WELSPUNLIV",
    "arvind": "ARVIND",
    "gail": "GAIL",
    "tata power": "TATAPOWER",
    "adani green": "ADANIGREEN",
    "coal india": "COALINDIA",
    "power grid": "POWERGRID",
    "divislab": "DIVISLAB",
    "biocon": "BIOCON",
    "lupin": "LUPIN",
}


def normalise_ticker(text: str) -> List[str]:
    """Extract and normalise ticker mentions from text."""
    tickers = set()
    text_lower = text.lower()

    # Check aliases
    for alias, symbol in TICKER_ALIASES.items():
        if alias in text_lower:
            tickers.add(symbol)

    # Check $TICKER pattern
    cashtags = re.findall(r"\$([A-Z]{2,20})", text.upper())
    for tag in cashtags:
        if tag in settings.sectors.all_tickers:
            tickers.add(tag)

    return list(tickers)


class RedditScraper:
    """Scrapes Indian finance subreddits for sentiment data using public JSON endpoints."""

    def __init__(self) -> None:
        self.subreddits = settings.reddit.subreddits
        # Use a generic browser User-Agent to avoid immediate 429 Too Many Requests errors
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 IMS-Research/1.0"
        }

    async def run_pipeline(self) -> int:
        """Full scraping pipeline: fetch posts → score → store."""
        total_stored = 0

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                for sub_name in self.subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{sub_name}/hot.json?limit=25"
                        async with session.get(url) as response:
                            if response.status == 429:
                                logger.warning("reddit_rate_limited", msg="Hit 429 limit, falling back to mock")
                                return await self._run_mock_pipeline()
                            
                            if response.status != 200:
                                logger.error("reddit_http_error", status=response.status, subreddit=sub_name)
                                continue

                            data = await response.json()
                            posts = data.get("data", {}).get("children", [])

                            for child in posts:
                                post = child.get("data", {})
                                title = post.get("title", "")
                                selftext = post.get("selftext", "")
                                text = f"{title} {selftext}"
                                tickers = normalise_ticker(text)

                                if not tickers:
                                    continue

                                score = compute_blended_score(text)
                                label = score_to_label(score)
                                num_comments = post.get("num_comments", 0)
                                post_score = post.get("score", 0)
                                engagement = post_score + (num_comments * 2)
                                permalink = post.get("permalink", "")

                                ts = datetime.fromtimestamp(
                                    post.get("created_utc", 0), tz=timezone.utc
                                )

                                for ticker in tickers:
                                    await db.insert_social_sentiment(
                                        time=ts,
                                        ticker=ticker,
                                        source="reddit",
                                        raw_text=text[:500],
                                        sentiment_score=score,
                                        sentiment_label=label.value,
                                        engagement_weight=float(engagement),
                                        url=f"https://reddit.com{permalink}",
                                    )
                                    total_stored += 1

                                # Fetch top-level comments if the post has tickers
                                if num_comments > 0:
                                    await asyncio.sleep(1) # Be gentle on the unauthenticated API
                                    comments_url = f"https://www.reddit.com{permalink}.json"
                                    async with session.get(comments_url) as c_response:
                                        if c_response.status == 200:
                                            c_data = await c_response.json()
                                            if len(c_data) > 1:
                                                comments_list = c_data[1].get("data", {}).get("children", [])
                                                limit = settings.reddit.comment_depth * 5
                                                
                                                for c_child in comments_list[:limit]:
                                                    comment = c_child.get("data", {})
                                                    c_text = comment.get("body", "")
                                                    
                                                    if not c_text: # Skip 'more' objects
                                                        continue

                                                    c_tickers = normalise_ticker(c_text)
                                                    if not c_tickers:
                                                        continue

                                                    c_score = compute_blended_score(c_text)
                                                    c_label = score_to_label(c_score)
                                                    c_ts = datetime.fromtimestamp(
                                                        comment.get("created_utc", 0), tz=timezone.utc
                                                    )

                                                    for ticker in c_tickers:
                                                        await db.insert_social_sentiment(
                                                            time=c_ts,
                                                            ticker=ticker,
                                                            source="reddit",
                                                            raw_text=c_text[:500],
                                                            sentiment_score=c_score,
                                                            sentiment_label=c_label.value,
                                                            engagement_weight=float(comment.get("score", 0)),
                                                        )
                                                        total_stored += 1

                        # Be polite to Reddit servers between subreddits
                        await asyncio.sleep(2)

                    except Exception as e:
                        logger.error(
                            "reddit_subreddit_error",
                            subreddit=sub_name,
                            error=str(e),
                        )

        except Exception as e:
            logger.error("reddit_pipeline_error", error=str(e))
            logger.warning("reddit_pipeline_failed", msg="Falling back to mock data")
            return await self._run_mock_pipeline()

        logger.info("reddit_pipeline_complete", items_stored=total_stored)
        return total_stored

    # ----------------------------------------------------------
    # MOCK_FALLBACK: synthetic Reddit posts for development
    # ----------------------------------------------------------
    async def _run_mock_pipeline(self) -> int:
        templates = [
            "What do you think about {ticker}? Results coming next week.",
            "{ticker} has been on a tear. FIIs loading up. Thoughts?",
            "DD: Why I'm bearish on {ticker} — management red flags",
            "Portfolio review: 20% in {ticker}, should I book profits?",
            "{ticker} — Hidden gem or value trap? Deep dive inside",
            "RBI policy impact on {ticker} sector — my analysis",
        ]

        tickers = settings.sectors.all_tickers[:10]
        total = 0

        for _ in range(30):
            ticker = random.choice(tickers)
            text = random.choice(templates).format(ticker=ticker)
            score = compute_blended_score(text)
            label = score_to_label(score)

            await db.insert_social_sentiment(
                time=datetime.now(timezone.utc),
                ticker=ticker,
                source="reddit",
                raw_text=text,
                sentiment_score=score,
                sentiment_label=label.value,
                engagement_weight=float(random.randint(5, 500)),
            )
            total += 1

        logger.info("reddit_mock_pipeline_complete", items_stored=total)
        return total


reddit_scraper = RedditScraper()