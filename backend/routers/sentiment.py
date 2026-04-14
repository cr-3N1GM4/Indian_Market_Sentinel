from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from backend.config import settings
from backend.db.timescale_client import db
from backend.models.sentiment_models import (
    SectorHeatmapResponse,
    SectorHeatmapSector,
    SectorHeatmapTicker,
    SentimentTrend,
    TickerSentimentResponse,
)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


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
