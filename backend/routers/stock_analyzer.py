from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from backend.services.scrapers.ticker_news_scraper import analyze_ticker
from backend.services.scrapers.nse_scraper import fetch_stock_quote

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.get("/{ticker}", response_model=dict)
async def analyze_stock(ticker: str):
    """
    Analyze a stock by scraping MoneyControl, Economic Times, and Reddit.
    Returns aggregated sentiment analysis with individual articles.
    """
    ticker = ticker.upper().strip()

    # Get current price from NSE
    quote = await fetch_stock_quote(ticker)

    # Run multi-source analysis
    analysis = await analyze_ticker(ticker)

    # Add price info
    if quote:
        analysis["current_price"] = quote.get("lastPrice", 0)
        analysis["price_change"] = quote.get("change", 0)
        analysis["price_pchange"] = quote.get("pChange", 0)
        analysis["company_name"] = quote.get("companyName", ticker)
        analysis["day_high"] = quote.get("dayHigh", 0)
        analysis["day_low"] = quote.get("dayLow", 0)
        analysis["previous_close"] = quote.get("previousClose", 0)
    else:
        analysis["current_price"] = None
        analysis["company_name"] = ticker

    # Generate LLM summary if available
    try:
        from backend.services.llm.langchain_orchestrator import llm_orchestrator
        if llm_orchestrator.client and analysis["total_articles"] > 0:
            from langchain_core.messages import SystemMessage, HumanMessage

            headlines = "\n".join([
                f"- [{a['sentiment_label']}] {a['headline']} (Source: {a['source']})"
                for a in analysis["articles"][:15]
            ])

            messages = [
                SystemMessage(content="You are a concise Indian stock market analyst. Provide a brief analysis."),
                HumanMessage(content=f"""Based on these recent news articles about {ticker}, provide a 3-4 sentence market sentiment summary and a clear BUY/HOLD/SELL recommendation with reasoning.

Recent Headlines:
{headlines}

Average Sentiment Score: {analysis['avg_sentiment']}
Positive articles: {analysis['sentiment_breakdown']['positive']}
Negative articles: {analysis['sentiment_breakdown']['negative']}

Reply in 3-4 sentences only. Start with the recommendation."""),
            ]

            llm_summary = await llm_orchestrator.invoke_with_retry(
                messages=messages,
                cache_key=f"stock_analysis_{ticker}",
            )
            if llm_summary:
                analysis["llm_summary"] = llm_summary
    except Exception:
        pass

    return {
        "data": analysis,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }
