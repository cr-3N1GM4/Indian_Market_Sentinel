# Portfolio optimization using LLM analysis
# Takes current holdings + market conditions and suggests improvements

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import structlog

from backend.services.llm.langchain_orchestrator import llm_orchestrator

logger = structlog.get_logger(__name__)

OPTIMIZATION_PROMPT = """You are an expert Indian equity portfolio manager. Analyze this portfolio and provide optimization recommendations.

Current Holdings:
{holdings_text}

Current Market Context:
- Market Mood: {market_mood}
- Nifty 50 Change: {nifty_change}%
- FII Net Flow: ₹{fii_net} Cr (recent)

Instructions:
1. Analyze the portfolio's sector concentration and diversification
2. Identify potential risks
3. Suggest 3-5 specific stocks to ADD to improve the portfolio
4. Suggest any stocks to REDUCE or EXIT with reasoning
5. Provide rebalancing recommendations

Return ONLY valid JSON with this structure:
{{
  "portfolio_health": "GOOD" or "MODERATE" or "NEEDS_ATTENTION",
  "health_score": 1-10 integer,
  "sector_analysis": "string describing sector exposure",
  "key_risks": ["risk1", "risk2"],
  "stocks_to_add": [
    {{"ticker": "SYMBOL", "reason": "why to add", "suggested_weight_pct": 10}}
  ],
  "stocks_to_reduce": [
    {{"ticker": "SYMBOL", "reason": "why to reduce"}}
  ],
  "rebalancing_notes": "overall recommendation string",
  "summary": "2-3 sentence overall assessment"
}}
"""

RISK_ANALYSIS_PROMPT = """You are a risk analyst specializing in Indian equities. Analyze the risk profile of this portfolio.

Holdings:
{holdings_text}

For each holding, assess:
1. Sector risk (regulatory, cyclical, structural)
2. Concentration risk
3. Liquidity risk
4. News/Event risk

Return ONLY valid JSON:
{{
  "overall_risk_level": "LOW" or "MEDIUM" or "HIGH",
  "overall_risk_score": 1-10,
  "holdings_risk": [
    {{
      "ticker": "SYMBOL",
      "risk_level": "LOW/MEDIUM/HIGH",
      "risk_score": 1-10,
      "risk_factors": ["factor1", "factor2"],
      "mitigation": "suggestion"
    }}
  ],
  "portfolio_risks": ["systemic risk descriptions"],
  "recommendation": "overall recommendation"
}}
"""


async def optimize_portfolio(
    holdings: List[Dict[str, Any]],
    market_mood: str = "Neutral",
    nifty_change: float = 0.0,
    fii_net: float = 0.0,
) -> Dict[str, Any]:
    """Use LLM to analyze and optimize portfolio."""

    holdings_text = "\n".join([
        f"- {h['ticker']}: {h['quantity']} shares @ ₹{h['avg_cost']} avg"
        + (f" (Current: ₹{h.get('current_price', 'N/A')})" if h.get('current_price') else "")
        for h in holdings
    ])

    prompt = OPTIMIZATION_PROMPT.format(
        holdings_text=holdings_text,
        market_mood=market_mood,
        nifty_change=nifty_change,
        fii_net=fii_net,
    )

    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content="You are an expert Indian equity portfolio manager."),
        HumanMessage(content=prompt),
    ]

    result = await llm_orchestrator.invoke_with_retry(
        messages=messages,
        cache_key=None,  # Don't cache portfolio-specific advice
    )

    if not result:
        return _mock_optimization(holdings)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error("portfolio_optimize_parse_error", error=str(e))
        return _mock_optimization(holdings)


async def analyze_portfolio_risk(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use LLM to perform risk analysis on portfolio."""

    holdings_text = "\n".join([
        f"- {h['ticker']}: {h['quantity']} shares @ ₹{h['avg_cost']} avg"
        for h in holdings
    ])

    prompt = RISK_ANALYSIS_PROMPT.format(holdings_text=holdings_text)

    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content="You are a risk analyst for Indian equity portfolios."),
        HumanMessage(content=prompt),
    ]

    result = await llm_orchestrator.invoke_with_retry(
        messages=messages,
        cache_key=None,
    )

    if not result:
        return _mock_risk_analysis(holdings)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error("risk_analysis_parse_error", error=str(e))
        return _mock_risk_analysis(holdings)


def _mock_optimization(holdings: List[Dict]) -> Dict:
    return {
        "portfolio_health": "MODERATE",
        "health_score": 6,
        "sector_analysis": "Portfolio is concentrated in limited sectors. Consider diversifying into IT, Banking, and FMCG.",
        "key_risks": [
            "High sector concentration risk",
            "Limited large-cap exposure",
            "No defensive stocks for downside protection",
        ],
        "stocks_to_add": [
            {"ticker": "HDFCBANK", "reason": "Strong fundamentals, consistent growth, adds banking sector exposure", "suggested_weight_pct": 15},
            {"ticker": "TCS", "reason": "IT sector diversification, strong cash flows, defensive in nature", "suggested_weight_pct": 12},
            {"ticker": "ITC", "reason": "FMCG + defensive play, high dividend yield, good for market downturns", "suggested_weight_pct": 10},
        ],
        "stocks_to_reduce": [],
        "rebalancing_notes": "Consider adding 3-4 more large-cap stocks to improve diversification. Target no more than 20% in any single sector.",
        "summary": "Portfolio needs broader sector diversification. Adding banking, IT and FMCG stocks would improve the risk-return profile significantly."
    }


def _mock_risk_analysis(holdings: List[Dict]) -> Dict:
    result_holdings = []
    for h in holdings:
        result_holdings.append({
            "ticker": h["ticker"],
            "risk_level": "MEDIUM",
            "risk_score": 5,
            "risk_factors": ["Sector-specific regulatory risk", "Moderate volatility"],
            "mitigation": "Consider setting stop-loss at 10% below current levels",
        })
    return {
        "overall_risk_level": "MEDIUM",
        "overall_risk_score": 5,
        "holdings_risk": result_holdings,
        "portfolio_risks": [
            "Concentration risk due to limited number of holdings",
            "Sector correlation risk during market downturns",
        ],
        "recommendation": "Diversify across more sectors and add some defensive positions.",
    }
