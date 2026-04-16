# On-demand ticker news scraper
# Searches MoneyControl, Economic Times, and Reddit for a specific ticker
# and returns aggregated news articles with sentiment scores.

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import structlog
from bs4 import BeautifulSoup

from backend.config import settings

logger = structlog.get_logger(__name__)


# Try to import sentiment scoring; fallback if unavailable
try:
    from backend.services.scrapers.twitter_scraper import compute_blended_score, score_to_label
except ImportError:
    def compute_blended_score(text):
        # Simple fallback sentiment
        positive = ["buy", "bullish", "growth", "profit", "surge", "rally", "gain", "upgrade", "beat"]
        negative = ["sell", "bearish", "loss", "decline", "crash", "fall", "downgrade", "miss", "risk"]
        text_lower = text.lower()
        pos = sum(1 for w in positive if w in text_lower)
        neg = sum(1 for w in negative if w in text_lower)
        if pos + neg == 0:
            return 0.0
        return (pos - neg) / (pos + neg)

    def score_to_label(score):
        if score > 0.1:
            return "POSITIVE"
        elif score < -0.1:
            return "NEGATIVE"
        return "NEUTRAL"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}


async def scrape_moneycontrol_for_ticker(ticker: str) -> List[Dict]:
    """Scrape MoneyControl for news about a specific ticker."""
    articles = []
    try:
        search_url = f"https://www.moneycontrol.com/stocks/cptmarket/compsearchnew.php?search_data={ticker}&cid=&mbsearch_str=&topsearch_type=1&search_str={ticker}"
        async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:
            # Try direct news search
            news_url = f"https://www.moneycontrol.com/news/tags/{ticker.lower()}.html"
            resp = await client.get(news_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                items = soup.select("li.clearfix") or soup.select("div.news_list li") or []
                for item in items[:10]:
                    headline_tag = item.find("h2") or item.find("a")
                    if not headline_tag:
                        continue
                    headline = headline_tag.get_text(strip=True)
                    if not headline or len(headline) < 10:
                        continue
                    snippet_tag = item.find("p")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    link = item.find("a", href=True)
                    url = link["href"] if link else ""

                    full_text = f"{headline} {snippet}"
                    score = compute_blended_score(full_text)
                    articles.append({
                        "source": "moneycontrol",
                        "headline": headline,
                        "snippet": snippet[:200],
                        "url": url,
                        "sentiment_score": round(score, 3),
                        "sentiment_label": score_to_label(score),
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    })
    except Exception as e:
        logger.warning("mc_ticker_scrape_error", ticker=ticker, error=str(e))
    return articles


async def scrape_et_for_ticker(ticker: str) -> List[Dict]:
    """Scrape Economic Times for news about a specific ticker."""
    articles = []
    try:
        search_url = f"https://economictimes.indiatimes.com/topic/{ticker}"
        async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(search_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                items = soup.select("div.clr.flt.topic_list") or soup.select("div.eachStory") or []
                for item in items[:10]:
                    headline_tag = item.find("h2") or item.find("a")
                    if not headline_tag:
                        continue
                    headline = headline_tag.get_text(strip=True)
                    if not headline or len(headline) < 10:
                        continue
                    snippet_tag = item.find("p")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    link = item.find("a", href=True)
                    url = link["href"] if link else ""
                    if url and not url.startswith("http"):
                        url = f"https://economictimes.indiatimes.com{url}"

                    full_text = f"{headline} {snippet}"
                    score = compute_blended_score(full_text)
                    articles.append({
                        "source": "economic_times",
                        "headline": headline,
                        "snippet": snippet[:200],
                        "url": url,
                        "sentiment_score": round(score, 3),
                        "sentiment_label": score_to_label(score),
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    })
    except Exception as e:
        logger.warning("et_ticker_scrape_error", ticker=ticker, error=str(e))
    return articles


async def scrape_reddit_for_ticker(ticker: str) -> List[Dict]:
    """Search Reddit Indian investing subs for mentions of a ticker."""
    articles = []
    subreddits = ["IndiaInvestments", "IndianStreetBets", "DalalStreet"]
    try:
        async with httpx.AsyncClient(timeout=15, headers={
            "User-Agent": "IMS/1.0 Stock Analyzer"
        }, follow_redirects=True) as client:
            for sub in subreddits:
                try:
                    url = f"https://www.reddit.com/r/{sub}/search.json?q={ticker}&restrict_sr=1&sort=new&limit=5"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        posts = data.get("data", {}).get("children", [])
                        for post in posts:
                            pd = post.get("data", {})
                            title = pd.get("title", "")
                            selftext = pd.get("selftext", "")[:200]
                            score = compute_blended_score(f"{title} {selftext}")
                            articles.append({
                                "source": f"reddit/{sub}",
                                "headline": title,
                                "snippet": selftext,
                                "url": f"https://reddit.com{pd.get('permalink', '')}",
                                "sentiment_score": round(score, 3),
                                "sentiment_label": score_to_label(score),
                                "published_at": datetime.fromtimestamp(
                                    pd.get("created_utc", 0), tz=timezone.utc
                                ).isoformat(),
                                "upvotes": pd.get("ups", 0),
                                "comments": pd.get("num_comments", 0),
                            })
                    await asyncio.sleep(0.5)  # Rate limiting
                except Exception:
                    continue
    except Exception as e:
        logger.warning("reddit_ticker_scrape_error", ticker=ticker, error=str(e))
    return articles


async def analyze_ticker(ticker: str) -> Dict:
    """
    Full multi-source analysis for a ticker.
    Scrapes MC, ET, Reddit in parallel, then aggregates sentiment.
    """
    ticker = ticker.upper().strip()

    # Fetch from all sources in parallel
    mc_articles, et_articles, reddit_articles = await asyncio.gather(
        scrape_moneycontrol_for_ticker(ticker),
        scrape_et_for_ticker(ticker),
        scrape_reddit_for_ticker(ticker),
    )

    all_articles = mc_articles + et_articles + reddit_articles

    # Calculate aggregate sentiment
    if all_articles:
        scores = [a["sentiment_score"] for a in all_articles]
        avg_sentiment = sum(scores) / len(scores)
        positive = sum(1 for s in scores if s > 0.1)
        negative = sum(1 for s in scores if s < -0.1)
        neutral = len(scores) - positive - negative
    else:
        avg_sentiment = 0.0
        positive = neutral = negative = 0

    if avg_sentiment > 0.15:
        verdict = "BULLISH"
        verdict_color = "#00FF88"
    elif avg_sentiment < -0.15:
        verdict = "BEARISH"
        verdict_color = "#FF3B5C"
    else:
        verdict = "NEUTRAL"
        verdict_color = "#FFB800"

    return {
        "ticker": ticker,
        "total_articles": len(all_articles),
        "avg_sentiment": round(avg_sentiment, 3),
        "verdict": verdict,
        "verdict_color": verdict_color,
        "sentiment_breakdown": {
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
        },
        "source_counts": {
            "moneycontrol": len(mc_articles),
            "economic_times": len(et_articles),
            "reddit": len(reddit_articles),
        },
        "articles": sorted(all_articles, key=lambda x: abs(x["sentiment_score"]), reverse=True)[:20],
    }
