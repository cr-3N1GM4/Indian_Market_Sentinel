# ARCHITECTURE NOTE:
# Processes scraped news articles in batches of 10 through the LLM
# for structured sentiment classification. Includes contradiction
# detection: if 3+ positive articles on a ticker while ICS is negative,
# auto-emits a NEWS_INSTITUTIONAL_DIVERGENCE alert.

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import structlog

from backend.config import settings
from backend.models.sentiment_models import LLMNewsSentiment, NewsArticle
from backend.services.llm.langchain_orchestrator import llm_orchestrator

logger = structlog.get_logger(__name__)

NEWS_SYSTEM_PROMPT = """You are a financial news analyst specialising in Indian equities.
Analyse each article and return structured JSON. For each article, assess:
1. Headline sentiment (POSITIVE, NEGATIVE, NEUTRAL, MIXED)
2. Body sentiment
3. Tickers mentioned (NSE symbols)
4. Event type classification
5. Forward impact assessment
6. Supply chain relevance for Indian pharma/manufacturing

Return a JSON array with one object per article.

Event type must be one of: EARNINGS_BEAT, EARNINGS_MISS, REGULATORY_APPROVAL,
REGULATORY_ACTION, MANAGEMENT_CHANGE, ACQUISITION, DIVESTMENT, CREDIT_RATING,
MACRO_POLICY, SUPPLY_CHAIN, GENERAL_MARKET

Forward impact must be one of: SHORT_TERM_BULLISH, SHORT_TERM_BEARISH,
LONG_TERM_BULLISH, LONG_TERM_BEARISH, NEUTRAL, MIXED
"""


async def process_news_batch(
    articles: List[NewsArticle],
) -> List[LLMNewsSentiment]:
    """Process a batch of articles through the LLM for structured analysis."""

    if not articles:
        return []

    # Build batch prompt
    batch_text = ""
    for i, article in enumerate(articles):
        batch_text += f"\n--- Article {i+1} ---\n"
        batch_text += f"Source: {article.source}\n"
        batch_text += f"Headline: {article.headline}\n"
        if article.body_snippet:
            batch_text += f"Body: {article.body_snippet}\n"
        batch_text += f"Published: {article.published_at}\n"

    user_prompt = f"""Analyse these {len(articles)} articles and return a JSON array:

{batch_text}

Return format: [{{"headline_sentiment": "...", "body_sentiment": "...", "tickers_mentioned": [...], "event_type": "...", "forward_impact_assessment": "...", "impact_duration": "...", "confidence": 0.0-1.0, "key_entities": [...], "supply_chain_relevance": true/false}}]
"""

    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=NEWS_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    result = await llm_orchestrator.invoke_with_retry(messages=messages)

    if not result:
        # Return basic sentiment from existing scores
        return [
            LLMNewsSentiment(
                headline_sentiment=a.sentiment_label,
                body_sentiment=a.sentiment_label,
                tickers_mentioned=[a.ticker] if a.ticker else [],
                event_type=a.event_type or "GENERAL_MARKET",
                confidence=0.5,
            )
            for a in articles
        ]

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]

        parsed = json.loads(cleaned.strip())
        if isinstance(parsed, list):
            return [LLMNewsSentiment(**item) for item in parsed]
        return [LLMNewsSentiment(**parsed)]

    except Exception as e:
        logger.error("news_llm_parse_error", error=str(e))
        return []


async def check_contradiction(
    ticker: str,
    positive_count: int,
    ics_value: float,
    threshold_articles: int = 3,
    ics_threshold: float = -0.30,
) -> bool:
    """
    Contradiction Detection:
    If 3+ positive articles in 6h window but ICS is negative
    → NEWS_INSTITUTIONAL_DIVERGENCE alert
    """
    if positive_count >= threshold_articles and ics_value < ics_threshold:
        logger.info(
            "news_institutional_divergence",
            ticker=ticker,
            positive_articles=positive_count,
            ics=ics_value,
        )
        return True
    return False
