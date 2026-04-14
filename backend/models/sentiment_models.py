# ARCHITECTURE NOTE:
# All data contracts use Pydantic v2 BaseModel for validation,
# serialisation, and auto-generated OpenAPI schemas. Every API
# response flows through these models before leaving the backend.

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SentimentLabel(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class SentimentSource(str, Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    MONEYCONTROL = "moneycontrol"
    ECONOMIC_TIMES = "et"
    BUSINESS_STANDARD = "bs"


class SocialSentimentRecord(BaseModel):
    time: datetime
    ticker: str
    source: SentimentSource
    raw_text: Optional[str] = None
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_label: SentimentLabel
    engagement_weight: float = 0.0
    crss_contribution: float = 0.0
    event_type: Optional[str] = None
    url: Optional[str] = None


class CRSSRecord(BaseModel):
    time: datetime
    ticker: str
    crss: float = Field(ge=-1.0, le=1.0)
    twitter_score: Optional[float] = None
    reddit_score: Optional[float] = None
    news_score: Optional[float] = None
    data_points: int = 0


class SentimentTrend(str, Enum):
    RISING = "RISING"
    FALLING = "FALLING"
    STABLE = "STABLE"


class TickerSentimentResponse(BaseModel):
    ticker: str
    crss: float
    twitter_score: Optional[float] = None
    reddit_score: Optional[float] = None
    news_score: Optional[float] = None
    data_points: int = 0
    trend: SentimentTrend = SentimentTrend.STABLE
    last_updated: Optional[datetime] = None


class SectorHeatmapTicker(BaseModel):
    crss: float = 0.0
    ics: float = 0.0
    crss_trend: SentimentTrend = SentimentTrend.STABLE
    data_points: int = 0


class SectorHeatmapSector(BaseModel):
    tickers: Dict[str, SectorHeatmapTicker]


class SentimentHeatmapResponse(BaseModel):
    sectors: Dict[str, SectorHeatmapSector]


class NewsArticle(BaseModel):
    source: str
    ticker: Optional[str] = None
    headline: str
    body_snippet: Optional[str] = None
    sentiment_score: float = 0.0
    sentiment_label: SentimentLabel = SentimentLabel.NEUTRAL
    event_type: Optional[str] = None
    published_at: Optional[datetime] = None
    url: Optional[str] = None


class LLMNewsSentiment(BaseModel):
    headline_sentiment: SentimentLabel
    body_sentiment: SentimentLabel
    tickers_mentioned: List[str] = []
    event_type: str = "GENERAL_MARKET"
    forward_impact_assessment: str = "NEUTRAL"
    impact_duration: str = "UNKNOWN"
    confidence: float = 0.5
    key_entities: List[str] = []
    supply_chain_relevance: bool = False
