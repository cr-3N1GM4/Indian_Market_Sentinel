from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from backend.config import settings
from backend.db.timescale_client import db
from backend.models.sentiment_models import (
    SentimentHeatmapResponse,
    SectorHeatmapSector,
    SectorHeatmapTicker,
    SentimentTrend,
    TickerSentimentResponse,
)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/trending-news", response_model=dict)
async def get_trending_news(limit: int = Query(default=20, ge=1, le=50)):
    """Get trending market news with sentiment scores."""
    # Try to get real news from DB
    try:
        rows = await db.fetch(
            """
            SELECT raw_text, sentiment_score, sentiment_label, source, url, time
            FROM social_sentiment
            WHERE source IN ('moneycontrol', 'economic_times')
            ORDER BY time DESC
            LIMIT $1
            """,
            limit,
        )
        if rows:
            news = []
            for r in rows:
                text = r["raw_text"] or ""
                parts = text.split(" | ", 1)
                headline = parts[0] if parts else text
                snippet = parts[1] if len(parts) > 1 else ""
                news.append({
                    "headline": headline,
                    "snippet": snippet[:200],
                    "source": r["source"],
                    "sentiment_score": r["sentiment_score"],
                    "sentiment_label": r["sentiment_label"],
                    "url": r.get("url", ""),
                    "time": r["time"].isoformat(),
                })
            return {
                "data": news,
                "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
            }
    except Exception:
        pass

    # Fallback: scrape on the fly
    try:
        from backend.services.scrapers.moneycontrol_scraper import moneycontrol_scraper
        articles = await moneycontrol_scraper.fetch_articles()
        news = []
        for a in articles[:limit]:
            news.append({
                "headline": a.headline,
                "snippet": (a.body_snippet or "")[:200],
                "source": a.source,
                "sentiment_score": a.sentiment_score,
                "sentiment_label": a.sentiment_label.value if hasattr(a.sentiment_label, "value") else str(a.sentiment_label),
                "url": a.url or "",
                "time": (a.published_at or datetime.utcnow()).isoformat(),
            })
        if news:
            return {
                "data": news,
                "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
            }
    except Exception:
        pass

    # Mock fallback
    from backend.services.scrapers.moneycontrol_scraper import moneycontrol_scraper
    mock_articles = moneycontrol_scraper._generate_mock_articles()
    news = []
    for a in mock_articles[:limit]:
        news.append({
            "headline": a.headline,
            "snippet": (a.body_snippet or "")[:200],
            "source": "moneycontrol",
            "sentiment_score": a.sentiment_score,
            "sentiment_label": a.sentiment_label.value if hasattr(a.sentiment_label, "value") else str(a.sentiment_label),
            "url": "",
            "time": datetime.utcnow().isoformat(),
        })
    return {
        "data": news,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0", "stale": True},
    }


@router.get("/market-mood", response_model=dict)
async def get_market_mood():
    """Get market mood index (Fear & Greed style gauge)."""
    import asyncio
    from backend.services.scrapers.market_mood import compute_market_mood

    adv_dec = {"advances": 25, "declines": 25}
    fii_net = 0.0
    vix = 15.0

    # Fetch components with per-call timeouts to avoid hanging
    try:
        from backend.services.scrapers.nse_scraper import fetch_advances_declines
        adv_dec = await asyncio.wait_for(fetch_advances_declines(), timeout=10)
    except Exception:
        pass

    try:
        from backend.services.scrapers.nse_scraper import fetch_fii_dii_activity
        fii_dii = await asyncio.wait_for(fetch_fii_dii_activity(), timeout=10)
        if fii_dii.get("fii"):
            latest = fii_dii["fii"][0] if fii_dii["fii"] else {}
            fii_net = latest.get("netValue", 0)
    except Exception:
        pass

    try:
        from backend.services.scrapers.nse_scraper import fetch_market_indices
        indices = await asyncio.wait_for(fetch_market_indices(), timeout=10)
        v = indices.get("indiaVix", 15)
        if isinstance(v, (int, float)) and v > 0:
            vix = v
    except Exception:
        pass

    # Get average news sentiment from DB
    avg_sentiment = 0.0
    try:
        val = await db.fetchval(
            """
            SELECT AVG(sentiment_score) FROM social_sentiment
            WHERE time > NOW() - INTERVAL '24 hours'
            """
        )
        if val is not None:
            avg_sentiment = float(val)
    except Exception:
        pass

    mood = compute_market_mood(
        advances=adv_dec.get("advances", 25),
        declines=adv_dec.get("declines", 25),
        vix=vix,
        fii_net=fii_net,
        avg_news_sentiment=avg_sentiment,
    )

    return {
        "data": mood,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/{ticker}", response_model=dict)
async def get_ticker_sentiment(
    ticker: str,
    hours: int = Query(default=24, ge=1, le=168),
):
    """Get sentiment data for a specific ticker."""
    crss_row = await db.get_crss_latest(ticker.upper())

    if crss_row:
        # Determine trend
        history = await db.get_crss_history(ticker.upper(), hours=hours)
        trend = SentimentTrend.STABLE
        if len(history) >= 2:
            recent = history[-1]["crss"]
            older = history[0]["crss"]
            if recent - older > 0.1:
                trend = SentimentTrend.RISING
            elif older - recent > 0.1:
                trend = SentimentTrend.FALLING

        return {
            "data": TickerSentimentResponse(
                ticker=ticker.upper(),
                crss=crss_row["crss"],
                twitter_score=crss_row.get("twitter_score"),
                reddit_score=crss_row.get("reddit_score"),
                news_score=crss_row.get("news_score"),
                data_points=crss_row.get("data_points", 0),
                trend=trend,
                last_updated=crss_row["time"],
            ).model_dump(),
            "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
        }

    # Return mock data if no DB data
    import random
    return {
        "data": TickerSentimentResponse(
            ticker=ticker.upper(),
            crss=round(random.uniform(-0.5, 0.5), 2),
            twitter_score=round(random.uniform(-0.5, 0.5), 2),
            reddit_score=round(random.uniform(-0.5, 0.5), 2),
            news_score=round(random.uniform(-0.5, 0.5), 2),
            data_points=random.randint(5, 50),
            trend=SentimentTrend.STABLE,
        ).model_dump(),
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0", "stale": True},
    }


@router.get("/heatmap", response_model=dict)
async def get_sentiment_heatmap():
    """Get sector × source sentiment heatmap data."""
    import random

    sectors_config = {
        "Energy": settings.sectors.energy_tickers[:5],
        "Pharma": settings.sectors.pharma_tickers[:5],
        "Textile": settings.sectors.textile_tickers[:5],
    }

    sectors = {}
    for sector_name, tickers in sectors_config.items():
        sector_tickers = {}
        for ticker in tickers:
            crss_row = await db.get_crss_latest(ticker)
            ics_row = await db.get_ics_latest(ticker)

            sector_tickers[ticker] = SectorHeatmapTicker(
                crss=crss_row["crss"] if crss_row else round(random.uniform(-0.5, 0.5), 2),
                ics=ics_row["ics"] if ics_row else round(random.uniform(-0.5, 0.5), 2),
                crss_trend=SentimentTrend.STABLE,
                data_points=crss_row["data_points"] if crss_row else random.randint(3, 30),
            ).model_dump()

        sectors[sector_name] = {"tickers": sector_tickers}

    return {
        "data": {"sectors": sectors},
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }
