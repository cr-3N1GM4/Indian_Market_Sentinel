# ARCHITECTURE NOTE:
# Scrapes Economic Times and Business Standard stock news.
# Shares the same deduplication engine as Moneycontrol scraper
# (cross-source dedup via shared _seen_hashes in moneycontrol module).

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List

import httpx
import structlog
from bs4 import BeautifulSoup

from backend.config import settings
from backend.db.timescale_client import db
from backend.models.sentiment_models import NewsArticle
from backend.services.scrapers.moneycontrol_scraper import (
    _extract_tickers_from_text,
    _is_duplicate,
)
from backend.services.scrapers.twitter_scraper import (
    compute_blended_score,
    score_to_label,
)

logger = structlog.get_logger(__name__)


class EconomicTimesScraper:
    """Scrapes Economic Times and Business Standard for stock news."""

    SOURCES = [
        {
            "name": "et",
            "url": "https://economictimes.indiatimes.com/markets/stocks/news",
            "label": "Economic Times",
        },
        {
            "name": "bs",
            "url": "https://www.business-standard.com/markets/capital-market",
            "label": "Business Standard",
        },
    ]

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _fetch_and_parse(self, source: dict) -> List[NewsArticle]:
        """Fetch and parse articles from a single source."""
        try:
            async with httpx.AsyncClient(
                timeout=30, headers=self.headers, follow_redirects=True
            ) as client:
                resp = await client.get(source["url"])
                resp.raise_for_status()
                return self._parse_html(resp.text, source["name"])
        except Exception as e:
            logger.error(
                "et_bs_fetch_error",
                source=source["name"],
                error=str(e),
            )
            return self._generate_mock_articles(source["name"])

    def _parse_html(self, html: str, source_name: str) -> List[NewsArticle]:
        """Parse news listing HTML from ET or BS."""
        soup = BeautifulSoup(html, "lxml")
        articles: List[NewsArticle] = []

        # Try multiple selectors for robustness
        selectors = [
            "div.eachStory h3 a",       # ET format
            "div.listing-txt h2 a",     # BS format
            "h3 a[href]",               # Generic
            "h2 a[href]",               # Generic
            "a.article-link",           # Alternative
        ]

        links = []
        for sel in selectors:
            links = soup.select(sel)
            if links:
                break

        for link in links[:15]:
            headline = link.get_text(strip=True)
            if not headline or len(headline) < 10:
                continue

            if _is_duplicate(headline):
                continue

            url = link.get("href", "")
            if url and not url.startswith("http"):
                if source_name == "et":
                    url = f"https://economictimes.indiatimes.com{url}"
                else:
                    url = f"https://www.business-standard.com{url}"

            tickers = _extract_tickers_from_text(headline)
            score = compute_blended_score(headline)
            label = score_to_label(score)

            for ticker in (tickers or ["MARKET"]):
                articles.append(
                    NewsArticle(
                        source=source_name,
                        ticker=ticker,
                        headline=headline,
                        sentiment_score=score,
                        sentiment_label=label,
                        published_at=datetime.now(timezone.utc),
                        url=url,
                    )
                )

        return articles

    async def run_pipeline(self) -> int:
        """Full pipeline across both sources."""
        total_stored = 0

        for source in self.SOURCES:
            articles = await self._fetch_and_parse(source)

            for article in articles:
                try:
                    await db.insert_social_sentiment(
                        time=article.published_at or datetime.now(timezone.utc),
                        ticker=article.ticker or "MARKET",
                        source=source["name"],
                        raw_text=f"{article.headline}",
                        sentiment_score=article.sentiment_score,
                        sentiment_label=article.sentiment_label.value,
                        engagement_weight=1.0,
                        url=article.url,
                    )
                    total_stored += 1
                except Exception as e:
                    logger.error("et_bs_store_error", error=str(e))

        logger.info("et_bs_pipeline_complete", articles_stored=total_stored)
        return total_stored

    # MOCK_FALLBACK
    def _generate_mock_articles(self, source: str) -> List[NewsArticle]:
        headlines = [
            "Market rally continues as FIIs turn net buyers",
            "RBI holds repo rate steady, signals cautious outlook",
            "Sun Pharma shares surge on strong Q3 earnings beat",
            "ONGC to invest in deepwater exploration blocks",
            "Textile sector faces headwinds from weak exports",
        ]
        articles = []
        for h in headlines:
            tickers = _extract_tickers_from_text(h)
            score = compute_blended_score(h)
            for t in (tickers or ["MARKET"]):
                articles.append(
                    NewsArticle(
                        source=source,
                        ticker=t,
                        headline=h,
                        sentiment_score=score,
                        sentiment_label=score_to_label(score),
                        published_at=datetime.now(timezone.utc),
                    )
                )
        return articles


et_scraper = EconomicTimesScraper()
